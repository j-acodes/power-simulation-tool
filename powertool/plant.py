"""Solve a drawn plant: canvas inputs -> Stage-1 chains -> manual arrangement
-> sized architecture.

Pure engine code (moved from ``backend/solve.py`` so engine modules such as
:mod:`powertool.efficiency` can solve a design without depending on the web
adapter, which re-exports these names unchanged).
"""

from __future__ import annotations

import math

from .architecture import (BusbarSection, arrange_plant_manual, auto_hv_transformer,
                           size_branch, size_plant)
from .cable_sizing import AutoCable
from .chain import Chain, ChainElement
from .components import AuxLoad, TransformerGroup
from .database import ComponentDatabase
from .graph import BranchInputs, GraphInputs
from .sizing import size_generation, size_generation_pq

# ---------------------------------------------------------------------------
# Diagram solve: canvas -> Stage-1 chain -> manual arrangement -> architecture.
# ---------------------------------------------------------------------------

def _uses_shared_export(inputs: GraphInputs) -> bool:
    """Whether the single shared export step owns the POC run — an HV
    interconnection (one physical line after the shared transformer,
    whatever the fleet count), or an MV interconnection with only ONE busbar
    drawn on the WHOLE PLANT (``n_busbars``, not ``len(branches)``: a single
    fleet may itself hold more than one busbar since ticket 05, in which case
    each busbar sizes its own MV export run instead — see
    ``mv_export_applicable`` in :func:`powertool.graph.graph_to_inputs`, this
    rule's exact complement)."""
    return inputs.hv_tx_id is not None or inputs.n_busbars <= 1


def build_export_chain(inputs: GraphInputs, db: ComponentDatabase) -> Chain:
    """The Stage-1 chain shared by every branch: the POC down to the shared MV
    bus.

    Same recipe as the export half of the old ``build_diagram_chain`` (see
    :func:`build_chain`, which carries the rationale both inherited from the
    deleted Streamlit UI): the export cable (real drawn length, export %/km
    budget — or, for an MV interconnection with no drawn run, the worst-case
    MV busbar -> POC cable) and the MV/HV transformer, when present. What used
    to follow — the MV collection section, the station fleet, the aux load —
    is now each branch's OWN chain (:func:`build_collection_chain`): those
    figures differ per fleet, this one is sized once on the combined flow.

    Stage 1 is deliberately conceptual here too: the export run's length is
    real but the transformer sizing (when ``auto``) is conceptual, sized off
    the combined POC apparent power; Stage 2 (:func:`solve_architecture`)
    re-sizes the real HV cable and transformer from the actual combined
    busbar power.
    """
    v_export_kv = inputs.v_hv_kv if inputs.hv_mode != "none" else inputs.v_mv_kv
    export_candidates = (
        [inputs.export_cable] if inputs.export_cable is not None
        else db.cables_for_voltage(v_export_kv)
    )

    elements: list[ChainElement] = []
    if _uses_shared_export(inputs) and inputs.export_length_km > 0:
        if export_candidates:
            auto = AutoCable(candidates=export_candidates,
                             max_utilization=inputs.max_utilization,
                             max_loss_percent_base=0.0,
                             max_loss_percent_per_km=inputs.export_loss_pct_per_km,
                             name="Export cable")
            elements.append(ChainElement(auto, v_kv=v_export_kv,
                                         length_km=inputs.export_length_km,
                                         label="Export cable"))
    elif inputs.hv_mode == "none" and export_candidates:
        # MV interconnection drawn with no length: the busbar -> POC cable is
        # still sized at the worst case, so its losses are not silently ignored.
        auto = AutoCable(candidates=export_candidates,
                         max_utilization=inputs.max_utilization,
                         max_loss_percent_base=inputs.collection_loss_pct,
                         name="MV interconnection cable")
        elements.append(ChainElement(auto, v_kv=v_export_kv,
                                     label="MV interconnection cable"))

    if inputs.hv_mode == "auto":
        # Conceptual auto-sizing from the COMBINED POC apparent power; Stage 2
        # re-sizes it precisely from the actual combined busbar power.
        hv_tx = auto_hv_transformer(inputs.p_poc_kw / inputs.pf_target,
                                    inputs.v_hv_kv, inputs.v_mv_kv)
        elements.append(ChainElement(hv_tx, v_kv=inputs.v_hv_kv,
                                     label="MV/HV transformer (auto)"))
    elif inputs.hv_transformer is not None:
        elements.append(ChainElement(inputs.hv_transformer, v_kv=inputs.v_hv_kv,
                                     n_parallel=inputs.hv_n_parallel,
                                     label="MV/HV transformer"))

    return Chain(elements, name="export chain")


