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


# The ambient the engine sizes to today. A single named constant so a future
# design-level ambient setting has one place to thread through — see ADR-0004
# and the "AC power at ambient" entry in CONTEXT.md. Not user-configurable yet.
DEFAULT_AMBIENT_C = 40.0

# The switchgear rated current a transformer station falls back to when its
# supplier publishes none — the standard IEC ring-main-unit size. Silence is
# not the absence of a limit (ADR-0006). It lives here and deliberately NOT in
# the YAML, so that a figure in a station's datasheet block always means a
# supplier published it.
DEFAULT_SWITCHGEAR_RATED_CURRENT_A = 630.0

# The cable entry a transformer station falls back to when its supplier
# publishes no figure, and the fixed figure assumed at the busbar end of a
# circuit's first cable — no station sits there to publish one (ADR-0007).
# Reused by both, so one number ever means "2 x 300 mm^2" in this engine. It
# lives here and deliberately NOT in the YAML, mirroring
# DEFAULT_SWITCHGEAR_RATED_CURRENT_A. Lowered from 2 x 630 mm^2 at
# implementation — see ADR-0007's amendment.
DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE = 2
DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2 = 300.0

# Standard rating ladder for SIZED busbar switchgear — the busbar, one feeder
# per circuit, and the export switchgear (ADR-0007, CONTEXT.md's "Busbar
# switchgear"). Unlike a transformer station's switchgear, this equipment is
# not a catalogue product with a published rating: the tool sizes each part to
# the smallest standard rating that carries its design-point current, with no
# utilization margin.
BUSBAR_SWITCHGEAR_LADDER_A = (630.0, 800.0, 1250.0, 1600.0, 2000.0, 2500.0, 3150.0, 4000.0)


def size_busbar_switchgear_rating(current_a: float) -> float | None:
    """The smallest ``BUSBAR_SWITCHGEAR_LADDER_A`` rating [A] carrying
    ``current_a``, or ``None`` when it exceeds the ladder's top (ADR-0007).

    No utilization margin, mirroring ``switchgear_rated_current_a``. The
    1e-9 tolerance matches the through-current-vs-rating comparisons
    elsewhere in the engine, so a current of exactly one rating (e.g. exactly
    630 A) resolves to that rating rather than escalating to the next size.
    A current above the top of the ladder has no admissible size; the caller
    still solves the design and flags it (ADR-0006's split) rather than
    raising, since this function never sees the busbar node to point at.
    """
    for rating in BUSBAR_SWITCHGEAR_LADDER_A:
        if current_a <= rating + 1e-9:
            return rating
    return None


