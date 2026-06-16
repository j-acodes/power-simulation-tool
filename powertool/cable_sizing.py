"""Automatic cable selection: pick the lowest cross-section that respects an
admissible power-loss budget, with the number of parallel circuits set by ampacity.

Selection rule (confirmed with the team):
  * Ampacity (hard limit): per-circuit current must stay below ``max_utilization``
    x rated current (default 0.80, i.e. a 1.25 design factor).
  * Power-loss budget (the governing sizing driver): the cable's active loss, as a
    percentage of the local active power through the section, must stay under the
    admissible limit. The budget is per section and is expressed as
    ``admissible % = base % + per_km % x length_km``:
        - Collection cables (inverters -> MV/HV transformer): base = 1.30 %, per_km = 0.
        - Export cables (last MV panel -> POC):               base = 0,      per_km = 0.1 %.
  * Circuits are set by ampacity (fewest circuits for which a cable fits), then the
    *smallest cross-section* that also meets the loss budget is chosen ("lowest
    cable section possible").
  * Voltage drop is an optional extra cap (off by default), since the loss budget
    now governs.

Loss of a cable carrying total current I over n parallel circuits of length L:
    dP_total = 3 * I^2 * (r_per_km * L) / n      [W]   (per-circuit loss summed over n)
Voltage drop uses the standard approximate three-phase formula with the local PF.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .components import Cable, current_a


@dataclass
class AutoCable:
    """A cable section to be auto-sized from a candidate catalogue based on load.

    The admissible loss budget is ``max_loss_percent_base + max_loss_percent_per_km
    * length_km`` — one mechanism that covers both the constant collection budget and
    the distance-scaled export budget.
    """

    candidates: list[Cable]
    max_utilization: float = 0.80
    max_loss_percent_base: float = 1.30  # collection default
    max_loss_percent_per_km: float = 0.0  # export uses 0.1
    max_vdrop_percent: float | None = None  # optional extra cap; None = not enforced
    max_parallel: int = 12
    name: str = "auto cable"

    def admissible_loss_percent(self, length_km: float) -> float:
        return self.max_loss_percent_base + self.max_loss_percent_per_km * length_km


@dataclass
class CableSelection:
    """The result of auto-sizing one cable section."""

    cable: Cable
    n_parallel: int
    current_per_circuit_a: float
    utilization: float  # I_per_circuit / rated_current
    loss_percent: float  # active loss as % of local active power
    vdrop_percent: float  # section voltage drop (computed for reporting)


def select_cable(
    candidates: list[Cable],
    s_kva: float,
    v_kv: float,
    length_km: float,
    cos_phi: float,
    sin_phi: float,
    max_utilization: float = 0.80,
    max_loss_percent: float | None = None,
    max_vdrop_percent: float | None = None,
    max_parallel: int = 12,
) -> CableSelection:
    """Pick the fewest circuits (by ampacity) then the smallest cross-section that
    also meets the loss budget (and optional voltage-drop cap)."""
    usable = [
        c for c in candidates
        if c.rated_current_a is not None and c.cross_section_mm2 is not None
    ]
    if not usable:
        raise ValueError(
            "No usable cables in the catalogue (need rated_current_a and "
            "cross_section_mm2) for this voltage section."
        )

    i_total = current_a(s_kva, v_kv)
    p_active = s_kva * cos_phi  # local active power [kW]
    by_area = sorted(usable, key=lambda c: c.cross_section_mm2)

    # Increasing n: fewer circuits first. Within an n, ascending cross-section: the
    # first cable that satisfies every constraint is the smallest section for that n.
    for n in range(1, max_parallel + 1):
        i_circuit = i_total / n
        for c in by_area:
            if i_circuit > max_utilization * c.rated_current_a:
                continue  # fails ampacity

            r = c.r_ohm_per_km * length_km
            x = c.x_ohm_per_km * length_km
            dp_total_kw = 3.0 * i_circuit * i_circuit * r * n / 1000.0
            loss_pct = (dp_total_kw / p_active * 100.0) if p_active > 0 else math.inf
            if max_loss_percent is not None and loss_pct > max_loss_percent:
                continue  # fails loss budget

            dv_ll = math.sqrt(3) * i_circuit * (r * cos_phi + x * sin_phi)
            vdrop_pct = dv_ll / (v_kv * 1000.0) * 100.0
            if max_vdrop_percent is not None and vdrop_pct > max_vdrop_percent:
                continue  # fails optional voltage-drop cap

            return CableSelection(
                cable=c,
                n_parallel=n,
                current_per_circuit_a=i_circuit,
                utilization=i_circuit / c.rated_current_a,
                loss_percent=loss_pct,
                vdrop_percent=vdrop_pct,
            )

    budget = "—" if max_loss_percent is None else f"{max_loss_percent:.2f}%"
    raise ValueError(
        f"No cable can carry {i_total:,.0f} A at {v_kv} kV over {length_km*1000:,.0f} m "
        f"within {max_utilization*100:.0f}% ampacity and a {budget} loss budget "
        f"(up to {max_parallel} parallel circuits). Add larger cables or relax limits."
    )


def select_cable_worst_case(
    candidates: list[Cable],
    s_kva: float,
    v_kv: float,
    cos_phi: float,
    sin_phi: float,
    max_utilization: float = 0.80,
    loss_percent: float = 1.30,
    max_parallel: int = 12,
) -> tuple[CableSelection, float]:
    """Size a cable section of UNKNOWN length, assuming the worst case: the
    section consumes its full admissible loss budget.

    Conceptual-stage (Stage 1) tool: lengths are not known yet, so instead of
    asking for one, the section's active loss is pinned at ``loss_percent`` of
    the local active power — the most conservative admissible value. The cable
    and circuit count are chosen by ampacity alone (fewest circuits, smallest
    section, as in :func:`select_cable`), and the IMPLIED length — the length
    at which that cable exactly exhausts the budget — is returned with the
    selection. Reactive series loss then follows from the cable's X/R ratio.
    """
    usable = [
        c for c in candidates
        if c.rated_current_a is not None and c.cross_section_mm2 is not None
    ]
    if not usable:
        raise ValueError(
            "No usable cables in the catalogue (need rated_current_a and "
            "cross_section_mm2) for this voltage section."
        )

    i_total = current_a(s_kva, v_kv)
    p_active = s_kva * cos_phi
    if p_active <= 0:
        raise ValueError("Worst-case cable sizing needs positive active power.")
    by_area = sorted(usable, key=lambda c: c.cross_section_mm2)

    for n in range(1, max_parallel + 1):
        i_circuit = i_total / n
        for c in by_area:
            if i_circuit > max_utilization * c.rated_current_a:
                continue  # fails ampacity

            # Implied worst-case length: dp_total = 3 I_c² r L n / 1000 kW must
            # equal the full budget loss_percent/100 * P.
            dp_total_kw = loss_percent / 100.0 * p_active
            length_km = dp_total_kw * 1000.0 / (3.0 * i_circuit * i_circuit
                                                * c.r_ohm_per_km * n)
            r = c.r_ohm_per_km * length_km
            x = c.x_ohm_per_km * length_km
            dv_ll = math.sqrt(3) * i_circuit * (r * cos_phi + x * sin_phi)
            vdrop_pct = dv_ll / (v_kv * 1000.0) * 100.0

            return (
                CableSelection(
                    cable=c,
                    n_parallel=n,
                    current_per_circuit_a=i_circuit,
                    utilization=i_circuit / c.rated_current_a,
                    loss_percent=loss_percent,
                    vdrop_percent=vdrop_pct,
                ),
                length_km,
            )

    raise ValueError(
        f"No cable can carry {i_total:,.0f} A at {v_kv} kV within "
        f"{max_utilization*100:.0f}% ampacity (up to {max_parallel} parallel "
        f"circuits). Add larger cables or relax limits."
    )
