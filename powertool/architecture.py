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
    v_lv_kv: float  # the station's own transformer LV rating
    kind: str = "pv"  # fleet kind ("pv" or "bess"); see powertool.graph


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
    kind: str = "pv",
) -> PlantLayout:
    """Arrange the Stage-1 station fleet into MV circuits.

    The fleet (models and counts) is given — it comes from the Stage-1 chain.
    Every station runs at the same per-unit loading r = S_inv / S_fleet, so its
    LV share of the inverter P and Q is proportional to its rating; its MV-side
    output (share minus its own transformer losses) sets its current, which
    drives the circuit grouping. Within each circuit the biggest stations sit
    nearest the substation (see PlantLayout). ``max_loading`` is a check
    threshold only: the layout is still produced when exceeded, with
    ``loading_ok = False`` so the caller can warn. ``kind`` (fleet kind, "pv"
    or "bess") is stamped on every station plan built here — see
    ``StationPlan.kind``.
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
            v_lv_kv=tx.lv_kv if tx.lv_kv is not None else 0.0,
            kind=kind,
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


def arrange_plant_manual(
    stage1: SizingResult,
    circuits: list[list[Transformer]],
    *,
    max_circuit_current_a: float,
    v_mv_kv: float,
    max_loading: float = 1.0,
    kind: str = "pv",
) -> PlantLayout:
    """Arrange the plant from a DRAWN circuit layout — the given order is kept.

    Same per-station physics as :func:`arrange_plant`: every station runs at the
    fleet's uniform per-unit loading r = S_inv / S_fleet, so its LV share of the
    inverter P and Q is proportional to its OWN rating, and its MV-side output
    (that share minus its own transformer losses, see
    :func:`station_mv_output`) sets its current. What is dropped is all the
    planning: no circuit assignment, no sorting by rating, no reordering of the
    circuits. ``circuits[c][k]`` becomes ``circuit_plans[c][k]`` verbatim, with
    position 0 nearest the substation — the user drew the plant, the engine only
    computes it.

    That positional stability is a hard invariant, not a convenience: the caller
    maps every result back to a canvas element by (circuit index, position), so
    no engine-side identifier is needed. Reordering here would silently mislabel
    every cable and station on the drawing.

    Nothing raises when the drawing exceeds a limit: a circuit above the current
    cap is flagged downstream by ``CircuitResult.current_ok`` and an undersized
    fleet by ``loading_ok``. ``max_loading`` is a check threshold only, exactly
    as in :func:`arrange_plant`.

    ``trunk_length_km`` / ``spacing_km`` are meaningless for a drawn plant (each
    run has its own length) and are set to a 1.0 km PLACEHOLDER. Callers must
    therefore pass a COMPLETE ``segment_lengths`` mapping to
    :func:`size_circuits` / :func:`size_architecture` — any run left out would
    silently fall back to that placeholder.

    ``kind`` (fleet kind, "pv" or "bess") is stamped on every station plan
    built here — see ``StationPlan.kind``.
    """
    if not circuits:
        raise ValueError("Need at least one MV circuit to arrange the plant")
    for i, circuit in enumerate(circuits, start=1):
        if not circuit:
            raise ValueError(f"Circuit {i} has no stations — every drawn circuit "
                             f"needs at least one MV/LV station")

    stations = [tx for circuit in circuits for tx in circuit]
    s_fleet = sum(tx.s_rated_kva for tx in stations)
    loading = stage1.s_inv_kva / s_fleet

    # Fleet = (model, count) aggregated over the drawn stations, in order of
    # first appearance; identical models drawn apart still merge into one entry.
    fleet: list[tuple[Transformer, int]] = []
    for tx in stations:
        for i, (known, count) in enumerate(fleet):
            if known == tx:
                fleet[i] = (known, count + 1)
                break
        else:
            fleet.append((tx, 1))

    def _plan(tx: Transformer) -> StationPlan:
        share = tx.s_rated_kva / s_fleet
        p_lv = stage1.p_inv_kw * share
        q_lv = stage1.q_inv_kvar * share
        p_mv, q_mv = station_mv_output(p_lv, q_lv, tx)
        s_mv = math.hypot(p_mv, q_mv)
        return StationPlan(
            transformer=tx,
            p_lv_kw=p_lv,
            q_lv_kvar=q_lv,
            s_lv_kva=math.hypot(p_lv, q_lv),
            p_mv_kw=p_mv,
            q_mv_kvar=q_mv,
            s_mv_kva=s_mv,
            i_a=current_a(s_mv, v_mv_kv),
            loading=loading,
            v_lv_kv=tx.lv_kv if tx.lv_kv is not None else 0.0,
            kind=kind,
        )

    return PlantLayout(
        fleet=fleet,
        circuit_plans=[[_plan(tx) for tx in circuit] for circuit in circuits],
        max_circuit_current_a=max_circuit_current_a,
        trunk_length_km=1.0,  # placeholder: drawn plants pass segment_lengths
        spacing_km=1.0,
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
    v_lv_kv: float  # the station's own transformer LV rating
    kind: str = "pv"  # fleet kind ("pv" or "bess"); see powertool.graph


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
    segment_candidates: dict[tuple[int, int], list[Cable]] | None = None,
) -> list[CircuitResult]:
    """Size every cable segment of every MV circuit in the layout.

    ``segment_lengths`` optionally overrides individual runs: keys are
    ``(circuit_index, segment_index)`` (both 1-based, segment 1 = trunk),
    values in km. Runs without an override use the layout's trunk/spacing.

    ``segment_candidates`` optionally narrows the catalogue offered to
    individual runs, keyed the same way: a one-element list FORCES that section
    (the user picked the cable on the drawing), while the parallel-circuit
    escalation still applies. A forced cable that cannot carry the flow within
    the ampacity and loss budgets raises the descriptive ``ValueError`` of
    :func:`select_cable` — a forced section is never silently replaced.

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
                v_lv_kv=plan.v_lv_kv,
                kind=plan.kind,
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

            candidates = cable_candidates
            if segment_candidates:
                candidates = segment_candidates.get((c_idx, k), cable_candidates)

            sel = select_cable(
                candidates,
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


@dataclass
class BranchArchitecture:
    """One branch's (one fleet's) sized MV circuits and its busbar totals,
    before the shared plant-level export step.

    ``p_busbar_kw`` / ``q_busbar_kvar`` are what this branch contributes to
    the shared MV/HV bus: every circuit's delivery to the busbar, less this
    branch's own auxiliary load (auxiliary load is a per-busbar figure — see
    the Auxiliary load entry in CONTEXT.md — so it is taken out here, at the
    branch level, never inflating a station's own sizing).
    """

    layout: PlantLayout
    circuits: list[CircuitResult]
    aux_p_kw: float
    aux_q_kvar: float

    @property
    def p_busbar_kw(self) -> float:
        return sum(c.p_busbar_kw for c in self.circuits) - self.aux_p_kw

    @property
    def q_busbar_kvar(self) -> float:
        return sum(c.q_busbar_kvar for c in self.circuits) - self.aux_q_kvar


def size_branch(
    layout: PlantLayout,
    cable_candidates: list[Cable],
    *,
    max_utilization: float = 0.80,
    max_loss_percent_base: float = 1.30,
    max_loss_percent_per_km: float = 0.0,
    max_vdrop_percent: float | None = None,
    max_parallel: int = 12,
    segment_lengths: dict[tuple[int, int], float] | None = None,
    segment_candidates: dict[tuple[int, int], list[Cable]] | None = None,
    aux_p_kw: float = 0.0,
    aux_q_kvar: float = 0.0,
) -> BranchArchitecture:
    """Size one branch's (one fleet's) MV circuits — the per-branch half of
    Stage 2. See :func:`size_plant` for the plant-level half that sizes the
    shared HV transformer and export cable once, on the combined result of
    every branch.
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
        segment_candidates=segment_candidates,
    )
    return BranchArchitecture(
        layout=layout,
        circuits=circuits,
        aux_p_kw=aux_p_kw,
        aux_q_kvar=aux_q_kvar,
    )


def _delivered_with_frozen_cables(
    branches: list[BranchArchitecture],
    export: "ExportResult | None",
    k: list[float],
) -> tuple[float, float, list[float]]:
    """Delivered POC (P [kW], Q [kvar], per-branch P [kW]) when each branch's
    collection output is scaled by its own ``k[i]``, keeping every cable
    selection FROZEN.

    Re-evaluates the forward loss cascade only — no cable re-selection — so
    the discrete picks cannot flap while the correction scalars iterate.
    Each branch's own aux load is subtracted at its own busbar; the branch
    totals are then summed at the shared bus, and the export step (shared HV
    transformer, then HV cable) is applied ONCE.

    The third return value attributes that ONE shared export step back to
    each branch, pro-rata by its own contribution to the busbar — the
    ticket-05 decision that each branch's own point-of-connection compliance
    is judged on its own delivered figure, not the plant aggregate:

        p_delivered_i = p_busbar_i * (p_total_after_export / p_total_before_export)

    which is exactly a uniform scaling, since the export step (a transformer
    plus a cable) treats every kW arriving at the shared bus identically —
    it cannot tell which branch a kW came from. With no export step (export
    is None or contributes nothing) ``p_delivered_i == p_busbar_i``. The
    ratio is guarded when the pre-export total is zero or non-positive
    (nothing to attribute a share of).
    """
    if len(k) != len(branches):
        raise ValueError(
            f"Need one correction scalar per branch, got {len(k)} for "
            f"{len(branches)} branches."
        )
    p_branches: list[float] = []
    p_total = q_total = 0.0
    for branch, k_i in zip(branches, k):
        p_branch = q_branch = 0.0
        for circuit, plans in zip(branch.circuits, branch.layout.circuit_plans):
            p = q = 0.0
            # Far station first; stations may be heterogeneous (mixed fleet).
            for seg, plan in zip(reversed(circuit.segments), reversed(plans)):
                p_mv, q_mv = station_mv_output(
                    plan.p_lv_kw * k_i, plan.q_lv_kvar * k_i, plan.transformer
                )
                p += p_mv
                q += q_mv
                s = math.hypot(p, q)
                sel = seg.selection
                dp, dq = sel.cable.series_losses(s, branch.layout.v_mv_kv, seg.length_km)
                p -= dp / sel.n_parallel
                q -= dq / sel.n_parallel
            p_branch += p
            q_branch += q
        p_branch -= branch.aux_p_kw
        q_branch -= branch.aux_q_kvar
        p_branches.append(p_branch)
        p_total += p_branch
        q_total += q_branch

    p_total_before_export = p_total

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

    if p_total_before_export > 0:
        export_ratio = p_total / p_total_before_export
        p_delivered_per_branch = [p_i * export_ratio for p_i in p_branches]
    else:
        p_delivered_per_branch = list(p_branches)

    return p_total, q_total, p_delivered_per_branch


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
class BranchRefinement:
    """One branch's own refined requirement — ticket-05: two fleets' refined
    inverter/PCS requirements are two different numbers, not one plant-wide
    figure split after the fact.

    ``p_poc_delivered_kw`` is this branch's UNREFINED delivered figure (its
    busbar contribution pro-rated through the shared export step, see
    :func:`_delivered_with_frozen_cables`); ``p_poc_refined_delivered_kw`` is
    the same figure once this branch's own ``correction_factor`` has been
    applied — None when no target was given for this branch (correction
    stays 1.0 and nothing was refined).
    """

    p_poc_target_kw: float | None
    p_poc_delivered_kw: float
    correction_factor: float  # 1.0 when no target was given for this branch
    p_inv_refined_kw: float
    q_inv_refined_kvar: float
    s_inv_refined_kva: float
    p_poc_refined_delivered_kw: float | None


@dataclass
class PlantArchitecture:
    """Full Stage-2 result: every branch, the shared export step, plant
    totals, and each branch's own refined requirement.

    Refinement rule — NEVER fall short at the POC, per branch: losses grow
    with the square of load, so a single proportional correction would
    deliver slightly UNDER the target. Instead each branch's own scalar
    correction is iterated together against the loss cascade with the cable
    selections frozen (no re-selection, so the discrete picks cannot flap)
    until EVERY branch's own delivered POC power is >= its own target.
    Overshoot is curtailable; shortfall is not acceptable, and it is judged
    branch by branch, not on the plant aggregate (see ``branch_refinements``
    and the ticket-05 decision recorded in
    :func:`_delivered_with_frozen_cables`).

    ``layout``, ``circuits``, ``aux_p_kw``, ``aux_q_kvar``,
    ``correction_factor``, ``p_inv_refined_kw``, ``q_inv_refined_kvar``,
    ``s_inv_refined_kva``, ``p_poc_refined_delivered_kw`` and
    ``p_poc_target_kw`` are single-branch compatibility properties,
    delegating to the sole branch / its sole refinement — every design today
    has exactly one branch. They exist so the reporting, PDF and
    result-mapping layers keep compiling unchanged; a design with more than
    one branch is not produced yet (see ``branches``). Ticket 09 deletes
    these.
    """

    branches: list[BranchArchitecture]
    export: ExportResult | None  # None = plant delivered at the MV busbar
    # Delivered at the POC when the inverters produce the Stage-1 output
    p_poc_delivered_kw: float
    q_poc_delivered_kvar: float
    # Each branch's own refined requirement, same order as `branches`.
    branch_refinements: list[BranchRefinement]
    power_balance_ok: bool

    @property
    def _sole_branch(self) -> BranchArchitecture:
        """The only branch, for the single-fleet compatibility properties.

        Raises rather than quietly preferring the first: these properties mean
        "the plant's layout", "the plant's circuits", and once a second branch
        exists there is no such thing. A caller still reading them then would
        otherwise get one fleet's figures presented as the whole plant — a
        wrong answer that looks entirely reasonable. Ticket 09 deletes these.
        """
        if len(self.branches) != 1:
            raise ValueError(
                f"This is a single-fleet accessor, but the plant has "
                f"{len(self.branches)} branches. Read `branches` instead."
            )
        return self.branches[0]

    @property
    def _sole_refinement(self) -> BranchRefinement:
        """The only branch's refinement — same rationale as ``_sole_branch``."""
        if len(self.branch_refinements) != 1:
            raise ValueError(
                f"This is a single-fleet accessor, but the plant has "
                f"{len(self.branch_refinements)} branches. Read "
                f"`branch_refinements` instead."
            )
        return self.branch_refinements[0]

    @property
    def layout(self) -> PlantLayout:
        return self._sole_branch.layout

    @property
    def circuits(self) -> list[CircuitResult]:
        return self._sole_branch.circuits

    @property
    def aux_p_kw(self) -> float:
        return self._sole_branch.aux_p_kw

    @property
    def aux_q_kvar(self) -> float:
        return self._sole_branch.aux_q_kvar

    @property
    def p_poc_target_kw(self) -> float | None:
        return self._sole_refinement.p_poc_target_kw

    @property
    def correction_factor(self) -> float:
        return self._sole_refinement.correction_factor

    @property
    def p_inv_refined_kw(self) -> float:
        return self._sole_refinement.p_inv_refined_kw

    @property
    def q_inv_refined_kvar(self) -> float:
        return self._sole_refinement.q_inv_refined_kvar

    @property
    def s_inv_refined_kva(self) -> float:
        return self._sole_refinement.s_inv_refined_kva

    @property
    def p_poc_refined_delivered_kw(self) -> float | None:
        return self._sole_refinement.p_poc_refined_delivered_kw

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