def busbar_switchgear_rating(current_a: float, pin_a: float | None = None) -> float | None:
    """A busbar switchgear part's rating [A]: its pin when the engineer set
    one — checked, never resized — otherwise the sized rating (ADR-0007)."""
    return pin_a if pin_a is not None else size_busbar_switchgear_rating(current_a)


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
    s_rated_kva_at_40c: float
    uk_percent: float
    pk_kw: float
    p0_kw: float = 0.0
    i0_percent: float = 0.0
    s_rated_kva_at_30c: float | None = None  # None: not published — see ADR-0004
    hv_kv: float | None = None
    lv_kv: float | None = None
    brand: str | None = None  # manufacturer, for catalogue display
    series: str | None = None  # supplier product family
    model: str | None = None  # typed parameter — never computed with
    vector_group: str | None = None  # typed parameter — never computed with
    cooling: str | None = None  # typed parameter — never computed with
    datasheet_url: str | None = None  # typed parameter — never computed with

    # --- Typed parameters ------------------------------------------------
    # Structured, stored, displayed — never read by the sizing engine. See
    # CONTEXT.md's "Simulated parameter / typed parameter" entry. All optional:
    # ``None`` means the datasheet is silent, not zero. String-valued fields are
    # transcribed verbatim from the datasheet row — not normalised or parsed.
    mv_kv_min: float | None = None
    mv_kv_max: float | None = None
    lv_winding_count: int = 1
    insulation_level: str | None = None
    f_nominal: str | None = None                # string: some products publish two
    uk_tolerance_pct: float | None = None
    winding_material_mv: str | None = None
    winding_material_lv: str | None = None
    ip_rating_transformer: str | None = None
    ip_rating_enclosure: str | None = None
    rmu_kv_min: float | None = None
    rmu_kv_max: float | None = None
    # SIMULATED, despite sitting among its typed RMU siblings: the sizing
    # engine reads this one. The domain calls it the switchgear rated current
    # and it bounds a station's through current (ADR-0006). ``None`` means the
    # supplier publishes no figure — resolve it through
    # ``switchgear_rated_current_a``, never read it raw.
    rmu_rated_current_a: float | None = None
    rmu_units: str | None = None
    rmu_relay_protection: str | None = None
    rmu_short_time_withstand: str | None = None
    cabinet_protection: str | None = None
    surge_protection: str | None = None
    ac_insulation_detection: str | None = None
    cabinet_temp_control: str | None = None
    ups: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    weight_kg: float | None = None
    cable_entry: str | None = None
    # SIMULATED, despite sitting beside its typed ``cable_entry`` string
    # sibling above: the sizing engine reads this pair to bound a circuit
    # cable (ADR-0007, CONTEXT.md's "Cable entry"). Resolve through
    # ``cable_entry_parallel_limit`` / ``cable_entry_cross_section_limit_mm2``,
    # never read raw. A datasheet publishing only one of the pair is treated
    # as unpublished (``cable_entry_published``) — one cable entry per
    # station model, never a mixed published/defaulted pair.
    cable_entry_cables_per_phase: int | None = None
    cable_entry_max_cross_section_mm2: float | None = None
    corrosion_class: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    altitude_max_m: float | None = None
    communication: str | None = None
    standards: str | None = None
    datasheet_version: str | None = None
    datasheet_date: str | None = None
    market: str | None = None
    preliminary: bool = False
    # Typed datasheet fields used by complete transformer-station views. They
    # stay strings where suppliers publish compound values or qualifiers.
    transformer_type: str | None = None
    transformer_tappings: str | None = None
    transformer_oil_type: str | None = None
    transformer_efficiency: str | None = None
    maximum_input_current: str | None = None
    lv_panel_segregation: str | None = None
    lv_main_switches: str | None = None
    lv_inverter_switches: str | None = None
    auxiliary_transformer: str | None = None
    auxiliary_output_voltage: str | None = None
    transformer_protection: str | None = None
    internal_arc_classification: str | None = None
    ac_input_protection: str | None = None
    optional_features: str | None = None
    weight_specification: str | None = None

    def __post_init__(self) -> None:
        required_positive = {
            "s_rated_kva_at_40c": self.s_rated_kva_at_40c,
            "uk_percent": self.uk_percent,
        }
        for field, value in required_positive.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive number")
        for field, value in {"pk_kw": self.pk_kw, "p0_kw": self.p0_kw, "i0_percent": self.i0_percent}.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative number")
        if self.s_rated_kva_at_30c is not None and self.s_rated_kva_at_30c <= 0:
            raise ValueError("s_rated_kva_at_30c must be positive when published")
        if self.rmu_rated_current_a is not None and self.rmu_rated_current_a <= 0:
            raise ValueError("rmu_rated_current_a must be positive when published")
        if self.cable_entry_cables_per_phase is not None:
            invalid = (isinstance(self.cable_entry_cables_per_phase, bool)
                       or not isinstance(self.cable_entry_cables_per_phase, int)
                       or self.cable_entry_cables_per_phase <= 0)
            if invalid:
                raise ValueError(
                    "cable_entry_cables_per_phase must be a positive integer when published"
                )
        if (self.cable_entry_max_cross_section_mm2 is not None
                and self.cable_entry_max_cross_section_mm2 <= 0):
            raise ValueError(
                "cable_entry_max_cross_section_mm2 must be positive when published"
            )

    @property
    def switchgear_rated_current_a(self) -> float:
        """The continuous current this station's MV switchgear can carry [A].

        A hard limit on the station's through current, with no utilization
        factor: unlike a cable's ampacity it carries no installation-condition
        margin (ADR-0006). An unpublished figure resolves to
        ``DEFAULT_SWITCHGEAR_RATED_CURRENT_A`` rather than to no limit;
        ``switchgear_rating_published`` says which happened.
        """
        if self.rmu_rated_current_a is None:
            return DEFAULT_SWITCHGEAR_RATED_CURRENT_A
        return float(self.rmu_rated_current_a)

    @property
    def switchgear_rating_published(self) -> bool:
        """Whether the figure came from the supplier or from the fallback.

        Kept visible so callers can report a defaulted rating instead of
        presenting it as published data — the same reason
        ``PvInverterCapability`` keeps its source ambient.
        """
        return self.rmu_rated_current_a is not None

    @property
    def cable_entry_published(self) -> bool:
        """Whether BOTH cable-entry figures came from the supplier.

        One cable entry per station model (CONTEXT.md's "Cable entry"): a
        datasheet publishing only cables-per-phase or only the cross-section
        is treated as unpublished, never a mixed published/defaulted pair.
        """
        return (self.cable_entry_cables_per_phase is not None
                and self.cable_entry_max_cross_section_mm2 is not None)

    @property
    def cable_entry_parallel_limit(self) -> int:
        """Cables accepted per phase [count] at this station's terminals.

        Falls back to ``DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE`` when
        unpublished, never to no limit (ADR-0007). Bounds the parallel-run
        count a circuit cable at this station may use — the stricter of the
        two ends of a segment wins; see ``powertool.cable_sizing``.
        """
        if not self.cable_entry_published:
            return DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE
        return int(self.cable_entry_cables_per_phase)

    @property
    def cable_entry_cross_section_limit_mm2(self) -> float:
        """Maximum cable cross-section [mm^2] this station's terminals accept.

        Falls back to ``DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2`` when
        unpublished, never to no limit (ADR-0007).
        """
        if not self.cable_entry_published:
            return DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2
        return float(self.cable_entry_max_cross_section_mm2)

    def rating_at(self, ambient_c: float) -> float:
        """The published rating [kVA] at ``ambient_c`` — lookup only, never
        interpolated. See CONTEXT.md's "AC power at ambient" and ADR-0004.

        An exact published ambient wins. Otherwise the nearest published
        ambient AT OR ABOVE the requested one — a hotter rating is a lower
        one, so this understates rather than invents. Otherwise (nothing
        published at or above) the highest published ambient.
        """
        published: dict[float, float] = {40.0: self.s_rated_kva_at_40c}
        if self.s_rated_kva_at_30c is not None:
            published[30.0] = self.s_rated_kva_at_30c
        if ambient_c in published:
            return published[ambient_c]
        at_or_above = [a for a in published if a >= ambient_c]
        chosen = min(at_or_above) if at_or_above else max(published)
        return published[chosen]

    @property
    def display_name(self) -> str:
        """Catalogue label: ``"POWER kVA - BRAND"`` when a brand is set, else the
        raw name (e.g. the generic placeholders)."""
        if self.brand:
            return f"{self.s_rated_kva_at_40c:g} kVA - {self.brand}"
        return self.name

    @property
    def ur_percent(self) -> float:
        """Resistive part of the short-circuit voltage [%], from the load loss."""
        return 100.0 * self.pk_kw / self.rating_at(DEFAULT_AMBIENT_C)

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
        s_rated = self.rating_at(DEFAULT_AMBIENT_C)
        load_ratio_sq = (s_kva / s_rated) ** 2
        p_cu = self.pk_kw * load_ratio_sq
        dp_kw = p_cu + self.p0_kw

        q_x = (self.ux_percent / 100.0) * (s_kva ** 2) / s_rated
        q_mag = (self.i0_percent / 100.0) * s_rated
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
        return sum(tx.rating_at(DEFAULT_AMBIENT_C) * count for tx, count in self.units)

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
            s_rated = tx.rating_at(DEFAULT_AMBIENT_C)
            dp_kw += count * (tx.pk_kw * r_sq + tx.p0_kw)
            dq_kvar += count * (
                (tx.ux_percent / 100.0) * r_sq * s_rated
                + (tx.i0_percent / 100.0) * s_rated
            )
        return dp_kw, dq_kvar


