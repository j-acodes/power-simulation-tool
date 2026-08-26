"""Seed wizard: propose a starting diagram from POC-level wizard params.

``seed_diagram`` fixed-points the station count the way the frozen Streamlit
form does, then hands the resulting fleet to the existing auto-arranger
(:func:`powertool.arrange_plant`) and renders the arrangement into the
diagram-dict schema of :mod:`powertool.graph` (see its module docstring for
the schema) — a proposal the user can then rearrange on the canvas, never a
fixed layout.

Pure function: takes a plain dict of wizard params and a
:class:`~powertool.ComponentDatabase`, returns a diagram dict. No
web-framework code here — see ``backend/main.py`` for the request/response
glue.
"""

from __future__ import annotations

import math

from powertool import ComponentDatabase, arrange_plant, size_pv_inverters
from powertool.architecture import PlantLayout
from powertool.sizing import SizingResult

from .solve import build_chain

# Grid layout constants, mirrored from frontend/src/canvas/autoArrange.ts so a
# seeded plant lands where the editor's Auto-arrange button would put it. Every
# gap fits a node plus the two-line cable label drawn at each edge's midpoint.
_POC_Y = 0.0
_HV_Y = 160.0
_BUS_Y = 320.0
_STATION_Y0 = 480.0
_STATION_DY = 150.0
_CIRCUIT_X0 = 100.0
_CIRCUIT_DX = 220.0
_AUX_DX = 520.0  # offset from the POC/busbar column
_AUX_Y = _BUS_Y + 90.0
_LV_KV = 0.8  # not a wizard param; matches powertool.graph.DEFAULT_TIERS

# The loss cascade's demand correction shrinks each pass, so this converges in
# a couple of iterations for realistic plants; capped defensively.
_MAX_ITERATIONS = 5


def _stage1_for_count(n: int, params: dict, db: ComponentDatabase,
                      v_export_kv: float) -> SizingResult:
    """Stage-1 conceptual chain for a fleet of ``n`` identical stations.

    Same recipe as the Stage-1 form (export cable / auto HV transformer / one
    worst-case MV collection cable / the station fleet / aux), built via the
    existing :func:`backend.solve.build_chain`.
    """
    v_mv_kv = params["v_mv_kv"]
    elements: list[dict] = [
        {"type": "Cable section", "v_kv": v_mv_kv, "label": "MV collection"},
        {"type": "Transformer", "component": params["station_model"],
         "v_kv": v_mv_kv, "n_parallel": n, "label": "MV/LV stations"},
    ]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0
    if aux_p_kw or aux_q_kvar:
        elements.append({"type": "Aux load", "v_kv": v_mv_kv, "p_kw": aux_p_kw,
                         "q_kvar": aux_q_kvar, "label": "Aux load"})

    p_poc_kw = params["p_poc_mw"] * 1000.0
    chain = build_chain(
        elements, db,
        interconnection=params["interconnection"],
        v_export_kv=v_export_kv,
        export_m=params["export_m"],
        p_poc_kw=p_poc_kw,
        pf_target=params["pf_target"],
    )
    return size_pv_inverters(chain, p_poc_kw=p_poc_kw, pf_target=params["pf_target"])


def seed_diagram(params: dict, db: ComponentDatabase) -> dict:
    """Propose a starting diagram for a POC target (plan section 5, M3).

    Fixed-point the station count: start from the POC apparent power at the
    target power factor, size the Stage-1 conceptual chain for that many
    stations, re-read the (loss-inflated) inverter requirement, and repeat
    until the count stops changing (capped at ``_MAX_ITERATIONS``). The
    resulting fleet is then handed to the existing auto-arranger
    (:func:`powertool.arrange_plant`) exactly as the frozen Stage-2 form
    does, and the layout is rendered into a diagram dict.

    ``params`` (see backend.schemas.SeedRequest): ``p_poc_mw``, ``pf_target``,
    ``interconnection`` ("HV"|"MV"), ``v_hv_kv`` (required for HV),
    ``export_m``, ``v_mv_kv``, ``station_model`` (a catalogue key),
    ``max_loading``, ``trunk_m``, ``spacing_m``, ``max_circuit_current_a``,
    optional ``aux_p_kw``/``aux_q_kvar``.
    """
    interconnection = params["interconnection"]
    v_mv_kv = params["v_mv_kv"]
    v_hv_kv = params.get("v_hv_kv")
    v_export_kv = v_hv_kv if interconnection == "HV" else v_mv_kv

    station = db.transformer(params["station_model"])
    rated_kva = station.s_rated_kva
    max_loading = params["max_loading"]
    p_poc_kw = params["p_poc_mw"] * 1000.0
    pf_target = params["pf_target"]

    n = max(1, math.ceil((p_poc_kw / pf_target) / (rated_kva * max_loading)))
    stage1 = None
    for _ in range(_MAX_ITERATIONS):
        stage1 = _stage1_for_count(n, params, db, v_export_kv)
        next_n = max(1, math.ceil(stage1.s_inv_kva / (rated_kva * max_loading)))
        if next_n == n:
            break
        n = next_n

    layout = arrange_plant(
        stage1, [(station, n)],
        max_circuit_current_a=params["max_circuit_current_a"],
        trunk_length_km=params["trunk_m"] / 1000.0,
        spacing_km=params["spacing_m"] / 1000.0,
        v_mv_kv=v_mv_kv,
        max_loading=max_loading,
    )

    return _layout_to_diagram(layout, params, v_export_kv)


