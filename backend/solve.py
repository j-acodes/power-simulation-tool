"""Solve pipelines: the Stage-1 chain and the full diagram solve.

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
    Sheet,
    Transformer,
    TransformerGroup,
    auto_hv_transformer,
    build_pdf_report,
    build_sld_pdf,
    sld_sheets,
)
from powertool.architecture import DEFAULT_FEEDERS_PER_BUSBAR
from powertool.graph import (
    branches_summary,
    fallback_notices,
    graph_to_inputs,
    map_results,
    sld_fleets,
    validate_graph,
)
# The diagram solve itself lives in the engine (powertool.plant); also
# imported from here by the tests.
from powertool.plant import solve_architecture

# Stage-1 cable-sizing rule defaults — max_utilization 80%,
# collection_loss_pct 1.30%, export_loss_pct_per_km 0.10%/km, inherited from
# the deleted Streamlit sidebar. Not exposed on the Stage-1 request; the
# frontend catalogue endpoint echoes them for display.
MAX_UTILIZATION = 0.80
COLLECTION_LOSS_PCT = 1.30
EXPORT_LOSS_PCT_PER_KM = 0.10
# Stage-1 planning's feeders-per-busbar limit (ADR-0007, ticket 06) — mirrors
# powertool.graph.DEFAULT_RULES["feeders_per_busbar"]; echoed the same way as
# the constants above for the frontend catalogue endpoint.
FEEDERS_PER_BUSBAR = DEFAULT_FEEDERS_PER_BUSBAR


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

    The interconnection is prepended at the POC end: the export cable (real
    length, export %/km budget — skipped when the catalogue has no cables at
    that voltage) and, for HV interconnection, ONE auto-sized MV/HV
    transformer. In MV interconnection with no export length given, the MV
    busbar -> POC cable is still sized at the worst case (full collection
    budget) so its losses are not ignored. Collection cable sections likewise
    carry no length: the solver runs them at the worst case, consuming the
    full admissible loss budget (conservative by design).

    ADJACENT transformer elements at the SAME voltage are merged into one
    parallel TransformerGroup sharing the load — a mixed station fleet.
    Without this, the linear chain would push the full plant power through
    each block in series, wildly overstating the losses.

    Originally a faithful port of ``build_chain`` in the Streamlit UI, whose
    docstring the two paragraphs above are inherited from; that UI is deleted
    and this is the rationale's only home now. ``elements`` replaces
    ``st.session_state.elements`` as an explicit parameter.
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
                # ``component`` is a catalogue key for every caller with a
                # request schema behind it (Stage1Request); the BESS seed
                # (backend.seed._seed_bess) has no PV-catalogue key for its
                # station and passes the already-resolved Transformer
                # (db.bess_transformer(...)) straight through instead.
                component = e["component"]
                comp = component if isinstance(component, Transformer) else db.transformer(component)
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


def solve_diagram(diagram: dict, db: ComponentDatabase) -> dict:
    """Validate and solve a drawing: ``{"issues": [...], "results": ... | None}``.

    Never raises for a bad drawing: a structural problem comes back as
    validation issues, and an engine ``ValueError`` — a forced cable that cannot
    carry its flow, a station whose losses exceed its own share, or a
    refinement that fails to converge within the iteration cap — comes back as
    an ``engine_error`` issue. Both are answers the editor can show, not server
    failures.
    """
    issues = validate_graph(diagram, db)
    if issues:
        return {"issues": [i.as_dict() for i in issues], "results": None}

    inputs = graph_to_inputs(diagram, db)
    try:
        stage1s, _layouts, arch = solve_architecture(inputs, db)
    except ValueError as exc:
        return {
            "issues": [{"code": "engine_error", "message": str(exc),
                        "node_id": None, "edge_id": None}],
            "results": None,
        }
    return {"issues": [], "results": map_results(inputs, stage1s, arch)}


def report_pdf(diagram: dict, db: ComponentDatabase, plant_name: str,
               project_name: str = "") -> bytes:
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
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    # The per-fleet reporting figures the editor gets, handed to the PDF
    # unchanged so the document and the screen cannot drift apart. This is also
    # what lifts ticket 07's refusal: the report can now describe every fleet
    # rather than the first one with the others silently missing.
    fleets = branches_summary(inputs, arch, stage1s)
    return build_pdf_report(stage1s, arch, fleets=fleets, plant_name=plant_name,
                            ambient_c=inputs.ambient_c,
                            feeders_per_busbar=inputs.feeders_per_busbar,
                            notices=[n.message for n in fallback_notices(arch)],
                            sld_sheets=design_sld_sheets(inputs, arch, fleets),
                            project_name=project_name,
                            pf_target=inputs.pf_target)


def design_sld_sheets(inputs, arch, fleets: list[dict]) -> list[Sheet]:
    """The SLD sheets for a solved design — the one builder both the
    standalone download and the report's embedded sheets go through.

    ``fleets`` is :func:`branches_summary`'s output (busbar/feeder pins
    included, so a pinned feeder rating draws exactly what the report shows);
    the SLD's own inverter model/count is merged in on COPIES, never mutating
    what the report itself reads or what the golden snapshot pins.
    """
    merged = [{**fleet, **pv} for fleet, pv in zip(fleets, sld_fleets(inputs))]
    return sld_sheets(arch, fleets=merged)


def sld_pdf(diagram: dict, db: ComponentDatabase, plant_name: str,
           project_name: str = "") -> bytes:
    """Standalone single-line-diagram PDF for a drawn diagram.

    Same validate-then-solve pipeline as :func:`report_pdf`: a diagram that
    cannot be solved raises ``ValueError`` with the reason, turned into a 400
    by the caller.
    """
    issues = validate_graph(diagram, db)
    if issues:
        raise ValueError(issues[0].message)
    inputs = graph_to_inputs(diagram, db)
    stage1s, _layouts, arch = solve_architecture(inputs, db)
    sheets = design_sld_sheets(inputs, arch, branches_summary(inputs, arch, stage1s))
    return build_sld_pdf(sheets, project_name=project_name, design_name=plant_name)