@dataclass
class AuxLoad:
    """A lumped auxiliary load (e.g. substation auxiliaries) consuming P and Q."""

    name: str
    p_kw: float
    q_kvar: float = 0.0


def fleet_label(fleet_kind: str) -> str:
    """The fleet itself, in the capitals a reader expects: "PV" or "BESS"."""
    return "BESS" if fleet_kind == "bess" else "PV"


def conversion_label(fleet_kind: str) -> str:
    """What to CALL the conversion device of a fleet: "PCS" or "inverter".

    Presentation only. The result fields are neither renamed nor duplicated per
    fleet kind — a BESS station's converted power lives in exactly the same
    ``p_inv_kw`` a PV station's does, because it is the same quantity computed
    the same way. Only the word in front of the engineer changes, because a
    battery project's reviewer expects to read "PCS".

    An unrecognised kind reads as the neutral default rather than raising: a
    report is the last place to discover an unknown fleet kind, and "inverter"
    is the pre-BESS reading the rest of the code already falls back to.
    """
    return "PCS" if fleet_kind == "bess" else "inverter"


@dataclass(frozen=True)
class BessSolution:
    """A named BESS supplier product, selected from a catalogue.

    Identified the way a supplier quote is: a brand, a series and a model
    number. The model number already encodes the discharge duration — Sungrow's
    ``ST6900UX-4H`` sells 4 h — so ``duration_h`` is DECLARED from the
    nameplate, not derived from energy and power (6904 kWh / 4 x 450 kVA works
    out to 3.84 h; the nameplate still says 4H). This is the same "declared,
    not derived" stance ADR-0002 takes for technology.

    Choosing a solution fixes everything the sizing of a BESS station depends
    on: the nominal energy, the PCS rating (apparent power per unit and a unit
    count) and LV voltage, and the worst-case auxiliary draw. The container
    count per station is NOT a property of the solution — it is a property of
    the pairing between a solution and a station transformer (one solution is
    sold behind many station transformer ratings, each serving a different
    count), read from ``ComponentDatabase.bess_pairings``. See
    :func:`powertool.graph.supported_durations` and ``data/bess_transformers.yaml``.
    """

    name: str
    brand: str
    series: str
    model: str
    e_nominal_kwh: float
    pcs_s_kva: float                         # apparent power, ONE PCS unit
    pcs_count: int                           # PCS units per container
    pcs_lv_kv: float
    duration_h: float                        # declared from the model number
    aux_p_kw: float | None = None             # None: the datasheet publishes no figure —
    aux_q_kvar: float | None = None           # the engine sums it as zero but raises an
                                               # informational notice (see powertool.graph).
                                               # 0.0 means the datasheet states zero.
    datasheet_version: str | None = None
    preliminary: bool = False
    datasheet_url: str | None = None

    # --- Typed parameters ------------------------------------------------
    # Structured, stored, displayed — never read by the sizing engine. See
    # CONTEXT.md's "Simulated parameter / typed parameter" entry. All optional:
    # ``None`` means the datasheet is silent, not zero. Where the datasheet
    # states an inequality (e.g. "> 0.99", "< 1 %"), the bound is stored here
    # and the comparator belongs in the view, not the data.
    cell_type: str | None = None
    dc_v_min: float | None = None
    dc_v_max: float | None = None
    ac_v_min: float | None = None
    ac_v_max: float | None = None
    ac_i_a: float | None = None                 # per PCS unit
    pf_at_nominal: float | None = None
    q_range_percent: float | None = None        # symmetric bound, e.g. 100.0 == "-100% ~ 100%"
    f_nominal_hz: str | None = None             # string: some products support two frequencies
    thdi_percent: float | None = None
    isolation: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    weight_kg: float | None = None
    ip_rating: str | None = None
    corrosion_class: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    altitude_max_m: float | None = None
    cooling: str | None = None

    @property
    def display_name(self) -> str:
        """Catalogue label: series first, model number qualifies it —
        ``"PowerTitan 3.0 — ST6900UX-4H"`` — because the series is how the
        product is recognised and the model number is what distinguishes two
        durations of it."""
        return f"{self.series} — {self.model}"