def build_collection_chain(inputs: GraphInputs, branch: BranchInputs,
                           db: ComponentDatabase) -> Chain:
    """One branch's own Stage-1 chain: below the shared MV bus, everything is
    this fleet's own — its MV collection section, ONE ``TransformerGroup``
    holding every drawn station of this branch (they are in parallel, so they
    SHARE the branch power — cascading them would multiply the losses), and
    this branch's own lumped aux load.

    Individual run lengths are ignored here too (the collection section takes
    its full loss budget): Stage 2 re-sizes every drawn segment of this branch
    with its real length via :func:`powertool.architecture.size_branch`.
    """
    elements: list[ChainElement] = []
    collection = AutoCable(candidates=db.cables_for_voltage(inputs.v_mv_kv),
                           max_utilization=inputs.max_utilization,
                           max_loss_percent_base=inputs.collection_loss_pct,
                           name="MV collection")
    elements.append(ChainElement(collection, v_kv=inputs.v_mv_kv,
                                 label="MV collection"))

    fleet = branch.fleet
    detail = " + ".join(f"{n}x {tx.display_name}" for tx, n in fleet)
    elements.append(ChainElement(TransformerGroup(name=detail, units=fleet),
                                 v_kv=inputs.v_mv_kv, label="MV/LV stations"))

    if branch.aux_ids:
        elements.append(ChainElement(
            AuxLoad("Aux load", p_kw=branch.aux_p_kw, q_kvar=branch.aux_q_kvar),
            v_kv=inputs.v_mv_kv, label="Aux load"))

    return Chain(elements, name=f"{branch.kind} collection chain")


def _split_active(branches: list[BranchInputs], p_total: float) -> list[float]:
    """Split the combined delivered active power pro-rata by each branch's own
    POC active target — the ticket-05 default, and the ONLY rule for the
    active split (ticket 01 made it the only rule for the reactive split too,
    see :func:`_split_reactive`)."""
    weight_total = sum(b.p_poc_target_kw for b in branches)
    if weight_total <= 0:
        # Unreachable in practice — every branch that exists has a positive
        # target (graph_to_inputs drops zero-target busbars) — guarded rather
        # than dividing by zero.
        return [p_total / len(branches)] * len(branches)
    return [p_total * (b.p_poc_target_kw / weight_total) for b in branches]


def _split_reactive(branches: list[BranchInputs], q_total: float) -> list[float]:
    """Split the combined reactive requirement at the shared MV bus.

    A lone branch (the other fleet's busbar was drawn at a zero target and so
    never became a branch — the topology gate) takes the WHOLE combined
    reactive duty: there is nothing else to assign it to, and this is exactly
    what keeps a zero-BESS hybrid identical to the PV-only design. With two
    branches, the duty is split pro-rata by active power (see
    :func:`_split_active`) — ticket 01 removed the user-controlled override
    that used to let a share be hand-tuned instead; this is now the only rule.
    """
    if len(branches) == 1:
        return [q_total]
    return _split_active(branches, q_total)


def _allocation_capacities_kw(branch: BranchInputs) -> list[list[float | None]] | None:
    """Installed conversion capacity per station, positionally matching
    ``branch.station_ids`` — passed to :func:`~powertool.architecture.
    arrange_plant_manual` so a station's LV share of duty is proportional to
    its own conversion equipment rather than its transformer-station rating.

    PV: installed inverter power (ADR-0005). BESS: installed PCS apparent
    power — containers x PCS units per container x PCS kVA, kVA read as kW at
    PF-1 the same way ADR-0005 reads inverter power (ADR-0008). ``None`` at a
    station position when nothing resolves (unknown solution, or a container
    count that cannot be read) — the same fallback PV already uses, which
    reverts that one station to transformer-rating allocation. Any other
    branch kind allocates by transformer-station rating throughout.
    """
    if branch.kind == "pv":
        return [
            [branch.pv_inverters_by_station[sid].installed_power_kw for sid in ids]
            for ids in branch.station_ids
        ]
    if branch.kind == "bess":
        def capacity_kw(sid: str) -> float | None:
            solution, containers = branch.bess_by_station.get(sid, (None, None))
            if solution is None or containers is None:
                return None
            return containers * solution.pcs_count * solution.pcs_s_kva

        return [[capacity_kw(sid) for sid in ids] for ids in branch.station_ids]
    return None


