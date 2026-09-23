"""Seed wizard: propose a starting diagram from POC-level wizard params.

``seed_diagram`` fixed-points the station count the way the deleted Streamlit
form did, then hands the resulting fleet to the existing auto-arranger
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

from powertool import ComponentDatabase, arrange_plant, size_generation
from powertool.architecture import PlantLayout
from powertool.components import DEFAULT_AMBIENT_C
from powertool.graph import DEFAULT_RULES, validate_graph
from powertool.sizing import SizingResult

from .solve import build_chain, solve_diagram

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
                      v_export_kv: float, *, station: str | object | None = None,
                      p_poc_kw: float | None = None) -> SizingResult:
    """Stage-1 conceptual chain for a fleet of ``n`` identical stations.

    Same recipe as the Stage-1 form (export cable / auto HV transformer / one
    worst-case MV collection cable / the station fleet / aux), built via the
    existing :func:`backend.solve.build_chain`.

    ``station`` and ``p_poc_kw`` default to the PV params (``station_model``
    / ``p_poc_mw``) so the PV seed's call site is byte-for-byte unchanged;
    the BESS seed passes its already-resolved :class:`~powertool.Transformer`
    (from ``db.bess_transformer(...)`` — no PV-catalogue key exists for it)
    and its own POC target explicitly. ``build_chain`` accepts either a
    catalogue key or a resolved component (see its "Transformer" handling).
    """
    v_mv_kv = params["v_mv_kv"]
    if station is None:
        station = params["station_model"]
    elements: list[dict] = [
        {"type": "Cable section", "v_kv": v_mv_kv, "label": "MV collection"},
        {"type": "Transformer", "component": station,
         "v_kv": v_mv_kv, "n_parallel": n, "label": "MV/LV stations"},
    ]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0
    if aux_p_kw or aux_q_kvar:
        elements.append({"type": "Aux load", "v_kv": v_mv_kv, "p_kw": aux_p_kw,
                         "q_kvar": aux_q_kvar, "label": "Aux load"})

    if p_poc_kw is None:
        p_poc_kw = params["p_poc_mw"] * 1000.0
    chain = build_chain(
        elements, db,
        interconnection=params["interconnection"],
        v_export_kv=v_export_kv,
        export_m=params["export_m"],
        p_poc_kw=p_poc_kw,
        pf_target=params["pf_target"],
    )
    return size_generation(chain, p_poc_kw=p_poc_kw, pf_target=params["pf_target"])


def seed_diagram(params: dict, db: ComponentDatabase) -> dict:
    """Propose a starting diagram for a design's declared technology.

    Branches on ``params["technology"]`` (default ``"pv"``, see
    ``backend.schemas.SeedRequest``): the PV branch is :func:`_seed_pv`,
    unchanged since before this docstring; the BESS branch is
    :func:`_seed_bess`; the hybrid branch (ticket 03) is :func:`_seed_hybrid`.
    """
    technology = params.get("technology", "pv")
    if technology == "pv":
        return _seed_pv(params, db)
    if technology == "bess":
        return _seed_bess(params, db)
    if technology == "hybrid":
        return _seed_hybrid(params, db)
    raise ValueError(f"Seeding a {technology!r} design is not yet supported.")


def _size_pv_fleet(params: dict, db: ComponentDatabase, v_export_kv: float, *,
                   p_poc_kw: float | None = None, min_count: int = 1):
    """Fixed-point the PV station count and arrange its layout.

    The sizing half of :func:`_seed_pv` (plan section 5, M3), split out so
    :func:`_seed_hybrid` can size the PV fleet against its own share of the
    shared point of connection. ``min_count`` floors every step of the
    fixed point (never lets the loop settle below it) so a caller forcing a
    higher count, because the real multi-branch solve found this fleet
    undersized, cannot have that override erased by the next iteration.

    Returns ``(layout, station)``. Raises ``ValueError`` for an unpaired
    inverter or an out-of-range ``inverter_count`` — same messages as before
    this split.
    """
    station_key = params["station_model"]
    station = db.transformer(station_key)
    inverter_key = params["pv_inverter"]
    inverter = db.pv_inverters.get(inverter_key)
    pairing = db.pv_inverter_pairings.get(station_key, {}).get(inverter_key)
    inverter_count = params["inverter_count"]
    if inverter is None or pairing is None:
        raise ValueError(
            f"PV inverter {inverter_key!r} is not paired with station {station_key!r}."
        )
    if (isinstance(inverter_count, bool) or not isinstance(inverter_count, int)
            or not 1 <= inverter_count <= pairing.maximum_count):
        raise ValueError(
            f"inverter_count must be a whole number from 1 to {pairing.maximum_count}."
        )
    per_station_capacity = (
        inverter.capability_at(DEFAULT_AMBIENT_C).power_kw * inverter_count
    )
    max_loading = params["max_loading"]
    if p_poc_kw is None:
        p_poc_kw = params["p_poc_mw"] * 1000.0
    pf_target = params["pf_target"]
    # The transformer's own AC power at ambient x max_loading, one station —
    # the fleet-loading bound the engine actually checks (hypot(p_inv, q_inv)
    # / (n * rating_at(ambient))), independent of installed inverter capacity.
    # Mirrors _size_bess_fleet's station_limit.
    station_limit = station.rating_at(DEFAULT_AMBIENT_C) * max_loading

    n = max(
        1,
        math.ceil(p_poc_kw / per_station_capacity),
        math.ceil((p_poc_kw / pf_target) / per_station_capacity),
        math.ceil((p_poc_kw / pf_target) / station_limit),
        min_count,
    )
    stage1 = None
    for _ in range(_MAX_ITERATIONS):
        stage1 = _stage1_for_count(n, params, db, v_export_kv, p_poc_kw=p_poc_kw)
        next_n = max(
            1,
            math.ceil(stage1.p_inv_kw / per_station_capacity),
            math.ceil(stage1.s_inv_kva / per_station_capacity),
            math.ceil(stage1.s_inv_kva / station_limit),
            min_count,
        )
        if next_n == n:
            break
        n = next_n

    layout = arrange_plant(
        stage1, [(station, n)],
        trunk_length_km=params["trunk_m"] / 1000.0,
        spacing_km=params["spacing_m"] / 1000.0,
        v_mv_kv=params["v_mv_kv"],
        max_loading=max_loading,
        # The seed wizard builds a brand-new diagram with no ambient setting
        # of its own yet (see ADR-0004) — explicit rather than relying on
        # arrange_plant's own default, since the produced diagram's default
        # ambient is this same constant.
        ambient_c=DEFAULT_AMBIENT_C,
        # Stage-1 grouping only proposes circuits every segment can actually
        # be cabled for (ADR-0007) — the wizard has the MV cable catalogue in
        # scope, so it opts into the cable-entry-aware ceiling. Every OTHER
        # rule the wizard has no setting of its own for yet (SeedRequest
        # carries none) — the produced diagram's rules below are
        # DEFAULT_RULES verbatim, so this reads the same named constant
        # rather than a second literal that could drift from it.
        cable_candidates=db.cables_for_voltage(params["v_mv_kv"]),
        max_utilization=DEFAULT_RULES["max_utilization"],
        # The wizard's own feeders-per-busbar setting (ADR-0007, ticket 06),
        # deciding when Stage-1 planning opens a second busbar of a fleet.
        # ``.get`` (not ``[...]``) because ``params`` is a plain dict contract
        # (see this function's docstring) older callers may still build
        # without the key, same as ``aux_p_kw``/``aux_q_kvar`` below.
        feeders_per_busbar=params.get("feeders_per_busbar", DEFAULT_RULES["feeders_per_busbar"]),
    )

    return layout, station


def _seed_pv(params: dict, db: ComponentDatabase) -> dict:
    """Propose a starting diagram for a POC target (plan section 5, M3).

    Fixed-point the station count: start from the POC apparent power at the
    target power factor, size the Stage-1 conceptual chain for that many
    stations, re-read the (loss-inflated) inverter requirement, and repeat
    until the count stops changing (capped at ``_MAX_ITERATIONS``) — see
    :func:`_size_pv_fleet`. The resulting fleet is then handed to the
    existing auto-arranger (:func:`powertool.arrange_plant`) exactly as the
    frozen Stage-2 form does, and the layout is rendered into a diagram dict.

    ``params`` (see backend.schemas.SeedRequest): ``p_poc_mw``, ``pf_target``,
    ``interconnection`` ("HV"|"MV"), ``v_hv_kv`` (required for HV),
    ``export_m``, ``v_mv_kv``, ``station_model`` (a catalogue key),
    ``pv_inverter`` (a paired catalogue key), ``inverter_count``,
    ``max_loading``, ``trunk_m``, ``spacing_m``, optional
    ``aux_p_kw``/``aux_q_kvar``.
    """
    interconnection = params["interconnection"]
    v_hv_kv = params.get("v_hv_kv")
    v_mv_kv = params["v_mv_kv"]
    v_export_kv = v_hv_kv if interconnection == "HV" else v_mv_kv

    layout, _station = _size_pv_fleet(params, db, v_export_kv)

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
    pv_inverter = params["pv_inverter"]
    inverter_count = params["inverter_count"]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0

    n_circuits = len(layout.circuit_plans)
    center_x = _CIRCUIT_X0 + max(0, n_circuits - 1) * _CIRCUIT_DX / 2.0

    def circuit_x(c_idx: int) -> float:
        return _CIRCUIT_X0 + (c_idx - 1) * _CIRCUIT_DX

    # Stage-1 planning may open more than one busbar (ADR-0007, ticket 06):
    # ``busbar_groups`` partitions the circuits (0-based) by which busbar
    # carries them, in the order arrange_plant already produced them. The
    # first busbar keeps the original "busbar" id so a single-busbar plan
    # renders byte-identical to before this ticket; each further one gets
    # its own export cable into the same shared HV transformer / POC
    # (ticket 05 made this drawable) and sits over the mean x of its own
    # circuits.
    busbar_groups = layout.busbar_groups or [list(range(n_circuits))]

    def busbar_id(g: int) -> str:
        return "busbar" if g == 0 else f"busbar{g + 1}"

    busbar_of_circuit: dict[int, str] = {}
    busbar_x: list[float] = []
    for g, indices in enumerate(busbar_groups):
        xs = [circuit_x(i + 1) for i in indices]
        busbar_x.append(sum(xs) / len(xs))
        for i in indices:
            busbar_of_circuit[i + 1] = busbar_id(g)

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
        for g in range(len(busbar_groups)):
            edges.append({
                "id": "e_sub" if g == 0 else f"e_sub{g + 1}",
                "source": "hv_tx", "target": busbar_id(g),
                "tier": "mv", "sizing": {"mode": "auto"},
            })
    else:
        for g in range(len(busbar_groups)):
            edges.append({
                "id": "e_export" if g == 0 else f"e_export{g + 1}",
                "source": "poc", "target": busbar_id(g),
                "tier": "mv", "length_m": export_m, "sizing": {"mode": "auto"},
            })

    for g, x in enumerate(busbar_x):
        nodes.append({"id": busbar_id(g), "kind": "busbar", "x": x, "y": _BUS_Y,
                     "props": {}})

    if aux_p_kw or aux_q_kvar:
        nodes.append({"id": "aux", "kind": "aux", "x": center_x + _AUX_DX, "y": _AUX_Y,
                     "props": {"p_kw": aux_p_kw, "q_kvar": aux_q_kvar}})
        edges.append({"id": "e_aux", "source": "busbar", "target": "aux",
                     "tier": "mv", "sizing": {"mode": "auto"}})

    for c_idx, circuit in enumerate(layout.circuit_plans, start=1):
        x = circuit_x(c_idx)
        previous_id: str | None = None
        for s_idx in range(1, len(circuit) + 1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            nodes.append({
                "id": node_id, "kind": "station",
                "x": x, "y": _STATION_Y0 + (s_idx - 1) * _STATION_DY,
                "props": {
                    "mode": "catalogue",
                    "model": station_model,
                    "fleet_kind": "pv",
                    "pv_inverter": pv_inverter,
                    "inverter_count": inverter_count,
                },
            })
            edges.append({
                "id": edge_id,
                "source": previous_id or busbar_of_circuit[c_idx],
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
                "max_utilization": DEFAULT_RULES["max_utilization"],
                "collection_loss_pct": 1.30,
                "export_loss_pct_per_km": 0.10,
                "max_loading": params["max_loading"],
                "feeders_per_busbar": params.get("feeders_per_busbar", DEFAULT_RULES["feeders_per_busbar"]),
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


# --- BESS seed (ticket 02) ---------------------------------------------------

def _bess_containers(required: int, maximum: int, n: int) -> list[int]:
    """Container count per station, in circuit order.

    Fills whole stations to ``maximum`` until ``required`` is placed, the
    station that reaches it takes only the remainder, and — because the
    station COUNT ``n`` is sized on power (installed PCS at the pairing
    maximum), not on energy — any station past that point still gets
    ``maximum`` rather than being left without a positive container count.
    In the ordinary case ``n`` is exactly enough to hold ``required`` (the
    catalogue's PCS-to-energy ratio tracks the declared duration), so this
    reduces to "every station full except the last, which takes what is
    left" — the fill the ticket describes.
    """
    full, remainder = divmod(required, maximum)
    counts = [maximum] * full
    if remainder:
        counts.append(remainder)
    counts += [maximum] * (n - len(counts))
    return counts


def _size_bess_fleet(params: dict, db: ComponentDatabase, v_export_kv: float, *,
                     p_poc_kw: float | None = None, include_aux: bool = True,
                     min_count: int = 1):
    """Fixed-point the BESS station count and arrange its layout.

    The sizing half of :func:`_seed_bess` (ticket 02), split out so
    :func:`_seed_hybrid` can size the BESS fleet against its own share of the
    shared point of connection. ``include_aux`` is False for the hybrid
    caller: the substation auxiliary load is drawn on the PV busbar there
    (ticket 03), so the BESS fleet's own internal Stage-1 approximation must
    not also carry it. ``min_count`` mirrors :func:`_size_pv_fleet`'s — it
    floors every step of the fixed point so a caller forcing a higher count
    cannot have that override eroded by the next iteration.

    Returns ``(layout, station_key, solution_key, maximum, containers,
    pcs_lv_kv)``. Raises ``ValueError`` for a duration mismatch or an
    unpaired station — same messages as before this split.
    """
    station_key = params["bess_station_model"]
    solution_key = params["bess_solution"]
    station = db.bess_transformer(station_key)  # KeyError -> 400 (main.py)
    solution = db.bess_solution(solution_key)  # KeyError -> 400 (main.py)

    discharge_hours = params["discharge_hours"]
    if not math.isclose(solution.duration_h, discharge_hours, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(
            f"BESS solution {solution_key!r} sells a {solution.duration_h:g} h "
            f"discharge, not the requested {discharge_hours:g} h."
        )
    maximum = (db.bess_pairings.get(station_key) or {}).get(solution_key)
    if maximum is None:
        raise ValueError(
            f"Station {station_key!r} is not sold with BESS solution "
            f"{solution_key!r}."
        )

    max_loading = params["max_loading_bess"]
    if p_poc_kw is None:
        p_poc_kw = params["p_poc_bess_mw"] * 1000.0
    pf_target = params["pf_target"]
    # Installed PCS apparent power at the pairing maximum, one station — the
    # BESS analogue of PV's per_station_capacity (ADR-0008: PCS kVA read as
    # kW, one figure for both the active and apparent limit).
    per_station_capacity = maximum * solution.pcs_count * solution.pcs_s_kva
    # The transformer's own AC power at ambient x max_loading, one station —
    # the fleet-loading bound the engine actually checks (hypot(p_inv, q_inv)
    # / (n * rating_at(ambient))), independent of installed PCS.
    station_limit = station.rating_at(DEFAULT_AMBIENT_C) * max_loading

    n = max(
        1,
        math.ceil(p_poc_kw / per_station_capacity),
        math.ceil((p_poc_kw / pf_target) / per_station_capacity),
        math.ceil((p_poc_kw / pf_target) / station_limit),
        min_count,
    )
    stage1_params = params if include_aux else {**params, "aux_p_kw": 0.0, "aux_q_kvar": 0.0}
    stage1 = None
    for _ in range(_MAX_ITERATIONS):
        stage1 = _stage1_for_count(n, stage1_params, db, v_export_kv,
                                   station=station, p_poc_kw=p_poc_kw)
        next_n = max(
            1,
            math.ceil(stage1.p_inv_kw / per_station_capacity),
            math.ceil(stage1.s_inv_kva / per_station_capacity),
            math.ceil(stage1.s_inv_kva / station_limit),
            min_count,
        )
        if next_n == n:
            break
        n = next_n

    # BESS duty is shared across installed PCS (ADR-0008): once the last
    # station holds fewer containers, every FULL station still carries more
    # than the fleet average, so an energy-only container count can leave a
    # full station's own loading over max_loading_bess even though
    # fleet_loading reads within it. A full station's duty is
    # S_fleet x maximum / C_total, so the container total must also satisfy
    # this loading-driven floor (ticket 06).
    required_energy = math.ceil((p_poc_kw * discharge_hours) / solution.e_nominal_kwh)
    required_loading = math.ceil((stage1.s_inv_kva * maximum) / station_limit)
    required = max(required_energy, required_loading)
    if required > n * maximum:
        n = math.ceil(required / maximum)
    containers = _bess_containers(required, maximum, n)

    layout = arrange_plant(
        stage1, [(station, n)],
        trunk_length_km=params["trunk_bess_m"] / 1000.0,
        spacing_km=params["spacing_bess_m"] / 1000.0,
        v_mv_kv=params["v_mv_kv"],
        max_loading=max_loading,
        ambient_c=DEFAULT_AMBIENT_C,
        cable_candidates=db.cables_for_voltage(params["v_mv_kv"]),
        max_utilization=DEFAULT_RULES["max_utilization"],
        feeders_per_busbar=params.get("feeders_per_busbar", DEFAULT_RULES["feeders_per_busbar"]),
    )

    return layout, station_key, solution_key, maximum, containers, solution.pcs_lv_kv


def _seed_bess(params: dict, db: ComponentDatabase) -> dict:
    """Propose a starting diagram for a BESS-only design (ticket 02).

    Mirrors :func:`_seed_pv`'s station-count fixed point, reading installed
    PCS apparent power at the pairing maximum in place of inverter capacity
    (ADR-0008). Containers are then sized to power x duration and filled in
    circuit order (:func:`_bess_containers`) — see :func:`_size_bess_fleet`.

    ``params`` (see backend.schemas.SeedRequest): ``p_poc_bess_mw``,
    ``discharge_hours``, ``bess_solution``, ``bess_station_model``,
    ``max_loading_bess``, ``trunk_bess_m``, ``spacing_bess_m``, plus the
    shared ``interconnection``/voltages/``pf_target``/``export_m``/aux/
    ``feeders_per_busbar`` fields ``_seed_pv`` also reads.
    """
    interconnection = params["interconnection"]
    v_hv_kv = params.get("v_hv_kv")
    v_mv_kv = params["v_mv_kv"]
    v_export_kv = v_hv_kv if interconnection == "HV" else v_mv_kv

    layout, station_key, solution_key, maximum, containers, lv_kv = _size_bess_fleet(
        params, db, v_export_kv,
    )

    return _layout_to_diagram_bess(layout, params, v_export_kv, station_key,
                                   solution_key, maximum, containers, lv_kv)


def _layout_to_diagram_bess(layout: PlantLayout, params: dict, v_export_kv: float,
                            station_key: str, solution_key: str, maximum: int,
                            containers: list[int], lv_kv: float) -> dict:
    """Render a BESS :class:`PlantLayout` into the diagram-dict schema.

    A separate function from :func:`_layout_to_diagram` (the PV renderer) so
    the PV path is never at risk of this ticket's changes; the two share the
    grid-layout constants and the busbar-grouping recipe (ADR-0007).

    The POC target is written to ``p_target_mw`` — the generic field, not
    ``p_target_bess_mw`` — because a single-fleet design (this ticket) is
    read by ``powertool.graph.graph_to_inputs`` off whichever field is the
    plant's only target; ``p_target_bess_mw`` distinguishes a second fleet
    from the first only once a hybrid design (ticket 03) actually draws one.
    See ``tests/test_hybrid.py``'s ``_bess_only`` fixture and its
    "single-fleet BESS plant (ticket 02)" comment in ``graph_to_inputs``.
    """
    interconnection = params["interconnection"]
    v_mv_kv = params["v_mv_kv"]
    v_hv_kv = params.get("v_hv_kv")
    export_m = params["export_m"]
    trunk_m = params["trunk_bess_m"]
    spacing_m = params["spacing_bess_m"]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0

    n_circuits = len(layout.circuit_plans)
    center_x = _CIRCUIT_X0 + max(0, n_circuits - 1) * _CIRCUIT_DX / 2.0

    def circuit_x(c_idx: int) -> float:
        return _CIRCUIT_X0 + (c_idx - 1) * _CIRCUIT_DX

    busbar_groups = layout.busbar_groups or [list(range(n_circuits))]

    def busbar_id(g: int) -> str:
        return "busbar" if g == 0 else f"busbar{g + 1}"

    busbar_of_circuit: dict[int, str] = {}
    busbar_x: list[float] = []
    for g, indices in enumerate(busbar_groups):
        xs = [circuit_x(i + 1) for i in indices]
        busbar_x.append(sum(xs) / len(xs))
        for i in indices:
            busbar_of_circuit[i + 1] = busbar_id(g)

    nodes: list[dict] = [
        {"id": "poc", "kind": "poc", "x": center_x, "y": _POC_Y,
         "props": {"p_target_mw": params["p_poc_bess_mw"], "pf": params["pf_target"]}},
    ]
    edges: list[dict] = []

    if interconnection == "HV":
        nodes.append({"id": "hv_tx", "kind": "hv_tx", "x": center_x, "y": _HV_Y,
                     "props": {"mode": "auto", "n_parallel": 1}})
        edges.append({"id": "e_export", "source": "poc", "target": "hv_tx",
                     "tier": "hv", "length_m": export_m, "sizing": {"mode": "auto"}})
        for g in range(len(busbar_groups)):
            edges.append({
                "id": "e_sub" if g == 0 else f"e_sub{g + 1}",
                "source": "hv_tx", "target": busbar_id(g),
                "tier": "mv", "sizing": {"mode": "auto"},
            })
    else:
        for g in range(len(busbar_groups)):
            edges.append({
                "id": "e_export" if g == 0 else f"e_export{g + 1}",
                "source": "poc", "target": busbar_id(g),
                "tier": "mv", "length_m": export_m, "sizing": {"mode": "auto"},
            })

    for g, x in enumerate(busbar_x):
        nodes.append({"id": busbar_id(g), "kind": "busbar", "x": x, "y": _BUS_Y,
                     "props": {"fleet_kind": "bess"}})

    if aux_p_kw or aux_q_kvar:
        nodes.append({"id": "aux", "kind": "aux", "x": center_x + _AUX_DX, "y": _AUX_Y,
                     "props": {"p_kw": aux_p_kw, "q_kvar": aux_q_kvar}})
        edges.append({"id": "e_aux", "source": "busbar", "target": "aux",
                     "tier": "mv", "sizing": {"mode": "auto"}})

    station_index = 0
    for c_idx, circuit in enumerate(layout.circuit_plans, start=1):
        x = circuit_x(c_idx)
        previous_id: str | None = None
        for s_idx in range(1, len(circuit) + 1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            count = containers[station_index]
            station_index += 1
            props = {
                "mode": "catalogue",
                "model": station_key,
                "fleet_kind": "bess",
                "bess_solution": solution_key,
            }
            if count != maximum:
                props["containers_override"] = count
            nodes.append({
                "id": node_id, "kind": "station",
                "x": x, "y": _STATION_Y0 + (s_idx - 1) * _STATION_DY,
                "props": props,
            })
            edges.append({
                "id": edge_id,
                "source": previous_id or busbar_of_circuit[c_idx],
                "target": node_id,
                "tier": "mv",
                "length_m": trunk_m if s_idx == 1 else spacing_m,
                "sizing": {"mode": "auto"},
            })
            previous_id = node_id

    return {
        "schema_version": 1,
        "settings": {
            "tiers": {"lv_kv": lv_kv, "mv_kv": v_mv_kv,
                     "hv_kv": v_hv_kv if interconnection == "HV" else None},
            "rules": {
                "max_utilization": DEFAULT_RULES["max_utilization"],
                "collection_loss_pct": 1.30,
                "export_loss_pct_per_km": 0.10,
                "max_loading_bess": params["max_loading_bess"],
                "discharge_hours": params["discharge_hours"],
                "feeders_per_busbar": params.get("feeders_per_busbar", DEFAULT_RULES["feeders_per_busbar"]),
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


# --- Hybrid seed (ticket 03) -------------------------------------------------

def _seed_hybrid(params: dict, db: ComponentDatabase) -> dict:
    """Propose a starting diagram for a hybrid design (ticket 03).

    Sizes the PV fleet (:func:`_size_pv_fleet`) and the BESS fleet
    (:func:`_size_bess_fleet`) each as its own cascade behind the one shared
    HV transformer or point of connection, exactly as the PV-only and
    BESS-only seeds do individually — the substation auxiliary load is
    excluded from the BESS fleet's own internal approximation
    (``include_aux=False``) because it is drawn on the PV busbar in the
    rendered diagram, never the BESS one.

    Those two independent, single-fleet approximations are a good starting
    guess but do not capture the interaction of sharing one HV transformer /
    export cable, so once both layouts are rendered into one diagram this
    runs the REAL multi-branch solve (:func:`~backend.solve.solve_diagram`)
    and checks each fleet's own compliance (loading, energy, installed
    inverter/PCS capacity). While a fleet is undersized, its station count is
    raised by one and its layout rebuilt, capped at ``_MAX_ITERATIONS``
    rounds of the real solve — raising if the plant still fails to size
    within that cap (the POC targets are likely too large for the chosen
    station models).
    """
    interconnection = params["interconnection"]
    v_hv_kv = params.get("v_hv_kv")
    v_mv_kv = params["v_mv_kv"]
    v_export_kv = v_hv_kv if interconnection == "HV" else v_mv_kv

    p_poc_pv_kw = params["p_poc_mw"] * 1000.0
    p_poc_bess_kw = params["p_poc_bess_mw"] * 1000.0

    pv_min_count = 1
    bess_min_count = 1
    diagram: dict | None = None

    for _ in range(_MAX_ITERATIONS):
        pv_layout, _pv_station = _size_pv_fleet(
            params, db, v_export_kv, p_poc_kw=p_poc_pv_kw, min_count=pv_min_count,
        )
        (bess_layout, bess_station_key, bess_solution_key, bess_maximum,
         bess_containers, _bess_lv_kv) = _size_bess_fleet(
            params, db, v_export_kv, p_poc_kw=p_poc_bess_kw,
            include_aux=False, min_count=bess_min_count,
        )

        diagram = _layout_to_diagram_hybrid(
            pv_layout, bess_layout, params, v_export_kv,
            bess_station_key, bess_solution_key, bess_maximum, bess_containers,
        )

        issues = validate_graph(diagram, db)
        if issues:
            raise ValueError(
                "Seeded hybrid plant does not validate: "
                + "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            )
        result = solve_diagram(diagram, db)
        if result["issues"]:
            raise ValueError(
                "Seeded hybrid plant did not solve: "
                + "; ".join(issue["message"] for issue in result["issues"])
            )

        station_kind = {
            node["id"]: node["props"].get("fleet_kind", "pv")
            for node in diagram["nodes"] if node["kind"] == "station"
        }
        branches = {branch["kind"]: branch for branch in result["results"]["summary"]["branches"]}
        result_nodes = result["results"]["nodes"]

        def _undersized(kind: str) -> bool:
            branch = branches.get(kind)
            if branch is None:
                return False
            if branch["loading_ok"] is False or branch.get("energy_ok") is False:
                return True
            return any(
                result_nodes.get(sid, {}).get(flag) is False
                for sid, fk in station_kind.items() if fk == kind
                for flag in (
                    "inverter_active_ok", "inverter_apparent_ok",
                    "pcs_active_ok", "pcs_apparent_ok",
                )
            )

        pv_undersized = _undersized("pv")
        bess_undersized = _undersized("bess")
        if not pv_undersized and not bess_undersized:
            return diagram
        if pv_undersized:
            pv_min_count = sum(len(circuit) for circuit in pv_layout.circuit_plans) + 1
        if bess_undersized:
            bess_min_count = sum(len(circuit) for circuit in bess_layout.circuit_plans) + 1

    raise ValueError(
        "Could not size a compliant hybrid plant within the iteration limit; "
        "the point-of-connection targets may be too large for the chosen "
        "station models."
    )


def _layout_to_diagram_hybrid(pv_layout: PlantLayout, bess_layout: PlantLayout,
                              params: dict, v_export_kv: float,
                              bess_station_key: str, bess_solution_key: str,
                              bess_maximum: int, bess_containers: list[int]) -> dict:
    """Render a hybrid PV + BESS :class:`PlantLayout` pair (ticket 03) into
    the diagram-dict schema.

    PV circuits occupy the low end of the shared circuit-index space, BESS
    circuits the high end, so both draw from the same grid-x helper the
    single-fleet renderers use and PV lands left of BESS with no separate
    offset to keep in sync. Busbar ids likewise continue across both
    fleets' ``busbar_groups`` in that same order; the very first busbar is
    always PV's (a hybrid requires a PV fleet) and keeps the bare "busbar"
    id the single-fleet renderers use, so the shared auxiliary load's edge
    target — always the first PV busbar, per the ticket — is unaffected by
    how many busbars either fleet opened.
    """
    interconnection = params["interconnection"]
    v_mv_kv = params["v_mv_kv"]
    v_hv_kv = params.get("v_hv_kv")
    export_m = params["export_m"]
    aux_p_kw = params.get("aux_p_kw") or 0.0
    aux_q_kvar = params.get("aux_q_kvar") or 0.0

    n_pv_circuits = len(pv_layout.circuit_plans)
    n_bess_circuits = len(bess_layout.circuit_plans)
    n_circuits = n_pv_circuits + n_bess_circuits
    center_x = _CIRCUIT_X0 + max(0, n_circuits - 1) * _CIRCUIT_DX / 2.0

    def circuit_x(c_idx: int) -> float:
        return _CIRCUIT_X0 + (c_idx - 1) * _CIRCUIT_DX

    pv_busbar_groups = pv_layout.busbar_groups or [list(range(n_pv_circuits))]
    bess_busbar_groups = bess_layout.busbar_groups or [list(range(n_bess_circuits))]
    pv_busbar_count = len(pv_busbar_groups)
    n_busbars = pv_busbar_count + len(bess_busbar_groups)

    def busbar_id(idx: int) -> str:
        return "busbar" if idx == 0 else f"busbar{idx + 1}"

    busbar_of_circuit: dict[int, str] = {}
    busbar_x: list[float] = []
    for g, indices in enumerate(pv_busbar_groups):
        xs = [circuit_x(i + 1) for i in indices]
        busbar_x.append(sum(xs) / len(xs))
        for i in indices:
            busbar_of_circuit[i + 1] = busbar_id(g)
    for g, indices in enumerate(bess_busbar_groups):
        xs = [circuit_x(n_pv_circuits + i + 1) for i in indices]
        busbar_x.append(sum(xs) / len(xs))
        for i in indices:
            busbar_of_circuit[n_pv_circuits + i + 1] = busbar_id(pv_busbar_count + g)

    nodes: list[dict] = [
        {"id": "poc", "kind": "poc", "x": center_x, "y": _POC_Y,
         "props": {"p_target_mw": params["p_poc_mw"],
                   "p_target_bess_mw": params["p_poc_bess_mw"],
                   "pf": params["pf_target"]}},
    ]
    edges: list[dict] = []

    if interconnection == "HV":
        nodes.append({"id": "hv_tx", "kind": "hv_tx", "x": center_x, "y": _HV_Y,
                     "props": {"mode": "auto", "n_parallel": 1}})
        edges.append({"id": "e_export", "source": "poc", "target": "hv_tx",
                     "tier": "hv", "length_m": export_m, "sizing": {"mode": "auto"}})
        for idx in range(n_busbars):
            edges.append({
                "id": "e_sub" if idx == 0 else f"e_sub{idx + 1}",
                "source": "hv_tx", "target": busbar_id(idx),
                "tier": "mv", "sizing": {"mode": "auto"},
            })
    else:
        for idx in range(n_busbars):
            edges.append({
                "id": "e_export" if idx == 0 else f"e_export{idx + 1}",
                "source": "poc", "target": busbar_id(idx),
                "tier": "mv", "length_m": export_m, "sizing": {"mode": "auto"},
            })

    for idx, x in enumerate(busbar_x):
        fleet_kind = "pv" if idx < pv_busbar_count else "bess"
        nodes.append({"id": busbar_id(idx), "kind": "busbar", "x": x, "y": _BUS_Y,
                     "props": {"fleet_kind": fleet_kind}})

    if aux_p_kw or aux_q_kvar:
        nodes.append({"id": "aux", "kind": "aux", "x": center_x + _AUX_DX, "y": _AUX_Y,
                     "props": {"p_kw": aux_p_kw, "q_kvar": aux_q_kvar}})
        edges.append({"id": "e_aux", "source": "busbar", "target": "aux",
                     "tier": "mv", "sizing": {"mode": "auto"}})

    for c_idx, circuit in enumerate(pv_layout.circuit_plans, start=1):
        x = circuit_x(c_idx)
        previous_id: str | None = None
        for s_idx in range(1, len(circuit) + 1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            nodes.append({
                "id": node_id, "kind": "station",
                "x": x, "y": _STATION_Y0 + (s_idx - 1) * _STATION_DY,
                "props": {
                    "mode": "catalogue",
                    "model": params["station_model"],
                    "fleet_kind": "pv",
                    "pv_inverter": params["pv_inverter"],
                    "inverter_count": params["inverter_count"],
                },
            })
            edges.append({
                "id": edge_id,
                "source": previous_id or busbar_of_circuit[c_idx],
                "target": node_id,
                "tier": "mv",
                "length_m": params["trunk_m"] if s_idx == 1 else params["spacing_m"],
                "sizing": {"mode": "auto"},
            })
            previous_id = node_id

    station_index = 0
    for local_c_idx, circuit in enumerate(bess_layout.circuit_plans, start=1):
        c_idx = n_pv_circuits + local_c_idx
        x = circuit_x(c_idx)
        previous_id = None
        for s_idx in range(1, len(circuit) + 1):
            node_id = f"s{c_idx}_{s_idx}"
            edge_id = f"c{c_idx}_seg{s_idx}"
            count = bess_containers[station_index]
            station_index += 1
            props = {
                "mode": "catalogue",
                "model": bess_station_key,
                "fleet_kind": "bess",
                "bess_solution": bess_solution_key,
            }
            if count != bess_maximum:
                props["containers_override"] = count
            nodes.append({
                "id": node_id, "kind": "station",
                "x": x, "y": _STATION_Y0 + (s_idx - 1) * _STATION_DY,
                "props": props,
            })
            edges.append({
                "id": edge_id,
                "source": previous_id or busbar_of_circuit[c_idx],
                "target": node_id,
                "tier": "mv",
                "length_m": params["trunk_bess_m"] if s_idx == 1 else params["spacing_bess_m"],
                "sizing": {"mode": "auto"},
            })
            previous_id = node_id

    return {
        "schema_version": 1,
        "settings": {
            "tiers": {"lv_kv": _LV_KV, "mv_kv": v_mv_kv,
                     "hv_kv": v_hv_kv if interconnection == "HV" else None},
            "rules": {
                "max_utilization": DEFAULT_RULES["max_utilization"],
                "collection_loss_pct": 1.30,
                "export_loss_pct_per_km": 0.10,
                "max_loading": params["max_loading"],
                "max_loading_bess": params["max_loading_bess"],
                "discharge_hours": params["discharge_hours"],
                "feeders_per_busbar": params.get("feeders_per_busbar", DEFAULT_RULES["feeders_per_busbar"]),
            },
        },
        "nodes": nodes,
        "edges": edges,
    }