@dataclass(frozen=True)
class PvInverterCapability:
    """One inverter unit's power resolved at a requested ambient.

    The project interprets the datasheet power at power factor 1, so this one
    scalar is both the active limit in kW and the apparent limit in kVA.  The
    source ambient remains visible so callers can report a conservative
    fallback instead of silently presenting it as published data.
    """

    power_kw: float
    requested_ambient_c: float
    source_ambient_c: float

    @property
    def used_fallback(self) -> bool:
        return not math.isclose(self.requested_ambient_c, self.source_ambient_c)

    @property
    def active_power_kw(self) -> float:
        return self.power_kw

    @property
    def apparent_power_kva(self) -> float:
        return self.power_kw


@dataclass(frozen=True)
class PvInverter:
    """A curated PV inverter product selected inside a transformer station."""

    name: str
    brand: str
    series: str
    model: str
    power_kw_at_40c: float
    power_kw_at_30c: float | None
    nominal_ac_voltage_kv: float
    minimum_power_factor: float | None
    # Provenance for the ambient power used by the engine. This is separate
    # from the datasheet citation because owner-declared engineering values
    # must never masquerade as supplier temperature claims (ADR-0005).
    power_provenance: str
    datasheet_url: str | None = None
    datasheet_version: str | None = None
    datasheet_date: str | None = None
    market: str | None = None
    preliminary: bool = False
    maximum_efficiency_percent: float | None = None
    european_efficiency_percent: float | None = None
    dc_voltage_max_v: float | None = None
    dc_voltage_min_v: float | None = None
    dc_voltage_nominal_v: float | None = None
    mppt_count: int | None = None
    strings_per_mppt: int | None = None
    input_current_per_mppt_a: float | None = None
    short_circuit_current_per_mppt_a: float | None = None
    rated_ac_power_kw: float | None = None
    max_ac_apparent_power_kva: float | None = None
    max_ac_current_a: float | None = None
    thdi_percent: float | None = None
    protection: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    weight_kg: float | None = None
    ip_rating: str | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    altitude_max_m: float | None = None
    cooling: str | None = None
    communication: str | None = None
    max_ac_active_power_kw: float | None = None
    nominal_ac_current_a: float | None = None
    rated_grid_frequency: str | None = None
    adjustable_power_factor: str | None = None
    pv_inputs_per_mppt: str | None = None
    start_voltage_v: float | None = None
    relative_humidity: str | None = None
    corrosion_class: str | None = None
    isolation: str | None = None
    dc_connector: str | None = None
    ac_connector: str | None = None
    standards: str | None = None
    grid_support: str | None = None
    weight_specification: str | None = None

    def __post_init__(self) -> None:
        required_text = {
            "brand": self.brand,
            "series": self.series,
            "model": self.model,
            "power_provenance": self.power_provenance,
        }
        for field, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        required_positive = {
            "power_kw_at_40c": self.power_kw_at_40c,
            "nominal_ac_voltage_kv": self.nominal_ac_voltage_kv,
        }
        for field, value in required_positive.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{field} must be a positive number")
        if self.power_kw_at_30c is not None and self.power_kw_at_30c <= 0:
            raise ValueError("power_kw_at_30c must be positive when published")

    @property
    def display_name(self) -> str:
        return f"{self.series} — {self.model}"

    def capability_at(self, ambient_c: float) -> PvInverterCapability:
        """Resolve the published/declaration-backed power without interpolation.

        The only supported design ambients are 30 and 40 °C.  A missing 30 °C
        value falls back to the required 40 °C value, conservatively.  Keeping
        the selected source ambient in the result makes that fallback
        externally reportable.
        """
        if math.isclose(ambient_c, 30.0, rel_tol=1e-9, abs_tol=1e-9):
            if self.power_kw_at_30c is not None:
                return PvInverterCapability(self.power_kw_at_30c, ambient_c, 30.0)
            return PvInverterCapability(self.power_kw_at_40c, ambient_c, 40.0)
        if math.isclose(ambient_c, 40.0, rel_tol=1e-9, abs_tol=1e-9):
            return PvInverterCapability(self.power_kw_at_40c, ambient_c, 40.0)
        raise ValueError(f"Unsupported inverter ambient {ambient_c:g} °C; use 30 or 40 °C")


@dataclass(frozen=True)
class PvInverterPairing:
    maximum_count: int
    count_provenance: str

    def __post_init__(self) -> None:
        if isinstance(self.maximum_count, bool) or not isinstance(self.maximum_count, int) or self.maximum_count < 1:
            raise ValueError("maximum_count must be a positive integer")
        if not isinstance(self.count_provenance, str) or not self.count_provenance.strip():
            raise ValueError("count_provenance must be a non-empty string")
