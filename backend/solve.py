"""Solve pipelines: the Stage-1 chain (ported from Streamlit) and the full
diagram solve.

Pure functions only: they take plain dicts and a :class:`ComponentDatabase` and
return engine objects or plain dicts. No web-framework code here — see
backend/main.py for the request/response glue.
"""

from __future__ import annotations

from powertool import (
    AutoCable,
    AuxLoad,
    Chain,
    ChainElement,
    ComponentDatabase,
    TransformerGroup,
    arrange_plant_manual,
    auto_hv_transformer,
    build_pdf_report,
    size_architecture,
    size_generation,
)
from powertool.graph import GraphInputs, graph_to_inputs, map_results, validate_graph

# Stage-1 cable-sizing rule defaults — the same values the Streamlit sidebar
# initializes to (max_utilization 80%, collection_loss_pct 1.30%,
# export_loss_pct_per_km 0.10%/km). Not exposed on the Stage-1 request; the
# frontend catalogue endpoint echoes them for display.
MAX_UTILIZATION = 0.80
COLLECTION_LOSS_PCT = 1.30
EXPORT_LOSS_PCT_PER_KM = 0.10


def build_chain(
    elements: list[dict],
    db: ComponentDatabase,
    *,
    interconnection: str,
    v_export_kv: float,
    export_m: float,
    p_poc_kw: float,
    pf_target: float,
    max_utilization: float = MAX_UTILIZATION,
    collection_loss_pct: float = COLLECTION_LOSS_PCT,
    export_loss_pct_per_km: float = EXPORT_LOSS_PCT_PER_KM,
) -> Chain:
    """Turn Stage-1 element dicts into a Chain of ChainElements.

    Faithful port of ``build_chain`` in ``app/streamlit_app.py`` — see that
    docstring for the full rationale (export cable / auto HV transformer /
    adjacency-merge of same-voltage transformers into a TransformerGroup /
    worst-case collection cable sections). ``elements`` replaces
    ``st.session_state.elements`` as an explicit parameter so this function
    has no UI dependency.
    """
    raw = elements

    chain_elements = []
    export_candidates = db.cables_for_voltage(v_export_kv)
    if export_m > 0:
        if export_candidates:
            auto = AutoCable(candidates=export_candidates,
                             max_utilization=max_utilization,
                             max_loss_percent_base=0.0,
                             max_loss_percent_per_km=export_loss_pct_per_km,
                             name="Export cable")
            chain_elements.append(ChainElement(auto, v_kv=v_export_kv,
                                         length_km=export_m / 1000.0,
                                         label="Export cable"))
    elif interconnection == "MV" and export_candidates:
        # MV interconnection with no given length: the MV busbar -> POC cable is
        # still sized at the worst case (full collection budget), so its losses
        # enter the cascade instead of being silently ignored.
        auto = AutoCable(candidates=export_candidates,
                         max_utilization=max_utilization,
                         max_loss_percent_base=collection_loss_pct,
                         name="MV interconnection cable")
        chain_elements.append(ChainElement(auto, v_kv=v_export_kv,
                                     label="MV interconnection cable"))
    if interconnection == "HV":
        # Conceptual auto-sizing from the POC apparent power; Stage 2 re-sizes
        # it precisely from the actual busbar power.
        tx_voltages = [e["v_kv"] for e in raw if e["type"] == "Transformer"]
        v_mv_guess = min(tx_voltages) if tx_voltages else 20.0
        hv_tx = auto_hv_transformer(p_poc_kw / pf_target, v_export_kv, v_mv_guess)
        chain_elements.append(ChainElement(hv_tx, v_kv=v_export_kv,
                                     label="MV/HV transformer (auto)"))

    i = 0
    while i < len(raw):
        e = raw[i]
        if e["type"] == "Transformer":
            run = [e]
            j = i + 1
            while (j < len(raw) and raw[j]["type"] == "Transformer"
                   and raw[j]["v_kv"] == e["v_kv"]):
                run.append(raw[j])
                j += 1
            if len(run) == 1:
                comp = db.transformer(e["component"])
                chain_elements.append(ChainElement(comp, v_kv=e["v_kv"],
                                             n_parallel=e["n_parallel"],
                                             label=e["label"]))
            else:
                units = [(db.transformer(r["component"]), r["n_parallel"])
                         for r in run]
                detail = " + ".join(
                    f"{r['n_parallel']}x {db.transformers[r['component']].display_name}"
                    for r in run)
                group = TransformerGroup(name=detail, units=units)
                labels = {r["label"] for r in run if r["label"]}
                label = labels.pop() if len(labels) == 1 else "MV/LV stations"
                chain_elements.append(ChainElement(group, v_kv=e["v_kv"], label=label))
            i = j
        elif e["type"] == "Cable section":
            candidates = db.cables_for_voltage(e["v_kv"])
            auto = AutoCable(candidates=candidates, max_utilization=max_utilization,
                             max_loss_percent_base=collection_loss_pct,
                             name=e["label"])
            chain_elements.append(ChainElement(auto, v_kv=e["v_kv"], label=e["label"]))
            i += 1
        else:  # Aux load
            comp = AuxLoad(e["label"] or "Aux load", p_kw=e["p_kw"], q_kvar=e["q_kvar"])
            chain_elements.append(ChainElement(comp, v_kv=e["v_kv"], label=e["label"]))
            i += 1
    return Chain(chain_elements, name="UI chain")