def _layout_to_diagram(layout: PlantLayout, params: dict, v_export_kv: float) -> dict:
    """Render a :class:`PlantLayout` into the diagram-dict schema."""
    interconnection = params["interconnection"]
    v_mv_kv = params["v_mv_kv"]
    v_hv_kv = params.get("v_hv_kv")
    export_m = params["export_m"]
    trunk_m = params["trunk_m"]
    spacing_m = params["spacing_m"]
    station_model = params["station_model"]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0

    n_circuits = len(layout.circuit_plans)
    center_x = _CIRCUIT_X0 + max(0, n_circuits - 1) * _CIRCUIT_DX / 2.0

    nodes: list[dict] = [
        {"id": "poc", "kind": "poc", "x": center_x, "y": _POC_Y,
         "props": {"p_target_mw": params["p_poc_mw"], "pf": params["pf_target"]}},
    ]
    edges: list[dict] = []

    if interconnection == "HV":
        nodes.append({"id": "hv_tx", "kind": "hv_tx", "x": center_x, "y": _HV_Y,
                     "props": {"mode": "auto", "n_parallel": 1}})
        edges.append({"id": "e_export", "source": "poc", "target": "hv_tx",
                     "tier": "hv", "length_m": export_m, "sizing": {"mode": "auto"}})
        edges.append({"id": "e_sub", "source": "hv_tx", "target": "busbar",
                     "tier": "mv", "sizing": {"mode": "auto"}})
    else:
        edges.append({"id": "e_export", "source": "poc", "target": "busbar",
                     "tier": "mv", "length_m": export_m, "sizing": {"mode": "auto"}})

    nodes.append({"id": "busbar", "kind": "busbar", "x": center_x, "y": _BUS_Y,
                 "props": {}})

    if aux_p_kw or aux_q_kvar:
        nodes.append({"id": "aux", "kind": "aux", "x": center_x + _AUX_DX, "y": _AUX_Y,
                     "props": {"p_kw": aux_p_kw, "q_kvar": aux_q_kvar}})
        edges.append({"id": "e_aux", "source": "busbar", "target": "aux",
                     "tier": "mv", "sizing": {"mode": "auto"}})

    for c_idx, circuit in enumerate(layout.circuit_plans, start=1):
        x = _CIRCUIT_X0 + (c_idx - 1) * _CIRCUIT_DX
        previous_id: str | None = None
        for s_idx in range(1, len(circuit) + 1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            nodes.append({
                "id": node_id, "kind": "station",
                "x": x, "y": _STATION_Y0 + (s_idx - 1) * _STATION_DY,
                "props": {"mode": "catalogue", "model": station_model},
            })
            edges.append({
                "id": edge_id,
                "source": previous_id or "busbar",
                "target": node_id,
                "tier": "mv",
                "length_m": trunk_m if s_idx == 1 else spacing_m,
                "sizing": {"mode": "auto"},
            })
            previous_id = node_id

    return {
        "schema_version": 1,
        "settings": {
            "tiers": {"lv_kv": _LV_KV, "mv_kv": v_mv_kv,
                     "hv_kv": v_hv_kv if interconnection == "HV" else None},
            "rules": {
                "max_utilization": 0.80,
                "collection_loss_pct": 1.30,
                "export_loss_pct_per_km": 0.10,
                "max_circuit_current_a": params["max_circuit_current_a"],
                "max_loading": params["max_loading"],
            },
        },
        "nodes": nodes,
        "edges": edges,
    }