_MAX_REFINE_ITERATIONS = 50  # geometric convergence; a handful of passes suffice


def size_plant(
    branches: list[BranchArchitecture],
    stage1s: list[SizingResult],
    *,
    max_utilization: float = 0.80,
    max_vdrop_percent: float | None = None,
    max_parallel: int = 12,
    hv_transformer: Transformer | None = None,
    auto_hv: bool = False,
    hv_n_parallel: int = 1,
    hv_cable_candidates: list[Cable] | None = None,
    hv_cable_length_km: float = 0.0,
    v_hv_kv: float | None = None,
    export_loss_percent_per_km: float = 0.1,
    p_poc_targets_kw: list[float] | None = None,
) -> PlantArchitecture:
    """Size the shared HV transformer and export cable ONCE, on the combined
    result of every already-sized branch — the plant-level half of Stage 2.

    Forward power flow, busbar -> POC: every branch's busbar total (already
    net of its own aux load, see :class:`BranchArchitecture`) is summed at the
    shared bus; then, when present, the MV/HV transformer and the HV export
    cable consume their losses on the way to the POC. HV-side parameters are
    all optional — without them the plant is delivered at the shared MV bus
    (MV interconnection).

    ``stage1s`` and ``p_poc_targets_kw`` (when given) carry ONE entry per
    branch, same order as ``branches`` — mismatched lengths raise.

    ``auto_hv=True`` sizes ONE MV/HV transformer automatically from the plant
    power and ``v_hv_kv`` (see :func:`auto_hv_transformer`) instead of taking
    a user-selected model.

    Refinement is genuinely per branch (the ticket-05 decision): each fleet
    complies with the point of connection independently. The shared HV
    transformer and HV line losses are applied on the combined flow and
    attributed back to each branch pro-rata by its busbar contribution (see
    :func:`_delivered_with_frozen_cables`), so each branch's own correction
    scalar is driven by that branch's OWN target — a lossier fleet cannot
    hide behind a lighter one meeting the combined figure. Each branch's
    scalar is seeded from its unrefined delivered figure and then iterated,
    together, against the frozen-cable cascade (no cable re-selection, so the
    discrete picks cannot flap) until EVERY branch's own delivered POC power
    is at or above its own target — overshoot is curtailable, shortfall is
    not. A branch with no target keeps ``correction_factor == 1.0`` and never
    blocks the others' convergence. If the cap of
    :data:`_MAX_REFINE_ITERATIONS` passes is exhausted with any branch still
    short, this raises ``ValueError`` naming the branch and the shortfall
    rather than returning a plausible-looking number.
    """
    if len(stage1s) != len(branches):
        raise ValueError(
            f"Need one Stage-1 result per branch, got {len(stage1s)} for "
            f"{len(branches)} branches."
        )
    if p_poc_targets_kw is not None and len(p_poc_targets_kw) != len(branches):
        raise ValueError(
            f"Need one POC target per branch (or None for the plant call), "
            f"got {len(p_poc_targets_kw)} for {len(branches)} branches."
        )

    p = sum(b.p_busbar_kw for b in branches)
    q = sum(b.q_busbar_kvar for b in branches)

    if auto_hv:
        if v_hv_kv is None:
            raise ValueError("auto_hv requires v_hv_kv (the HV interconnection voltage).")
        mv_voltages = {b.layout.v_mv_kv for b in branches}
        if len(mv_voltages) > 1:
            raise ValueError(
                f"One shared MV/HV transformer cannot serve branches at "
                f"different MV voltages: {sorted(mv_voltages)}."
            )
        v_mv_kv = branches[0].layout.v_mv_kv
        hv_transformer = auto_hv_transformer(math.hypot(p, q), v_hv_kv, v_mv_kv)
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

    # Refined requirement, per branch — never fall short at the POC (see
    # PlantArchitecture): each branch's own scalar correction is iterated,
    # together, against the frozen-cable cascade until EVERY branch's own
    # delivered POC power is at or above its own target (ticket-05: each
    # fleet complies with the POC independently — see the module docstring
    # of :func:`_delivered_with_frozen_cables` for the attribution rule).
    targets: list[float | None] = (
        list(p_poc_targets_kw) if p_poc_targets_kw is not None else [None] * len(branches)
    )

    # Unrefined per-branch delivered figures (k=1 for everyone): each
    # branch's busbar contribution pro-rated through the ONE shared export
    # step. Always computed — it seeds the per-branch scalars below and is
    # reported on every branch's refinement, refined or not.
    _, _, p_delivered_unrefined = _delivered_with_frozen_cables(
        branches, export, [1.0] * len(branches)
    )

    k = [1.0] * len(branches)
    for i, (target_i, delivered_i) in enumerate(zip(targets, p_delivered_unrefined)):
        if target_i is None:
            continue
        if delivered_i <= 0:
            raise ValueError(
                f"Nothing delivered at branch {i + 1}'s point of connection — "
                f"losses and aux consume the whole branch output; check the "
                f"inputs."
            )
        k[i] = target_i / delivered_i

    p_refined_delivered_per_branch = p_delivered_unrefined
    if any(t is not None for t in targets):
        shortfalls: list[tuple[int, float, float]] = []
        for _ in range(_MAX_REFINE_ITERATIONS):  # geometric convergence; a handful suffice
            _, _, p_refined_delivered_per_branch = _delivered_with_frozen_cables(
                branches, export, k
            )
            shortfalls = [
                (i, target_i, delivered_i)
                for i, (target_i, delivered_i) in enumerate(
                    zip(targets, p_refined_delivered_per_branch)
                )
                if target_i is not None and delivered_i < target_i
            ]
            if not shortfalls:
                break
            for i, target_i, delivered_i in shortfalls:
                k[i] *= target_i / delivered_i
        else:
            i, target_i, delivered_i = shortfalls[0]
            raise ValueError(
                f"Loss refinement did not converge within "
                f"{_MAX_REFINE_ITERATIONS} iterations (branch {i + 1} delivers "
                f"{delivered_i:,.1f} kW against a {target_i:,.1f} kW target). "
                f"Check the export losses and the auxiliary load."
            )

    branch_refinements = [
        BranchRefinement(
            p_poc_target_kw=target_i,
            p_poc_delivered_kw=p_delivered_unrefined[i],
            correction_factor=k[i],
            p_inv_refined_kw=stage1s[i].p_inv_kw * k[i],
            q_inv_refined_kvar=stage1s[i].q_inv_kvar * k[i],
            s_inv_refined_kva=math.hypot(
                stage1s[i].p_inv_kw * k[i], stage1s[i].q_inv_kvar * k[i]
            ),
            p_poc_refined_delivered_kw=(
                p_refined_delivered_per_branch[i] if target_i is not None else None
            ),
        )
        for i, target_i in enumerate(targets)
    ]

    # Conservation check, same spirit as the Stage-1 solver: everything the
    # stations take in at LV must come out at the POC or be consumed en route.
    p_in = sum(st.p_lv_kw for b in branches for c in b.circuits for st in c.stations)
    consumed = (
        sum(st.dp_tx_kw for b in branches for c in b.circuits for st in c.stations)
        + sum(seg.dp_kw for b in branches for c in b.circuits for seg in c.segments)
        + sum(b.aux_p_kw for b in branches)
        + (export.dp_tx_kw if export is not None else 0.0)
        + (export.hv_cable.dp_kw if export is not None and export.hv_cable else 0.0)
    )
    balance_ok = math.isclose(p_in, p + consumed, rel_tol=1e-6)

    return PlantArchitecture(
        branches=branches,
        export=export,
        p_poc_delivered_kw=p,
        q_poc_delivered_kvar=q,
        branch_refinements=branch_refinements,
        power_balance_ok=balance_ok,
    )


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
    segment_candidates: dict[tuple[int, int], list[Cable]] | None = None,
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

    The single-branch entry point, kept so every existing caller works
    unchanged: sizes one branch's MV circuits (:func:`size_branch`) and then
    the shared HV transformer and export cable (:func:`size_plant`) on that one
    branch's result. Callers that need more than one branch call the two halves
    directly; this shim goes when the last single-branch caller does. ``segment_lengths`` and
    ``segment_candidates`` are passed straight through to
    :func:`size_circuits` (per-run lengths and per-run forced sections).
    """
    branch = size_branch(
        layout,
        cable_candidates,
        max_utilization=max_utilization,
        max_loss_percent_base=max_loss_percent_base,
        max_loss_percent_per_km=max_loss_percent_per_km,
        max_vdrop_percent=max_vdrop_percent,
        max_parallel=max_parallel,
        segment_lengths=segment_lengths,
        segment_candidates=segment_candidates,
        aux_p_kw=aux_p_kw,
        aux_q_kvar=aux_q_kvar,
    )
    return size_plant(
        [branch],
        [stage1],
        max_utilization=max_utilization,
        max_vdrop_percent=max_vdrop_percent,
        max_parallel=max_parallel,
        hv_transformer=hv_transformer,
        auto_hv=auto_hv,
        hv_n_parallel=hv_n_parallel,
        hv_cable_candidates=hv_cable_candidates,
        hv_cable_length_km=hv_cable_length_km,
        v_hv_kv=v_hv_kv,
        export_loss_percent_per_km=export_loss_percent_per_km,
        p_poc_targets_kw=(
            [p_poc_target_kw] if p_poc_target_kw is not None else None
        ),
    )