def solve_architecture(inputs: GraphInputs, db: ComponentDatabase):
    """Run the full pipeline for a drawing.

    Solve order (the substantive change of ticket 05): size the shared export
    chain on the COMBINED active target against the point-of-connection power
    factor, giving the combined (P, Q) requirement at the shared MV bus; split
    that by branch (active pro-rata to each branch's own target, reactive per
    :func:`_split_reactive`); then, per branch, size its own collection chain
    with the reactive-in entry point, arrange it against its own maximum
    loading (:func:`arrange_plant_manual` keeps the drawn circuits and their
    order verbatim, so every run is sized with its own drawn length and any
    section the user pinned on the canvas is forced), and size its circuits;
    finally size the shared HV transformer and export cable ONCE, on every
    branch's combined result — see :func:`powertool.architecture.size_plant`
    for the per-branch refinement this drives.

    Returns ``(stage1s, layouts, arch)`` — one Stage-1 result and one layout
    per branch, same order as ``inputs.branches``, plus the plant-level
    architecture.
    """
    combined = size_generation(build_export_chain(inputs, db),
                               p_poc_kw=inputs.p_poc_kw,
                               pf_target=inputs.pf_target)
    p_splits = _split_active(inputs.branches, combined.p_inv_kw)
    q_splits = _split_reactive(inputs.branches, combined.q_inv_kvar)

    stage1s: list = []
    layouts: list = []
    branch_archs = []
    for branch, p_i, q_i in zip(inputs.branches, p_splits, q_splits):
        stage1 = size_generation_pq(build_collection_chain(inputs, branch, db),
                                    p_head_kw=p_i, q_head_kvar=q_i)
        layout = arrange_plant_manual(
            stage1, branch.circuits,
            v_mv_kv=inputs.v_mv_kv,
            max_loading=branch.max_loading,
            kind=branch.kind,
            ambient_c=inputs.ambient_c,
            allocation_capacities_kw=_allocation_capacities_kw(branch),
        )
        branch_arch = size_branch(
            layout, db.cables_for_voltage(inputs.v_mv_kv),
            max_utilization=inputs.max_utilization,
            max_loss_percent_base=inputs.collection_loss_pct,
            segment_lengths=branch.segment_lengths,
            segment_candidates=branch.segment_candidates,
            export_loss_percent_per_km=inputs.export_loss_pct_per_km,
            # DRAWN aux only, per busbar (ticket 05). The BESS solutions' own
            # auxiliary draw is deliberately absent from the sizing cascade: a
            # battery station's PCS is sized for export duty alone, and the
            # container auxiliaries are fed from a separate supply rather than
            # from the batteries.
            #
            # Keeping it out of the Stage-1 chain alone was not enough. The
            # refinement drives each branch's DELIVERED power up to its target,
            # so an auxiliary load subtracted at the busbar is compensated back
            # into the refined conversion figure — the PCS gets upsized to carry
            # it, by the back door. The nameplate figure stayed clean while the
            # figure that actually sizes the equipment did not.
            #
            # The draw is reported per branch instead (see the branch summary),
            # because the site still has to supply it.
            sections=[
                BusbarSection(
                    busbar_id=busbar.busbar_id,
                    circuit_indices=busbar.circuit_indices,
                    aux_p_kw=busbar.aux_p_kw,
                    aux_q_kvar=busbar.aux_q_kvar,
                    export_edge_id=busbar.export_edge_id,
                    export_length_km=busbar.export_length_km,
                    export_candidates=busbar.export_candidates,
                    export_forced=busbar.export_forced,
                )
                for busbar in branch.busbars
            ],
        )
        stage1s.append(stage1)
        layouts.append(layout)
        branch_archs.append(branch_arch)

    v_export_kv = inputs.v_hv_kv if inputs.hv_mode != "none" else inputs.v_mv_kv
    if _uses_shared_export(inputs) and inputs.export_length_km > 0:
        export_candidates = ([inputs.export_cable] if inputs.export_cable is not None
                             else db.cables_for_voltage(v_export_kv))
    else:
        export_candidates = []
    arch = size_plant(
        branch_archs, stage1s,
        max_utilization=inputs.max_utilization,
        auto_hv=(inputs.hv_mode == "auto"),
        hv_transformer=inputs.hv_transformer,
        hv_n_parallel=inputs.hv_n_parallel,
        hv_cable_candidates=export_candidates,
        hv_cable_length_km=(inputs.export_length_km if _uses_shared_export(inputs)
                            else 0.0),
        v_hv_kv=v_export_kv,
        export_loss_percent_per_km=inputs.export_loss_pct_per_km,
        p_poc_targets_kw=[b.p_poc_target_kw for b in inputs.branches],
        q_poc_targets_kvar=[
            b.p_poc_target_kw * math.tan(math.acos(inputs.pf_target))
            for b in inputs.branches
        ],
    )
    return stage1s, layouts, arch