# ---------------------------------------------------------------------------
# Diagram solve: canvas -> Stage-1 chain -> manual arrangement -> architecture.
# ---------------------------------------------------------------------------

def build_diagram_chain(inputs: GraphInputs, db: ComponentDatabase) -> Chain:
    """The Stage-1 conceptual chain implied by a drawing.

    Same recipe as :func:`build_chain` (the frozen Streamlit one), read off the
    canvas instead of a form, POC-first: the export cable (real drawn length,
    export %/km budget — or, for an MV interconnection with no drawn run, the
    worst-case MV busbar -> POC cable), the MV/HV transformer, ONE worst-case MV
    collection section standing for the whole collector network, ONE
    ``TransformerGroup`` holding every drawn station (they are in parallel, so
    they SHARE the plant power — cascading them would multiply the losses), and
    the lumped aux load.

    Stage 1 is deliberately conceptual: individual run lengths are ignored here
    (the collection section is taken at its full loss budget) because Stage 2 —
    :func:`solve_diagram` — re-sizes every drawn segment with its real length.
    """
    v_export_kv = inputs.v_hv_kv if inputs.hv_mode != "none" else inputs.v_mv_kv
    export_candidates = (
        [inputs.export_cable] if inputs.export_cable is not None
        else db.cables_for_voltage(v_export_kv)
    )

    elements: list[ChainElement] = []
    if inputs.export_length_km > 0:
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
        # Conceptual auto-sizing from the POC apparent power; Stage 2 re-sizes it
        # precisely from the actual busbar power.
        hv_tx = auto_hv_transformer(inputs.p_poc_kw / inputs.pf_target,
                                    inputs.v_hv_kv, inputs.v_mv_kv)
        elements.append(ChainElement(hv_tx, v_kv=inputs.v_hv_kv,
                                     label="MV/HV transformer (auto)"))
    elif inputs.hv_transformer is not None:
        elements.append(ChainElement(inputs.hv_transformer, v_kv=inputs.v_hv_kv,
                                     n_parallel=inputs.hv_n_parallel,
                                     label="MV/HV transformer"))

    collection = AutoCable(candidates=db.cables_for_voltage(inputs.v_mv_kv),
                           max_utilization=inputs.max_utilization,
                           max_loss_percent_base=inputs.collection_loss_pct,
                           name="MV collection")
    elements.append(ChainElement(collection, v_kv=inputs.v_mv_kv,
                                 label="MV collection"))

    fleet = inputs.fleet
    detail = " + ".join(f"{n}x {tx.display_name}" for tx, n in fleet)
    elements.append(ChainElement(TransformerGroup(name=detail, units=fleet),
                                 v_kv=inputs.v_mv_kv, label="MV/LV stations"))

    if inputs.aux_ids:
        elements.append(ChainElement(
            AuxLoad("Aux load", p_kw=inputs.aux_p_kw, q_kvar=inputs.aux_q_kvar),
            v_kv=inputs.v_mv_kv, label="Aux load"))

    return Chain(elements, name="diagram chain")


