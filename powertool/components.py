"""Component physics models for the power simulation tool.

Each component knows how to compute its own losses from the apparent power
flowing through it. There is deliberately NO solver and NO I/O here, so these
models can be unit-tested in isolation.

Conventions / assumptions (apply to every model in this module):
  * Three-phase, balanced, positive-sequence, RMS, steady-state.
  * Voltages are line-to-line, in kV.
  * Active power P in kW, reactive power Q in kvar, apparent power S in kVA.
  * Sign convention for returned losses: ΔP, ΔQ are *consumed* by the element
    (positive). Capacitive charging, which *produces* reactive power, is
    returned as a positive "generated" quantity by its own method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SQRT3 = math.sqrt(3.0)


def current_a(s_kva: float, v_kv: float) -> float:
    """Line current [A] for three-phase apparent power S [kVA] at V_LL [kV].

    From S = sqrt(3) * V_LL * I, with S in VA and V in V, this reduces to
    I[A] = S[kVA] / (sqrt(3) * V[kV]).
    """
    if v_kv <= 0:
        raise ValueError(f"Voltage must be positive, got {v_kv} kV")
    return s_kva / (SQRT3 * v_kv)


@dataclass
class Cable:
    """A cable *type*: electrical parameters given per kilometre.

    A placed cable segment also has a length (km), which is passed to the
    methods below rather than stored on the type, so one type can be reused at
    many lengths.
    """

    name: str
    r_ohm_per_km: float
    x_ohm_per_km: float
    b_us_per_km: float = 0.0
    cross_section_mm2: float | None = None
    material: str | None = None
    rated_current_a: float | None = None
    rated_voltage_kv: float | None = None

    def series_losses(self, s_kva: float, v_kv: float, length_km: float) -> tuple[float, float]:
        """Series losses (ΔP [kW], ΔQ [kvar]) for S [kVA] flowing at V_LL [kV].

        ΔP = 3 I² R and ΔQ = 3 I² X, with R = r_per_km * length and similarly X.
        """
        r = self.r_ohm_per_km * length_km
        x = self.x_ohm_per_km * length_km
        i = current_a(s_kva, v_kv)
        dp_kw = 3.0 * i * i * r / 1000.0
        dq_kvar = 3.0 * i * i * x / 1000.0
        return dp_kw, dq_kvar

    def charging_kvar(self, v_kv: float, length_km: float) -> float:
        """Capacitive reactive power *generated* by the cable [kvar] (positive).

        Q_charging = V_LL² * B_total. With V in kV and B in microsiemens this
        works out to Q[kvar] = V_kV² * B_us / 1000.
        """
        b_us = self.b_us_per_km * length_km
        return v_kv * v_kv * b_us / 1000.0


@dataclass
class Transformer:
    """A two-winding transformer, defined by its nameplate / factory-test data.

    Loss model (standard short-circuit + open-circuit test model):
      * Copper (load) loss scales with the square of loading: Pk * (S/Sr)².
      * Iron (no-load) loss P0 is treated as constant.
      * The reactive part of the short-circuit voltage (ux%) drives the load-
        dependent reactive loss; i0% gives the (roughly constant) magnetizing
        reactive demand.
    """

    name: str
    s_rated_kva: float
    uk_percent: float
    pk_kw: float
    p0_kw: float = 0.0
    i0_percent: float = 0.0
    hv_kv: float | None = None
    lv_kv: float | None = None
    brand: str | None = None  # manufacturer, for catalogue display

    @property
    def display_name(self) -> str:
        """Catalogue label: ``"POWER kVA - BRAND"`` when a brand is set, else the
        raw name (e.g. the generic placeholders)."""
        if self.brand:
            return f"{self.s_rated_kva:g} kVA - {self.brand}"
        return self.name

    @property
    def ur_percent(self) -> float:
        """Resistive part of the short-circuit voltage [%], from the load loss."""
        return 100.0 * self.pk_kw / self.s_rated_kva

    @property
    def ux_percent(self) -> float:
        """Reactive part of the short-circuit voltage [%]: sqrt(uk² - ur²)."""
        ur = self.ur_percent
        val = self.uk_percent ** 2 - ur ** 2
        if val < 0:
            raise ValueError(
                f"Transformer '{self.name}': uk% ({self.uk_percent}) is smaller than the "
                f"resistive part ur% ({ur:.3f}) implied by the load losses — check Pk/uk."
            )
        return math.sqrt(val)

    def losses(self, s_kva: float, v_kv: float | None = None) -> tuple[float, float]:
        """Losses (ΔP [kW], ΔQ [kvar]) at load S [kVA].

        v_kv is accepted for a uniform interface with Cable but is not needed:
        this model is expressed in per-unit of the transformer rating.
        """
        load_ratio_sq = (s_kva / self.s_rated_kva) ** 2
        p_cu = self.pk_kw * load_ratio_sq
        dp_kw = p_cu + self.p0_kw

        q_x = (self.ux_percent / 100.0) * (s_kva ** 2) / self.s_rated_kva
        q_mag = (self.i0_percent / 100.0) * self.s_rated_kva
        dq_kvar = q_x + q_mag
        return dp_kw, dq_kvar


@dataclass
class TransformerGroup:
    """Parallel transformers of mixed ratings sharing one section's power.

    Models a fleet of LV/MV stations (possibly different models and counts)
    connected in parallel at the same voltage level. The load splits at EQUAL
    PER-UNIT LOADING: each unit carries S x (its rating / fleet rating) — the
    standard assumption when each station's inverters are sized to its rating.
    A group of one type with count n is numerically identical to a single
    Transformer element with n_parallel = n.
    """

    name: str
    units: list[tuple[Transformer, int]]  # (transformer type, count)

    def __post_init__(self) -> None:
        if not self.units:
            raise ValueError(f"TransformerGroup '{self.name}' needs at least one unit")
        for tx, count in self.units:
            if count < 1:
                raise ValueError(
                    f"TransformerGroup '{self.name}': count for '{tx.name}' must be "
                    f">= 1, got {count}"
                )

    @property
    def s_rated_total_kva(self) -> float:
        """Fleet rating: the sum of every unit's rated power."""
        return sum(tx.s_rated_kva * count for tx, count in self.units)

    @property
    def n_units(self) -> int:
        return sum(count for _, count in self.units)

    def losses(self, s_kva: float, v_kv: float | None = None) -> tuple[float, float]:
        """Losses (ΔP [kW], ΔQ [kvar]) at total load S [kVA], split at equal
        per-unit loading r = S / S_fleet across every unit."""
        r_sq = (s_kva / self.s_rated_total_kva) ** 2
        dp_kw = 0.0
        dq_kvar = 0.0
        for tx, count in self.units:
            dp_kw += count * (tx.pk_kw * r_sq + tx.p0_kw)
            dq_kvar += count * (
                (tx.ux_percent / 100.0) * r_sq * tx.s_rated_kva
                + (tx.i0_percent / 100.0) * tx.s_rated_kva
            )
        return dp_kw, dq_kvar


@dataclass
class AuxLoad:
    """A lumped auxiliary load (e.g. substation auxiliaries) consuming P and Q."""

    name: str
    p_kw: float
    q_kvar: float = 0.0


@dataclass(frozen=True)
class BessSolution:
    """A named BESS supplier product, selected from a catalogue.

    Choosing a solution fixes everything the sizing of a BESS station depends
    on: the energy in one container, the power and LV voltage of one PCS, the
    worst-case auxiliary draw, and the container count the supplier offers at
    each discharge duration. ``containers_by_duration`` is READ, never
    interpolated, derived or rounded — a duration the solution does not sell
    cannot be requested.
    """

    name: str
    e_container_kwh: float
    pcs_p_kw: float
    pcs_lv_kv: float
    aux_p_kw: float                          # worst case, from the spec sheet
    aux_q_kvar: float
    containers_by_duration: dict[float, int]  # discharge hours -> containers per station
