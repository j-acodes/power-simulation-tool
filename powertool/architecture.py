"""Plant electrical architecture: organize the Stage-1 inverter power into blocks.

Stage 1 (powertool.sizing) lumps the whole plant into one MV cable and one
parallel transformer block, which oversizes cable sections — the full plant
power never flows in a single feeder. This module performs Stage 2:

  1. Count the LV/MV transformers needed to carry the required inverter power
     (user-selected model and maximum loading factor).
  2. Group them into MV collector circuits capped by a maximum current per
     circuit. The per-station current is CALCULATED from the actual MV-side
     power flow (LV share plus the transformer's own losses pushed through),
     not assumed from the nameplate.
  3. (size_architecture, added in later steps) Size every daisy-chain cable
     segment separately for the cumulative power it actually carries, recompute
     the plant losses, and refine the inverter requirement.

Conventions follow powertool.components: three-phase balanced steady-state,
line-to-line kV, P in kW / Q in kvar / S in kVA. The worst-case reactive sign
convention of the Stage-1 solver is preserved throughout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .cable_sizing import CableSelection, select_cable
from .components import Cable, Transformer, current_a
from .sizing import SizingResult, format_cable_label


@dataclass
class StationPlan:
    """Planned electrical figures for ONE MV/LV station, before cable sizing.

    Every station runs at the fleet's uniform per-unit loading, so its LV share
    of the inverter power is proportional to its rating.
    """

    transformer: Transformer
    p_lv_kw: float
    q_lv_kvar: float
    s_lv_kva: float
    p_mv_kw: float
    q_mv_kvar: float
    s_mv_kva: float
    i_a: float  # MV-side current at the layout's v_mv_kv
    loading: float  # s_lv / s_rated (uniform across the fleet)


@dataclass
class PlantLayout:
    """The arrangement decisions for the plant, before any cable is sized.

    The fleet (transformer models and counts) comes from Stage 1; the tool no
    longer invents a count. Stations are grouped into circuits respecting the
    max current per circuit; within each circuit, position 0 is NEAREST the
    substation and stations are ordered biggest-rating first — the trunk
    carries everything regardless, and keeping the big stations close to the
    busbar minimises the power flowing through the long tail segments (lowest
    cable losses).

    Lengths apply to every circuit alike: ``trunk_length_km`` from the
    substation to the first station, ``spacing_km`` between consecutive
    stations (individual runs editable later via ``segment_lengths``).
    """

    fleet: list[tuple[Transformer, int]]
    circuit_plans: list[list[StationPlan]]  # [circuit][position], 0 = nearest substation
    max_circuit_current_a: float
    trunk_length_km: float
    spacing_km: float
    v_mv_kv: float
    fleet_loading: float  # S_inv / fleet rating (uniform per-unit loading)
    loading_ok: bool  # fleet_loading <= the requested max loading

    @property
    def n_transformers(self) -> int:
        return sum(len(c) for c in self.circuit_plans)

    @property
    def s_fleet_kva(self) -> float:
        return sum(tx.s_rated_kva * n for tx, n in self.fleet)

    @property
    def circuit_sizes(self) -> list[int]:
        return [len(c) for c in self.circuit_plans]

    @property
    def n_circuits(self) -> int:
        return len(self.circuit_plans)

    @property
    def circuit_sizes_label(self) -> str:
        """e.g. ``"4 (5+5+4+4)"`` for quick display."""
        return f"{self.n_circuits} ({'+'.join(str(s) for s in self.circuit_sizes)})"


def assign_circuits(i_stations: list[float], i_max_a: float) -> list[list[int]]:
    """Group station indices into MV circuits respecting the current cap.

    Fewest circuits first (searching up from the total-current lower bound),
    then balanced: stations are placed biggest-current-first onto the
    least-loaded circuit that still fits (LPT heuristic). With identical
    stations this reproduces the balanced split (18 stations capped at 5 per
    circuit -> sizes [5, 5, 4, 4]); with a mixed fleet it balances the circuit
    currents.
    """
    if not i_stations:
        raise ValueError("Need at least one station to arrange circuits")
    if any(i <= 0 for i in i_stations):
        raise ValueError("Station currents must be positive")
    worst = max(i_stations)
    if worst > i_max_a + 1e-9:
        raise ValueError(
            f"One station alone draws {worst:,.0f} A, above the {i_max_a:,.0f} A "
            f"circuit limit. Raise the max current per circuit or pick smaller "
            f"transformers."
        )

    order = sorted(range(len(i_stations)), key=lambda i: -i_stations[i])
    lower = max(1, math.ceil(sum(i_stations) / i_max_a - 1e-9))
    for n_circuits in range(lower, len(i_stations) + 1):
        bins: list[list[int]] = [[] for _ in range(n_circuits)]
        loads = [0.0] * n_circuits
        feasible = True
        for idx in order:
            fitting = [j for j in range(n_circuits)
                       if loads[j] + i_stations[idx] <= i_max_a + 1e-9]
            if not fitting:
                feasible = False
                break
            j = min(fitting, key=lambda j: loads[j])
            bins[j].append(idx)
            loads[j] += i_stations[idx]
        if feasible:
            return [b for b in bins if b]
    raise AssertionError("unreachable: one station per circuit always fits the cap")


def station_mv_output(
    p_lv_kw: float, q_lv_kvar: float, transformer: Transformer
) -> tuple[float, float]:
    """MV-side (P [kW], Q [kvar]) out of one station for an LV-side input.

    Forward power flow through the station transformer: the losses computed at
    the LV-side apparent power are consumed en route, so
    p_mv = p_lv - dP and q_mv = q_lv - dQ. The reactive consumed by the
    transformer (uk-driven) worsens the MV-side power factor relative to the
    inverter terminals — this is why circuit currents must be computed here and
    not from the nameplate.
    """
    s_lv = math.hypot(p_lv_kw, q_lv_kvar)
    dp, dq = transformer.losses(s_lv)
    p_mv = p_lv_kw - dp
    if p_mv <= 0:
        raise ValueError(
            f"Transformer '{transformer.name}' losses ({dp:,.1f} kW) exceed the station "
            f"input ({p_lv_kw:,.1f} kW) — check the transformer data or the station share."
        )
    return p_mv, q_lv_kvar - dq


def arrange_plant(
    stage1: SizingResult,
    fleet: list[tuple[Transformer, int]],
    *,
    max_circuit_current_a: float,
    trunk_length_km: float,
    spacing_km: float,
    v_mv_kv: float,
    max_loading: float = 1.0,
) -> PlantLayout:
    """Arrange the Stage-1 station fleet into MV circuits.

    The fleet (models and counts) is given — it comes from the Stage-1 chain.
    Every station runs at the same per-unit loading r = S_inv / S_fleet, so its
    LV share of the inverter P and Q is proportional to its rating; its MV-side
    output (share minus its own transformer losses) sets its current, which
    drives the circuit grouping. Within each circuit the biggest stations sit
    nearest the substation (see PlantLayout). ``max_loading`` is a check
    threshold only: the layout is still produced when exceeded, with
    ``loading_ok = False`` so the caller can warn.
    """
    if trunk_length_km < 0 or spacing_km < 0:
        raise ValueError("Lengths must be non-negative")
    if not fleet:
        raise ValueError("The fleet needs at least one transformer model")

    s_fleet = sum(tx.s_rated_kva * n for tx, n in fleet)
    loading = stage1.s_inv_kva / s_fleet

    plans: list[StationPlan] = []
    for tx, count in fleet:
        share = tx.s_rated_kva / s_fleet
        p_lv = stage1.p_inv_kw * share
        q_lv = stage1.q_inv_kvar * share
        p_mv, q_mv = station_mv_output(p_lv, q_lv, tx)
        s_mv = math.hypot(p_mv, q_mv)
        plan = StationPlan(
            transformer=tx,
            p_lv_kw=p_lv,
            q_lv_kvar=q_lv,
            s_lv_kva=math.hypot(p_lv, q_lv),
            p_mv_kw=p_mv,
            q_mv_kvar=q_mv,
            s_mv_kva=s_mv,
            i_a=current_a(s_mv, v_mv_kv),
            loading=loading,
        )
        plans.extend([plan] * count)  # identical figures for every unit of a model

    bins = assign_circuits([p.i_a for p in plans], max_circuit_current_a)
    circuit_plans = [
        sorted((plans[i] for i in b), key=lambda p: -p.transformer.s_rated_kva)
        for b in bins
    ]
    # Deterministic display order: heaviest circuit first.
    circuit_plans.sort(key=lambda c: (-sum(p.i_a for p in c), -len(c)))

    return PlantLayout(
        fleet=fleet,
        circuit_plans=circuit_plans,
        max_circuit_current_a=max_circuit_current_a,
        trunk_length_km=trunk_length_km,
        spacing_km=spacing_km,
        v_mv_kv=v_mv_kv,
        fleet_loading=loading,
        loading_ok=loading <= max_loading + 1e-9,
    )


@dataclass
class StationResult:
    """One MV/LV station: an equal share of the Stage-1 inverter requirement.

    ``index`` is 1-based within the circuit, 1 = nearest the substation.
    """

    index: int
    p_lv_kw: float
    q_lv_kvar: float
    s_lv_kva: float
    dp_tx_kw: float
    dq_tx_kvar: float
    p_mv_kw: float
    q_mv_kvar: float
    s_mv_kva: float
    loading: float  # s_lv / s_rated
    s_rated_kva: float
    model: str  # display label, e.g. "3300 kVA - Huawei"


@dataclass
class SegmentResult:
    """One sized cable span. Within a circuit, segment 1 (the trunk) carries the
    whole circuit and the last segment carries only the far station; the same
    shape also describes the HV export cable.

    P/Q/S are taken at the sending end of the span (before its own losses),
    which is also where the span's current is highest. ``selection`` is None
    only for an HV export cable when the catalogue has no cables at the HV
    voltage yet — the span is then recorded with zero losses ("not sized").
    """

    index: int  # 1 = substation -> first station (trunk); 0 = HV export cable
    length_km: float
    p_kw: float
    q_kvar: float
    s_kva: float
    selection: CableSelection | None
    cable_label: str
    dp_kw: float
    dq_series_kvar: float
    q_charging_kvar: float


@dataclass
class CircuitResult:
    """One MV collector circuit: its stations, its sized segments, and what it
    actually delivers to the MV busbar."""

    index: int
    stations: list[StationResult]
    segments: list[SegmentResult]  # same order as stations; index 1 = trunk
    i_trunk_a: float  # current entering the trunk (the circuit's maximum)
    current_ok: bool  # i_trunk_a <= the layout's max circuit current
    p_busbar_kw: float
    q_busbar_kvar: float

    @property
    def dp_cables_kw(self) -> float:
        return sum(s.dp_kw for s in self.segments)

    @property
    def dp_transformers_kw(self) -> float:
        return sum(s.dp_tx_kw for s in self.stations)


def size_circuits(
    layout: PlantLayout,
    cable_candidates: list[Cable],
    *,
    max_utilization: float = 0.80,
    max_loss_percent_base: float = 1.30,
    max_loss_percent_per_km: float = 0.0,
    max_vdrop_percent: float | None = None,
    max_parallel: int = 12,
    segment_lengths: dict[tuple[int, int], float] | None = None,
) -> list[CircuitResult]:
    """Size every cable segment of every MV circuit in the layout.

    ``segment_lengths`` optionally overrides individual runs: keys are
    ``(circuit_index, segment_index)`` (both 1-based, segment 1 = trunk),
    values in km. Runs without an override use the layout's trunk/spacing.

    Each circuit is walked from the FAR station toward the substation,
    accumulating (P, Q): a segment carries the cumulative MV output of the
    stations behind it, minus the cable losses already consumed en route —
    this is forward power flow (inverter -> POC), the mirror image of the
    Stage-1 solver which walks POC -> inverter adding losses. Stations may be
    heterogeneous (mixed fleet); each contributes its own MV output.

    Each segment gets its own ``select_cable`` call with the LOCAL power
    factor of the accumulated flow (the station transformers consume reactive,
    so the MV-side PF is worse than at the inverter terminals). Worst-case
    reactive convention preserved: cable charging is recorded per segment but
    never netted against the series reactive.
    """
    if segment_lengths:
        for key, value in segment_lengths.items():
            if value <= 0:
                raise ValueError(f"Segment length override {key} must be positive, "
                                 f"got {value} km")

    circuits: list[CircuitResult] = []
    for c_idx, plans in enumerate(layout.circuit_plans, start=1):
        n_stations = len(plans)
        stations = [
            StationResult(
                index=k,
                p_lv_kw=plan.p_lv_kw,
                q_lv_kvar=plan.q_lv_kvar,
                s_lv_kva=plan.s_lv_kva,
                dp_tx_kw=plan.p_lv_kw - plan.p_mv_kw,
                dq_tx_kvar=plan.q_lv_kvar - plan.q_mv_kvar,
                p_mv_kw=plan.p_mv_kw,
                q_mv_kvar=plan.q_mv_kvar,
                s_mv_kva=plan.s_mv_kva,
                loading=plan.loading,
                s_rated_kva=plan.transformer.s_rated_kva,
                model=plan.transformer.display_name,
            )
            for k, plan in enumerate(plans, start=1)
        ]

        segments: list[SegmentResult] = []
        p = q = 0.0
        i_trunk_a = 0.0
        # Far station first: segment k joins station k to station k-1 (or, for
        # k = 1, to the substation), so it carries stations k..n_stations.
        for k in range(n_stations, 0, -1):
            p += plans[k - 1].p_mv_kw
            q += plans[k - 1].q_mv_kvar
            s = math.hypot(p, q)
            cos_phi = p / s if s > 0 else 1.0
            sin_phi = q / s if s > 0 else 0.0
            length_km = layout.trunk_length_km if k == 1 else layout.spacing_km
            if segment_lengths:
                length_km = segment_lengths.get((c_idx, k), length_km)

            sel = select_cable(
                cable_candidates,
                s,
                layout.v_mv_kv,
                length_km,
                cos_phi,
                sin_phi,
                max_utilization=max_utilization,
                max_loss_percent=(
                    max_loss_percent_base + max_loss_percent_per_km * length_km
                ),
                max_vdrop_percent=max_vdrop_percent,
                max_parallel=max_parallel,
            )

            # Same 1/n arithmetic as the Stage-1 solver (sizing._cable_contribution):
            # n parallel circuits share the current, so series losses scale as 1/n
            # while charging scales as n.
            dp, dq_series = sel.cable.series_losses(s, layout.v_mv_kv, length_km)
            dp /= sel.n_parallel
            dq_series /= sel.n_parallel
            q_charging = sel.cable.charging_kvar(layout.v_mv_kv, length_km) * sel.n_parallel

            segments.append(
                SegmentResult(
                    index=k,
                    length_km=length_km,
                    p_kw=p,
                    q_kvar=q,
                    s_kva=s,
                    selection=sel,
                    cable_label=format_cable_label(sel.cable, sel.n_parallel),
                    dp_kw=dp,
                    dq_series_kvar=dq_series,
                    q_charging_kvar=q_charging,
                )
            )
            if k == 1:
                i_trunk_a = current_a(s, layout.v_mv_kv)
            # Losses are consumed en route toward the substation. Charging is
            # NEVER netted in (worst-case convention, see powertool.sizing).
            p -= dp
            q -= dq_series

        segments.reverse()  # report in circuit order: 1 = trunk first
        circuits.append(
            CircuitResult(
                index=c_idx,
                stations=stations,
                segments=segments,
                i_trunk_a=i_trunk_a,
                current_ok=i_trunk_a <= layout.max_circuit_current_a + 1e-9,
                p_busbar_kw=p,
                q_busbar_kvar=q,
            )
        )
    return circuits


# IEC 60076-style preferred ratings [MVA] for the auto-sized MV/HV transformer.
_HV_RATINGS_MVA = [5, 6.3, 8, 10, 12.5, 16, 20, 25, 31.5, 40, 50, 63, 80, 100,
                   125, 160, 200, 250]


def auto_hv_transformer(s_kva: float, v_hv_kv: float, v_mv_kv: float) -> Transformer:
    """ONE MV/HV transformer auto-sized for the plant.

    Picks the smallest IEC-preferred rating that covers ``s_kva`` and builds a
    representative unit around it: uk = 12.5 %, Pk = 0.36 % and P0 = 0.06 % of
    the rating, i0 = 0.3 % — the same per-unit figures as the placeholder HV
    unit in the catalogue. When the real transformer catalogue lands, this can
    pick actual datasheet units instead.
    """
    if s_kva <= 0:
        raise ValueError(f"Apparent power must be positive, got {s_kva} kVA")
    for rating_mva in _HV_RATINGS_MVA:
        if rating_mva * 1000.0 >= s_kva:
            s_rated = rating_mva * 1000.0
            return Transformer(
                name=f"HV_{rating_mva:g}MVA_{v_hv_kv:g}_{v_mv_kv:g}kV (auto)",
                s_rated_kva=s_rated,
                uk_percent=12.5,
                pk_kw=0.0036 * s_rated,
                p0_kw=0.0006 * s_rated,
                i0_percent=0.3,
                hv_kv=v_hv_kv,
                lv_kv=v_mv_kv,
            )
    raise ValueError(
        f"Plant apparent power {s_kva / 1000:,.1f} MVA exceeds the largest "
        f"preferred single-transformer rating ({_HV_RATINGS_MVA[-1]} MVA)."
    )


def _delivered_with_frozen_cables(
    layout: PlantLayout,
    circuits: list[CircuitResult],
    export: "ExportResult | None",
    aux_p_kw: float,
    aux_q_kvar: float,
    k: float,
) -> tuple[float, float]:
    """Delivered POC (P [kW], Q [kvar]) when the inverter output is scaled by
    ``k``, keeping every cable selection FROZEN.

    Re-evaluates the forward loss cascade only — no cable re-selection — so the
    discrete picks cannot flap while the inverter refinement iterates on the
    smooth scalar ``k``.
    """
    p_total = q_total = 0.0
    for circuit, plans in zip(circuits, layout.circuit_plans):
        p = q = 0.0
        # Far station first; stations may be heterogeneous (mixed fleet).
        for seg, plan in zip(reversed(circuit.segments), reversed(plans)):
            p_mv, q_mv = station_mv_output(
                plan.p_lv_kw * k, plan.q_lv_kvar * k, plan.transformer
            )
            p += p_mv
            q += q_mv
            s = math.hypot(p, q)
            sel = seg.selection
            dp, dq = sel.cable.series_losses(s, layout.v_mv_kv, seg.length_km)
            p -= dp / sel.n_parallel
            q -= dq / sel.n_parallel
        p_total += p
        q_total += q
    p_total -= aux_p_kw
    q_total -= aux_q_kvar

    if export is not None:
        if export.hv_transformer is not None:
            s = math.hypot(p_total, q_total)
            dp_unit, dq_unit = export.hv_transformer.losses(s / export.hv_n_parallel)
            p_total -= dp_unit * export.hv_n_parallel
            q_total -= dq_unit * export.hv_n_parallel
        hv = export.hv_cable
        if hv is not None and hv.selection is not None:
            s = math.hypot(p_total, q_total)
            dp, dq = hv.selection.cable.series_losses(s, export.v_hv_kv, hv.length_km)
            p_total -= dp / hv.selection.n_parallel
            q_total -= dq / hv.selection.n_parallel
    return p_total, q_total


@dataclass
class ExportResult:
    """The busbar -> POC step: optional MV/HV transformer plus HV export cable.

    ``hv_cable`` is None when no export cable was requested (length 0);
    ``hv_cable_sized`` is False when a cable was requested but the catalogue has
    no cables at the HV voltage yet — the section is then recorded with zero
    losses and the architecture still computes through the transformer.
    """

    hv_transformer: Transformer | None
    hv_n_parallel: int
    s_tx_through_kva: float  # apparent power entering the transformer (MV side)
    dp_tx_kw: float
    dq_tx_kvar: float
    hv_cable: SegmentResult | None
    hv_cable_sized: bool
    v_hv_kv: float | None


@dataclass
class PlantArchitecture:
    """Full Stage-2 result: layout, sized circuits, export step, plant totals,
    and the refined inverter requirement.

    Refinement rule — NEVER fall short at the POC: losses grow with the square
    of load, so a single proportional correction would deliver slightly UNDER
    the target. Instead the scalar correction is iterated against the loss
    cascade with the cable selections frozen (no re-selection, so the discrete
    picks cannot flap) until the delivered POC power is >= the target.
    Overshoot is curtailable; shortfall is not acceptable.
    """

    layout: PlantLayout
    circuits: list[CircuitResult]
    export: ExportResult | None  # None = plant delivered at the MV busbar
    aux_p_kw: float
    aux_q_kvar: float
    # Delivered at the POC when the inverters produce the Stage-1 output
    p_poc_delivered_kw: float
    q_poc_delivered_kvar: float
    # Refined requirement to actually meet (never undershoot) the POC target
    p_poc_target_kw: float | None
    correction_factor: float  # 1.0 when no target was given
    p_inv_refined_kw: float
    q_inv_refined_kvar: float
    s_inv_refined_kva: float
    # POC power delivered with the refined inverter output (>= target by rule)
    p_poc_refined_delivered_kw: float | None
    power_balance_ok: bool

    @property
    def n_circuits(self) -> int:
        return len(self.circuits)

    @property
    def total_cable_loss_kw(self) -> float:
        total = sum(seg.dp_kw for c in self.circuits for seg in c.segments)
        if self.export is not None and self.export.hv_cable is not None:
            total += self.export.hv_cable.dp_kw
        return total

    @property
    def total_transformer_loss_kw(self) -> float:
        total = sum(st.dp_tx_kw for c in self.circuits for st in c.stations)
        if self.export is not None:
            total += self.export.dp_tx_kw
        return total

    @property
    def total_active_loss_kw(self) -> float:
        return self.total_cable_loss_kw + self.total_transformer_loss_kw

    @property
    def all_current_ok(self) -> bool:
        return all(c.current_ok for c in self.circuits)


def size_architecture(
    layout: PlantLayout,
    stage1: SizingResult,
    cable_candidates: list[Cable],
    *,
    max_utilization: float = 0.80,
    max_loss_percent_base: float = 1.30,
    max_loss_percent_per_km: float = 0.0,
    max_vdrop_percent: float | None = None,
    max_parallel: int = 12,
    segment_lengths: dict[tuple[int, int], float] | None = None,
    hv_transformer: Transformer | None = None,
    auto_hv: bool = False,
    hv_n_parallel: int = 1,
    hv_cable_candidates: list[Cable] | None = None,
    hv_cable_length_km: float = 0.0,
    v_hv_kv: float | None = None,
    export_loss_percent_per_km: float = 0.1,
    aux_p_kw: float = 0.0,
    aux_q_kvar: float = 0.0,
    p_poc_target_kw: float | None = None,
) -> PlantArchitecture:
    """Size the full plant architecture and recompute the delivered POC power.

    Forward power flow, inverter -> POC: MV circuits (size_circuits) deliver to
    the busbar; the aux load is taken there; then, when present, the MV/HV
    transformer and the HV export cable consume their losses on the way to the
    POC. HV-side parameters are all optional — without them the plant is
    delivered at the MV busbar (MV interconnection).

    ``auto_hv=True`` sizes ONE MV/HV transformer automatically from the plant
    power and ``v_hv_kv`` (see :func:`auto_hv_transformer`) instead of taking
    a user-selected model.

    When ``p_poc_target_kw`` is given, the refined inverter requirement is the
    Stage-1 output scaled so the delivered POC power lands AT OR ABOVE the
    target — never below (see PlantArchitecture).
    """
    circuits = size_circuits(
        layout,
        cable_candidates,
        max_utilization=max_utilization,
        max_loss_percent_base=max_loss_percent_base,
        max_loss_percent_per_km=max_loss_percent_per_km,
        max_vdrop_percent=max_vdrop_percent,
        max_parallel=max_parallel,
        segment_lengths=segment_lengths,
    )

    p = sum(c.p_busbar_kw for c in circuits)
    q = sum(c.q_busbar_kvar for c in circuits)
    p -= aux_p_kw
    q -= aux_q_kvar

    if auto_hv:
        if v_hv_kv is None:
            raise ValueError("auto_hv requires v_hv_kv (the HV interconnection voltage).")
        hv_transformer = auto_hv_transformer(math.hypot(p, q), v_hv_kv, layout.v_mv_kv)
        hv_n_parallel = 1

    export: ExportResult | None = None
    if hv_transformer is not None or hv_cable_length_km > 0:
        # MV/HV transformer step (same n-parallel arithmetic as the Stage-1
        # solver: each unit carries S/n, losses summed over the n units).
        dp_tx = dq_tx = 0.0
        s_tx = math.hypot(p, q)
        if hv_transformer is not None:
            if hv_n_parallel < 1:
                raise ValueError(f"hv_n_parallel must be >= 1, got {hv_n_parallel}")
            dp_unit, dq_unit = hv_transformer.losses(s_tx / hv_n_parallel)
            dp_tx = dp_unit * hv_n_parallel
            dq_tx = dq_unit * hv_n_parallel
            p -= dp_tx
            q -= dq_tx

        # HV export cable step, at the HV voltage.
        hv_cable: SegmentResult | None = None
        hv_cable_sized = False
        v_hv = v_hv_kv if v_hv_kv is not None else (
            hv_transformer.hv_kv if hv_transformer is not None else None
        )
        if hv_cable_length_km > 0:
            if v_hv is None:
                raise ValueError(
                    "An HV export cable needs its voltage: set v_hv_kv or use an "
                    "MV/HV transformer with hv_kv defined."
                )
            s = math.hypot(p, q)
            candidates = hv_cable_candidates or []
            if candidates:
                cos_phi = p / s if s > 0 else 1.0
                sin_phi = q / s if s > 0 else 0.0
                sel = select_cable(
                    candidates,
                    s,
                    v_hv,
                    hv_cable_length_km,
                    cos_phi,
                    sin_phi,
                    max_utilization=max_utilization,
                    max_loss_percent=export_loss_percent_per_km * hv_cable_length_km,
                    max_vdrop_percent=max_vdrop_percent,
                    max_parallel=max_parallel,
                )
                dp, dq_series = sel.cable.series_losses(s, v_hv, hv_cable_length_km)
                dp /= sel.n_parallel
                dq_series /= sel.n_parallel
                q_charging = sel.cable.charging_kvar(v_hv, hv_cable_length_km) * sel.n_parallel
                hv_cable = SegmentResult(
                    index=0,
                    length_km=hv_cable_length_km,
                    p_kw=p,
                    q_kvar=q,
                    s_kva=s,
                    selection=sel,
                    cable_label=format_cable_label(sel.cable, sel.n_parallel),
                    dp_kw=dp,
                    dq_series_kvar=dq_series,
                    q_charging_kvar=q_charging,
                )
                hv_cable_sized = True
                p -= dp
                q -= dq_series
            else:
                # Catalogue has no cables at this voltage yet: record the span
                # unsized with zero losses so the rest still computes.
                hv_cable = SegmentResult(
                    index=0,
                    length_km=hv_cable_length_km,
                    p_kw=p,
                    q_kvar=q,
                    s_kva=s,
                    selection=None,
                    cable_label="HV cable (not sized — catalogue pending)",
                    dp_kw=0.0,
                    dq_series_kvar=0.0,
                    q_charging_kvar=0.0,
                )

        export = ExportResult(
            hv_transformer=hv_transformer,
            hv_n_parallel=hv_n_parallel,
            s_tx_through_kva=s_tx,
            dp_tx_kw=dp_tx,
            dq_tx_kvar=dq_tx,
            hv_cable=hv_cable,
            hv_cable_sized=hv_cable_sized,
            v_hv_kv=v_hv,
        )

    # Refined inverter requirement — never fall short at the POC (see
    # PlantArchitecture): iterate the scalar correction against the frozen-cable
    # cascade until the delivered power is at or above the target.
    correction = 1.0
    p_refined_delivered: float | None = None
    if p_poc_target_kw is not None:
        if p <= 0:
            raise ValueError(
                "Nothing delivered at the POC — losses and aux consume the whole "
                "plant output; check the inputs."
            )
        correction = p_poc_target_kw / p
        for _ in range(50):  # geometric convergence; a handful suffice
            p_refined_delivered, _ = _delivered_with_frozen_cables(
                layout, circuits, export, aux_p_kw, aux_q_kvar, correction
            )
            if p_refined_delivered >= p_poc_target_kw:
                break
            correction *= p_poc_target_kw / p_refined_delivered
    p_inv_refined = stage1.p_inv_kw * correction
    q_inv_refined = stage1.q_inv_kvar * correction

    # Conservation check, same spirit as the Stage-1 solver: everything the
    # stations take in at LV must come out at the POC or be consumed en route.
    p_in = sum(st.p_lv_kw for c in circuits for st in c.stations)
    consumed = (
        sum(st.dp_tx_kw for c in circuits for st in c.stations)
        + sum(seg.dp_kw for c in circuits for seg in c.segments)
        + aux_p_kw
        + (export.dp_tx_kw if export is not None else 0.0)
        + (export.hv_cable.dp_kw if export is not None and export.hv_cable else 0.0)
    )
    balance_ok = math.isclose(p_in, p + consumed, rel_tol=1e-6)

    return PlantArchitecture(
        layout=layout,
        circuits=circuits,
        export=export,
        aux_p_kw=aux_p_kw,
        aux_q_kvar=aux_q_kvar,
        p_poc_delivered_kw=p,
        q_poc_delivered_kvar=q,
        p_poc_target_kw=p_poc_target_kw,
        correction_factor=correction,
        p_inv_refined_kw=p_inv_refined,
        q_inv_refined_kvar=q_inv_refined,
        s_inv_refined_kva=math.hypot(p_inv_refined, q_inv_refined),
        p_poc_refined_delivered_kw=p_refined_delivered,
        power_balance_ok=balance_ok,
    )