def solve_architecture(inputs: GraphInputs, db: ComponentDatabase):
    """Run the full pipeline for a drawing: Stage 1, then Stage 2.

    The arrangement is the user's (:func:`arrange_plant_manual` keeps the drawn
    circuits and their order verbatim), so every run is sized with its own drawn
    length and any section the user pinned on the canvas is forced.
    """
    stage1 = size_generation(build_diagram_chain(inputs, db),
                               p_poc_kw=inputs.p_poc_kw,
                               pf_target=inputs.pf_target)
    layout = arrange_plant_manual(
        stage1, inputs.circuits,
        max_circuit_current_a=inputs.max_circuit_current_a,
        v_mv_kv=inputs.v_mv_kv,
        max_loading=inputs.max_loading,
    )
    v_export_kv = inputs.v_hv_kv if inputs.hv_mode != "none" else inputs.v_mv_kv
    if inputs.export_length_km > 0:
        export_candidates = ([inputs.export_cable] if inputs.export_cable is not None
                             else db.cables_for_voltage(v_export_kv))
    else:
        export_candidates = []
    arch = size_architecture(
        layout, stage1, db.cables_for_voltage(inputs.v_mv_kv),
        max_utilization=inputs.max_utilization,
        max_loss_percent_base=inputs.collection_loss_pct,
        segment_lengths=inputs.segment_lengths,
        segment_candidates=inputs.segment_candidates,
        auto_hv=(inputs.hv_mode == "auto"),
        hv_transformer=inputs.hv_transformer,
        hv_n_parallel=inputs.hv_n_parallel,
        hv_cable_candidates=export_candidates,
        hv_cable_length_km=inputs.export_length_km,
        v_hv_kv=v_export_kv,
        export_loss_percent_per_km=inputs.export_loss_pct_per_km,
        aux_p_kw=inputs.aux_p_kw,
        aux_q_kvar=inputs.aux_q_kvar,
        p_poc_target_kw=inputs.p_poc_kw,
    )
    return stage1, layout, arch


def solve_diagram(diagram: dict, db: ComponentDatabase) -> dict:
    """Validate and solve a drawing: ``{"issues": [...], "results": ... | None}``.

    Never raises for a bad drawing: a structural problem comes back as
    validation issues, and an engine ``ValueError`` — a forced cable that cannot
    carry its flow, a station whose losses exceed its own share — comes back as
    an ``engine_error`` issue. Both are answers the editor can show, not server
    failures.
    """
    issues = validate_graph(diagram, db)
    if issues:
        return {"issues": [i.as_dict() for i in issues], "results": None}

    inputs = graph_to_inputs(diagram, db)
    try:
        stage1, _layout, arch = solve_architecture(inputs, db)
    except ValueError as exc:
        return {
            "issues": [{"code": "engine_error", "message": str(exc),
                        "node_id": None, "edge_id": None}],
            "results": None,
        }
    return {"issues": [], "results": map_results(inputs, stage1, arch)}


def report_pdf(diagram: dict, db: ComponentDatabase, plant_name: str) -> bytes:
    """PDF sizing report for a drawn diagram — methodology + full loss tables.

    Same pipeline as :func:`solve_diagram`, but the architecture goes to
    :func:`powertool.build_pdf_report` instead of the canvas mapping. A drawing
    that cannot be solved raises ``ValueError`` with the reason: unlike the
    editor's live solve there is nothing partial worth returning, so the caller
    turns it into a 400.
    """
    issues = validate_graph(diagram, db)
    if issues:
        raise ValueError(issues[0].message)
    inputs = graph_to_inputs(diagram, db)
    stage1, _layout, arch = solve_architecture(inputs, db)
    return build_pdf_report(stage1, arch, plant_name=plant_name)
