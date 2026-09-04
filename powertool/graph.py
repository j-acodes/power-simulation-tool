"""Diagram <-> engine mapping: validate a drawn single-line diagram, turn it
into engine inputs, and key the engine results back to the canvas elements.

The canvas is the input: an engineer draws the plant (POC, optional MV/HV
transformer, MV busbar, MV/LV stations daisy-chained on collector circuits, aux
loads) and the drawing — not a form — dictates the arrangement. This module is
the whole translation layer and deliberately contains NO physics: it reads plain
dicts (the stored canvas payload, see the schema below), produces the engine
types of :mod:`powertool`, and re-keys the results by canvas id. It imports no
web framework and no UI code, so it can be unit-tested on hand-built dicts.

Diagram schema (``schema_version`` 1)::

    {"schema_version": 1,
     "settings": {
        "tiers": {"lv_kv": 0.8, "mv_kv": 20.0, "hv_kv": 132.0},   # hv_kv null -> MV interconnection
        "rules": {"max_utilization": 0.80, "collection_loss_pct": 1.30,
                  "export_loss_pct_per_km": 0.10, "max_circuit_current_a": 400.0}},
     "nodes": [{"id": ..., "kind": "poc|hv_tx|busbar|station|aux",
                "x": ..., "y": ..., "props": {...}}],
     "edges": [{"id": ..., "source": ..., "target": ..., "tier": "lv|mv|hv",
                "length_m": ..., "sizing": {"mode": "auto"}
                                  | {"mode": "forced", "cable": "<catalogue key>"}}]}

Parsing is PERMISSIVE about unknown keys (the canvas may carry cosmetic fields
the engine ignores, and the schema will grow) and STRICT about structure: every
problem is reported as a :class:`GraphIssue` carrying the offending node or edge
id, never as an exception — the editor highlights the element instead of showing
a stack trace.

Topology contract (checked by :func:`validate_graph`)::

    poc --(hv edge = export cable)-- hv_tx --(mv)-- busbar --(mv trunk)-- station -- station ...
    poc --(mv edge = MV interconnection)--------- busbar --(mv)-- aux

Edges are drawn undirected; the direction is derived by rooting the graph at the
POC, so an edge drawn "backwards" still reads correctly. Power flows the other
way (inverter -> POC), as everywhere else in the engine.

Positional bijection: circuits and the stations inside them keep the drawn order
all the way through :func:`powertool.architecture.arrange_plant_manual`, so a
result at (circuit c, position k) always belongs to ``station_ids[c][k]`` and
``segment_edge_ids[(c + 1, k + 1)]``. No engine-side identifier is needed, and
nothing in the pipeline may reorder.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .architecture import PlantArchitecture
from .components import Cable, Transformer
from .sizing import SizingResult

NODE_KINDS = ("poc", "hv_tx", "busbar", "station", "aux")
TIERS = ("lv", "mv", "hv")
# The fleet kinds a station may declare. One tuple, read by both the lenient
# parser below and the strict validator, so "what counts as a fleet kind" has
# exactly one definition.
FLEET_KINDS = ("pv", "bess")

# Rule defaults, mirroring the frozen Streamlit sidebar (max utilization 80 %,
# collection loss budget 1.30 %, export budget 0.10 %/km) and the Stage-2
# planning cap of 400 A per MV collector circuit. A diagram may override any of
# them in ``settings.rules``.
DEFAULT_RULES = {
    "max_utilization": 0.80,
    "collection_loss_pct": 1.30,
    "export_loss_pct_per_km": 0.10,
    "max_circuit_current_a": 400.0,
    "max_loading": 1.0,
}
DEFAULT_TIERS = {"lv_kv": 0.8, "mv_kv": 20.0, "hv_kv": None}


@dataclass(frozen=True)
class GraphIssue:
    """One problem found in a drawing (or one warning raised by the results).

    ``node_id`` / ``edge_id`` point at the offending canvas element whenever the
    problem has one, so the editor can select and highlight it.
    """

    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message,
                "node_id": self.node_id, "edge_id": self.edge_id}


# --- small tolerant readers -------------------------------------------------
# The diagram comes from JSON written by a browser: anything may be missing or
# of the wrong type. These never raise; callers turn a None into an issue.

def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value) -> float | None:
    """A finite float, or None when the value is not a usable number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _props(node: dict) -> dict:
    return _dict(node.get("props"))


def _tier_kv(diagram: dict, tier: str) -> float | None:
    tiers = _dict(_dict(diagram.get("settings")).get("tiers"))
    key = f"{tier}_kv"
    if key not in tiers:
        return _num(DEFAULT_TIERS.get(key))
    return _num(tiers.get(key))


def _rule(diagram: dict, key: str) -> float:
    rules = _dict(_dict(diagram.get("settings")).get("rules"))
    value = _num(rules.get(key))
    return DEFAULT_RULES[key] if value is None else value


def _length_km(edge: dict) -> float | None:
    metres = _num(edge.get("length_m"))
    return None if metres is None else metres / 1000.0


# --- transformer construction ------------------------------------------------

_CUSTOM_TX_REQUIRED = ("s_rated_kva", "uk_percent", "pk_kw")
_CUSTOM_TX_OPTIONAL = ("p0_kw", "i0_percent")


def _custom_transformer(props: dict, name: str, hv_kv: float | None,
                        lv_kv: float | None) -> Transformer | None:
    """Build a Transformer from custom (non-catalogue) props, or None if the
    props are unusable — including a uk% too small for the given load loss,
    which the loss model itself rejects."""
    values = {}
    for key in _CUSTOM_TX_REQUIRED:
        value = _num(props.get(key))
        if value is None or value <= 0:
            return None
        values[key] = value
    for key in _CUSTOM_TX_OPTIONAL:
        value = _num(props.get(key, 0.0))
        if value is None or value < 0:
            return None
        values[key] = value
    tx = Transformer(name=str(props.get("name") or name), hv_kv=hv_kv, lv_kv=lv_kv,
                     **values)
    try:
        tx.ux_percent  # rejects uk% < ur% implied by the load losses
    except ValueError:
        return None
    return tx


def _fleet_kind(props: dict) -> str:
    """A station's fleet kind: ``pv`` or ``bess``. Absent parses as ``pv`` —
    the backward-compatibility guarantee for every design already saved.

    Deliberately lenient: an unrecognised value also reads as ``pv`` so that
    mapping a drawing never raises. :func:`validate_graph` is the authority and
    rejects such a value outright (``bad_fleet_kind``), so this fallback is only
    ever reached for a diagram that was never validated.
    """
    kind = props.get("fleet_kind")
    return kind if kind in FLEET_KINDS else "pv"


def _station_transformer(node: dict, db, v_mv_kv: float | None,
                         v_lv_kv: float | None) -> Transformer | None:
    """The Transformer a station node stands for, or None when its props are
    unusable (unknown catalogue key or invalid custom parameters).

    A catalogue-mode station picks from the transformer catalogue that
    matches its fleet kind: PV stations from ``db.transformers``, BESS
    stations from the separate ``db.bess_transformers``.
    """
    props = _props(node)
    mode = props.get("mode") or ("catalogue" if props.get("model") else None)
    if mode == "catalogue":
        key = props.get("model")
        catalogue = db.bess_transformers if _fleet_kind(props) == "bess" else db.transformers
        tx = catalogue.get(key) if isinstance(key, str) else None
        return tx
    if mode == "custom":
        return _custom_transformer(props, f"Station {node.get('id')}",
                                   hv_kv=v_mv_kv, lv_kv=v_lv_kv)
    return None


def _hv_transformer(node: dict, db, v_hv_kv: float | None,
                    v_mv_kv: float | None) -> Transformer | None:
    """The MV/HV Transformer for a ``model``/``custom`` hv_tx node (``auto`` is
    sized by the engine and returns None here)."""
    props = _props(node)
    mode = props.get("mode") or "auto"
    if mode == "model":
        key = props.get("model")
        return db.transformers.get(key) if isinstance(key, str) else None
    if mode == "custom":
        return _custom_transformer(props, f"MV/HV transformer {node.get('id')}",
                                   hv_kv=v_hv_kv, lv_kv=v_mv_kv)
    return None


# --- graph structure ---------------------------------------------------------

@dataclass
class _Tree:
    """The drawing rooted at the POC: parent/children plus what did not fit."""

    parent: dict[str, tuple[str, dict]] = field(default_factory=dict)
    children: dict[str, list[tuple[str, dict]]] = field(default_factory=dict)
    reached: set[str] = field(default_factory=set)
    extra_edges: list[dict] = field(default_factory=list)  # cycle-closing edges


def _root_tree(nodes: dict[str, dict], edges: list[dict], root_id: str) -> _Tree:
    """Root the (undirected) drawing at the POC by breadth-first search.

    Children keep the order of the diagram's edge list — that is the drawing's
    own order, and it becomes the circuit order downstream.
    """
    adjacency: dict[str, list[tuple[str, dict]]] = {nid: [] for nid in nodes}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        adjacency[source].append((target, edge))
        adjacency[target].append((source, edge))

    tree = _Tree(children={nid: [] for nid in nodes})
    tree.reached.add(root_id)
    queue = [root_id]
    seen_edges: set[int] = set()
    while queue:
        current = queue.pop(0)
        for neighbour, edge in adjacency[current]:
            if id(edge) in seen_edges:
                continue
            seen_edges.add(id(edge))
            if neighbour in tree.reached:
                tree.extra_edges.append(edge)  # closes a loop: not radial
                continue
            tree.reached.add(neighbour)
            tree.parent[neighbour] = (current, edge)
            tree.children[current].append((neighbour, edge))
            queue.append(neighbour)
    return tree


def _parse_structure(diagram: dict, issues: list[GraphIssue]):
    """Index nodes and edges, reporting malformed entries. Returns
    ``(nodes, edges)`` or ``None`` when the drawing cannot be walked at all."""
    if not isinstance(diagram, dict):
        issues.append(GraphIssue("bad_schema", "The diagram must be an object."))
        return None

    nodes: dict[str, dict] = {}
    for index, raw in enumerate(_list(diagram.get("nodes"))):
        node = _dict(raw)
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            issues.append(GraphIssue("bad_schema",
                                     f"Node #{index + 1} has no usable id."))
            continue
        if node_id in nodes:
            issues.append(GraphIssue("bad_schema",
                                     f"Duplicate node id '{node_id}'.", node_id=node_id))
            continue
        if node.get("kind") not in NODE_KINDS:
            issues.append(GraphIssue(
                "bad_schema",
                f"Node '{node_id}' has an unknown kind {node.get('kind')!r} "
                f"(expected one of {', '.join(NODE_KINDS)}).", node_id=node_id))
            continue
        nodes[node_id] = node

    edges: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(_list(diagram.get("edges"))):
        edge = _dict(raw)
        edge_id = edge.get("id")
        if not isinstance(edge_id, str) or not edge_id:
            issues.append(GraphIssue("bad_schema",
                                     f"Edge #{index + 1} has no usable id."))
            continue
        if edge_id in seen_ids:
            issues.append(GraphIssue("bad_schema",
                                     f"Duplicate edge id '{edge_id}'.", edge_id=edge_id))
            continue
        seen_ids.add(edge_id)
        source, target = edge.get("source"), edge.get("target")
        if source not in nodes or target not in nodes:
            issues.append(GraphIssue(
                "unknown_node",
                f"Edge '{edge_id}' connects to a block that is not on the "
                f"diagram ({source!r} -> {target!r}).", edge_id=edge_id))
            continue
        if source == target:
            issues.append(GraphIssue("cycle",
                                     f"Edge '{edge_id}' loops a block onto itself.",
                                     edge_id=edge_id))
            continue
        edges.append(edge)

    if not nodes:
        issues.append(GraphIssue("no_poc", "The diagram is empty — draw a Point "
                                           "of Connection to start."))
        return None
    return nodes, edges


def _singleton(nodes: dict[str, dict], kind: str, issues: list[GraphIssue],
               missing_code: str, extra_code: str, label: str) -> str | None:
    """Exactly one node of ``kind`` must exist; report and return None if not."""
    found = [nid for nid, node in nodes.items() if node["kind"] == kind]
    if not found:
        issues.append(GraphIssue(missing_code, f"The diagram needs a {label}."))
        return None
    if len(found) > 1:
        for extra in found[1:]:
            issues.append(GraphIssue(
                extra_code,
                f"Only one {label} is allowed — remove '{extra}'.", node_id=extra))
        return None
    return found[0]


# --- validation --------------------------------------------------------------

def _check_roles(nodes, tree, poc_id, busbar_id, issues) -> None:
    """Every block must sit where its kind belongs on the POC-rooted tree."""
    kind_of = {nid: node["kind"] for nid, node in nodes.items()}

    def children(nid: str) -> list[str]:
        return [child for child, _ in tree.children.get(nid, [])]

    def parent(nid: str) -> str | None:
        entry = tree.parent.get(nid)
        return entry[0] if entry else None

    poc_children = children(poc_id)
    if len(poc_children) != 1 or kind_of[poc_children[0]] not in ("hv_tx", "busbar"):
        issues.append(GraphIssue(
            "bad_topology",
            "The Point of Connection must connect to exactly one block: the "
            "MV/HV transformer, or the MV busbar for an MV interconnection.",
            node_id=poc_id))

    for nid, kind in kind_of.items():
        if nid not in tree.reached or nid == poc_id:
            continue
        kids = children(nid)
        up = parent(nid)
        if kind == "hv_tx":
            if up != poc_id or [kind_of[k] for k in kids] != ["busbar"]:
                issues.append(GraphIssue(
                    "bad_topology",
                    "The MV/HV transformer must sit between the Point of "
                    "Connection and the MV busbar.", node_id=nid))
        elif kind == "busbar":
            if kind_of.get(up) not in ("poc", "hv_tx"):
                issues.append(GraphIssue(
                    "bad_topology",
                    "The MV busbar must hang off the Point of Connection or the "
                    "MV/HV transformer.", node_id=nid))
            bad = [k for k in kids if kind_of[k] not in ("station", "aux")]
            for k in bad:
                issues.append(GraphIssue(
                    "bad_topology",
                    f"Only stations and aux loads connect to the MV busbar "
                    f"('{k}' does not).", node_id=k))
            if not any(kind_of[k] == "station" for k in kids):
                issues.append(GraphIssue(
                    "no_stations",
                    "No MV/LV station is connected to the busbar — the plant has "
                    "nothing to size.", node_id=nid))
        elif kind == "station":
            if kind_of.get(up) not in ("busbar", "station"):
                issues.append(GraphIssue(
                    "bad_topology",
                    "A station must be fed by the MV busbar or by the station "
                    "before it on its circuit.", node_id=nid))
            downstream = [k for k in kids if kind_of[k] == "station"]
            for k in kids:
                if kind_of[k] != "station":
                    issues.append(GraphIssue(
                        "bad_topology",
                        f"A station can only feed the next station on its "
                        f"circuit ('{k}' is a {kind_of[k]}).", node_id=k))
            if len(downstream) > 1:
                issues.append(GraphIssue(
                    "station_degree",
                    f"Station '{nid}' feeds {len(downstream)} stations — MV "
                    f"circuits are radial daisy chains: one cable in, at most "
                    f"one cable out.", node_id=nid))
        elif kind == "aux":
            if up != busbar_id or kids:
                issues.append(GraphIssue(
                    "bad_topology",
                    "An aux load attaches to the MV busbar and feeds nothing.",
                    node_id=nid))


def _edge_role(kinds: tuple[str, str]) -> tuple[str, str]:
    """What an edge is and which tier it must carry, from the kinds of the
    blocks it joins (upstream first, as rooted at the POC):

    * ``export``     — POC -> MV/HV transformer (HV) or POC -> busbar (MV
      interconnection): the export cable, sized with its real length.
    * ``substation``  — MV/HV transformer -> busbar: an internal substation
      connection, not a cable run (no length, never sized).
    * ``segment``     — busbar -> station or station -> station: a sized MV run.
    * ``aux``         — busbar -> aux load: an attachment, not a run.
    """
    upstream, downstream = kinds
    if upstream == "poc":
        return "export", ("hv" if downstream == "hv_tx" else "mv")
    if (upstream, downstream) == ("hv_tx", "busbar"):
        return "substation", "mv"
    if downstream == "aux":
        return "aux", "mv"
    return "segment", "mv"


def _check_edges(diagram, nodes, tree, edges, db, issues) -> None:
    """Tier, length and forced-section checks, per what each edge represents."""
    v_mv = _tier_kv(diagram, "mv")
    v_hv = _tier_kv(diagram, "hv")
    if v_mv is None or v_mv <= 0:
        issues.append(GraphIssue("bad_tier",
                                 "settings.tiers.mv_kv must be a positive voltage."))

    oriented = {id(edge): (parent, child)
                for child, (parent, edge) in tree.parent.items()}

    for edge in edges:
        if id(edge) not in oriented:
            continue  # a loop-closing or disconnected edge: already reported
        edge_id = edge["id"]
        tier = edge.get("tier")
        upstream, downstream = oriented[id(edge)]
        role, expected = _edge_role((nodes[upstream]["kind"], nodes[downstream]["kind"]))

        if tier not in TIERS:
            issues.append(GraphIssue(
                "bad_tier",
                f"Cable '{edge_id}' has an unknown network tier {tier!r} "
                f"(expected one of {', '.join(TIERS)}).", edge_id=edge_id))
            continue
        if tier != expected:
            issues.append(GraphIssue(
                "bad_tier",
                f"Cable '{edge_id}' is drawn as {tier.upper()} but joins a "
                f"{expected.upper()} section — voltages are set once per tier in "
                f"the settings, so the tier must match the section.",
                edge_id=edge_id))
            continue
        if tier == "hv" and (v_hv is None or v_hv <= 0):
            issues.append(GraphIssue(
                "bad_tier",
                "An HV export cable needs settings.tiers.hv_kv (null means an MV "
                "interconnection, with no MV/HV transformer).", edge_id=edge_id))

        length_km = _length_km(edge)
        if role == "segment":
            # A drawn run always has a real length; the manual layout carries no
            # default spacing to fall back on.
            if length_km is None or length_km <= 0:
                issues.append(GraphIssue(
                    "missing_length",
                    f"Cable '{edge_id}' needs a positive length_m — every drawn "
                    f"MV run is sized with its own length.", edge_id=edge_id))
        elif role == "export":
            # 0 m is legitimate: the POC sits at the substation, no export run.
            if length_km is not None and length_km < 0:
                issues.append(GraphIssue(
                    "missing_length",
                    f"Cable '{edge_id}' has a negative length_m.", edge_id=edge_id))

        sizing = _dict(edge.get("sizing"))
        mode = sizing.get("mode", "auto")
        if mode not in ("auto", "forced"):
            issues.append(GraphIssue(
                "bad_schema",
                f"Cable '{edge_id}' has an unknown sizing mode {mode!r} "
                f"(expected 'auto' or 'forced').", edge_id=edge_id))
        elif mode == "forced":
            if role not in ("segment", "export"):
                issues.append(GraphIssue(
                    "bad_schema",
                    f"Cable '{edge_id}' is not a sized run — it cannot force a "
                    f"section.", edge_id=edge_id))
                continue
            name = sizing.get("cable")
            cable = db.cables.get(name) if isinstance(name, str) else None
            if cable is None:
                issues.append(GraphIssue(
                    "unknown_cable",
                    f"Cable '{edge_id}' forces section {name!r}, which is not in "
                    f"the catalogue.", edge_id=edge_id))
                continue
            section_kv = v_hv if tier == "hv" else v_mv
            if (section_kv is not None and cable.rated_voltage_kv is not None
                    and cable.rated_voltage_kv < section_kv - 1e-9):
                issues.append(GraphIssue(
                    "bad_tier",
                    f"Cable '{edge_id}' forces {cable.name} "
                    f"({cable.rated_voltage_kv:g} kV), below the "
                    f"{section_kv:g} kV of its section.", edge_id=edge_id))


def _check_props(nodes, tree, db, diagram, issues) -> None:
    """POC target, station models and aux figures must be usable numbers."""
    v_mv = _tier_kv(diagram, "mv")
    v_lv = _tier_kv(diagram, "lv")
    v_hv = _tier_kv(diagram, "hv")

    for nid, node in nodes.items():
        if nid not in tree.reached:
            continue
        kind = node["kind"]
        props = _props(node)
        if kind == "poc":
            p_mw = _num(props.get("p_target_mw"))
            pf = _num(props.get("pf"))
            if p_mw is None or p_mw <= 0:
                issues.append(GraphIssue(
                    "bad_props",
                    "The Point of Connection needs a positive target power "
                    "(p_target_mw).", node_id=nid))
            if pf is None or not 0.0 < pf <= 1.0:
                issues.append(GraphIssue(
                    "bad_props",
                    "The Point of Connection needs a power factor in (0, 1].",
                    node_id=nid))
        elif kind == "station":
            fleet_kind = _fleet_kind(props)
            # An ABSENT fleet kind legitimately means "pv" (old designs). A
            # PRESENT but unrecognised one is a structural error, not an
            # unknown key to shrug off: coercing "BESS" or "wind" to "pv"
            # would size the station against the wrong catalogue silently.
            raw_kind = props.get("fleet_kind")
            if raw_kind is not None and raw_kind not in FLEET_KINDS:
                issues.append(GraphIssue(
                    "bad_fleet_kind",
                    f"Station '{nid}' has fleet kind {raw_kind!r}; it must be "
                    f"one of {', '.join(repr(k) for k in FLEET_KINDS)}.",
                    node_id=nid))
            mode = props.get("mode") or ("catalogue" if props.get("model") else None)
            tx = None
            if mode == "catalogue":
                tx = _station_transformer(node, db, v_mv, v_lv)
                if tx is None:
                    issues.append(GraphIssue(
                        "unknown_model",
                        f"Station '{nid}' uses transformer "
                        f"{props.get('model')!r}, which is not in the catalogue.",
                        node_id=nid))
            elif mode == "custom":
                tx = _station_transformer(node, db, v_mv, v_lv)
                if tx is None:
                    issues.append(GraphIssue(
                        "bad_props",
                        f"Station '{nid}' has incomplete or inconsistent custom "
                        f"transformer data (needs s_rated_kva, uk_percent, pk_kw, "
                        f"with uk% above the load-loss share).", node_id=nid))
            else:
                issues.append(GraphIssue(
                    "unknown_model",
                    f"Station '{nid}' has no transformer: pick a catalogue model "
                    f"or enter custom parameters.", node_id=nid))

            if fleet_kind == "bess":
                solution_name = props.get("bess_solution")
                solution = (db.bess_solutions.get(solution_name)
                           if isinstance(solution_name, str) else None)
                if solution is None:
                    issues.append(GraphIssue(
                        "unknown_bess_solution",
                        f"Station '{nid}' names no BESS solution: pick one from "
                        f"the catalogue.", node_id=nid))
                elif (tx is not None and tx.lv_kv is not None
                      and abs(tx.lv_kv - solution.pcs_lv_kv) > 1e-9):
                    issues.append(GraphIssue(
                        "bess_lv_mismatch",
                        f"Station '{nid}' transformer LV ({tx.lv_kv:g} kV) "
                        f"disagrees with {solution.name}'s PCS voltage "
                        f"({solution.pcs_lv_kv:g} kV).", node_id=nid))
        elif kind == "hv_tx":
            mode = props.get("mode") or "auto"
            n_parallel = _num(props.get("n_parallel", 1))
            if mode not in ("auto", "model", "custom"):
                issues.append(GraphIssue(
                    "bad_props",
                    f"The MV/HV transformer mode {mode!r} is unknown (auto, "
                    f"model or custom).", node_id=nid))
            elif mode == "model" and _hv_transformer(node, db, v_hv, v_mv) is None:
                issues.append(GraphIssue(
                    "unknown_model",
                    f"The MV/HV transformer uses {props.get('model')!r}, which is "
                    f"not in the catalogue.", node_id=nid))
            elif mode == "custom" and _hv_transformer(node, db, v_hv, v_mv) is None:
                issues.append(GraphIssue(
                    "bad_props",
                    "The MV/HV transformer has incomplete or inconsistent custom "
                    "data (needs s_rated_kva, uk_percent, pk_kw).", node_id=nid))
            if n_parallel is None or n_parallel < 1 or n_parallel != int(n_parallel):
                issues.append(GraphIssue(
                    "bad_props",
                    "The MV/HV transformer needs a whole number of parallel units "
                    "(>= 1).", node_id=nid))
        elif kind == "aux":
            for key in ("p_kw", "q_kvar"):
                if _num(props.get(key, 0.0)) is None:
                    issues.append(GraphIssue(
                        "bad_props",
                        f"Aux load '{nid}' has a non-numeric {key}.", node_id=nid))


def validate_graph(diagram: dict, db) -> list[GraphIssue]:
    """Check a drawn diagram against the topology contract of this module.

    Returns every problem found (empty list = the drawing can be solved). The
    checks run in dependency order — structure, then the single POC/busbar, then
    connectivity, then roles, edges and block properties — and stop early only
    when what follows would be meaningless (no POC to root the walk at, for
    instance), so the user is never shown a cascade of derived errors.
    """
    issues: list[GraphIssue] = []
    parsed = _parse_structure(diagram, issues)
    if parsed is None:
        return issues
    nodes, edges = parsed

    poc_id = _singleton(nodes, "poc", issues, "no_poc", "multiple_poc",
                        "Point of Connection")
    busbar_id = _singleton(nodes, "busbar", issues, "no_busbar", "multiple_busbar",
                           "MV busbar")
    if poc_id is None or busbar_id is None:
        return issues

    tree = _root_tree(nodes, edges, poc_id)
    for edge in tree.extra_edges:
        issues.append(GraphIssue(
            "cycle",
            f"Cable '{edge['id']}' closes a loop — MV circuits must be radial.",
            edge_id=edge["id"]))
    for nid in nodes:
        if nid not in tree.reached:
            issues.append(GraphIssue(
                "disconnected",
                f"Block '{nid}' is not connected to the Point of Connection.",
                node_id=nid))
    if busbar_id not in tree.reached:
        return issues  # nothing downstream can be judged

    _check_roles(nodes, tree, poc_id, busbar_id, issues)
    _check_edges(diagram, nodes, tree, edges, db, issues)
    _check_props(nodes, tree, db, diagram, issues)
    return issues


# --- diagram -> engine inputs ------------------------------------------------

@dataclass
class GraphInputs:
    """Everything the engine needs to solve a drawing, plus the canvas ids that
    every result maps back to.

    The parallel lists/dicts are the bijection: ``circuits[c][k]`` is the
    transformer of ``station_ids[c][k]``, and the cable feeding it is
    ``segment_edge_ids[(c + 1, k + 1)]`` (1-based keys, the engine's segment
    convention: segment 1 = the trunk from the busbar).
    """

    # canvas identity
    poc_id: str
    busbar_id: str
    hv_tx_id: str | None
    aux_ids: list[str]
    export_edge_id: str | None
    station_ids: list[list[str]]
    segment_edge_ids: dict[tuple[int, int], str]
    # POC target
    p_poc_kw: float
    pf_target: float
    # tier voltages
    v_lv_kv: float
    v_mv_kv: float
    v_hv_kv: float | None  # None = MV interconnection (no MV/HV transformer)
    # sizing rules
    max_utilization: float
    collection_loss_pct: float
    export_loss_pct_per_km: float
    max_circuit_current_a: float
    max_loading: float
    # drawn arrangement
    circuits: list[list[Transformer]]
    segment_lengths: dict[tuple[int, int], float]  # km, complete by construction
    segment_candidates: dict[tuple[int, int], list[Cable]]  # forced sections only
    # export step
    hv_mode: str  # "none" | "auto" | "model" | "custom"
    hv_transformer: Transformer | None  # None for "none" and "auto"
    hv_n_parallel: int
    export_length_km: float
    export_cable: Cable | None  # forced export section, if any
    # aux totals (taken at the MV busbar)
    aux_p_kw: float
    aux_q_kvar: float

    @property
    def fleet(self) -> list[tuple[Transformer, int]]:
        """(model, count) over every drawn station, first appearance first."""
        fleet: list[tuple[Transformer, int]] = []
        for tx in (t for circuit in self.circuits for t in circuit):
            for i, (known, count) in enumerate(fleet):
                if known == tx:
                    fleet[i] = (known, count + 1)
                    break
            else:
                fleet.append((tx, 1))
        return fleet

    @property
    def n_stations(self) -> int:
        return sum(len(c) for c in self.circuits)


def graph_to_inputs(diagram: dict, db) -> GraphInputs:
    """Read a VALID diagram into engine inputs.

    Call :func:`validate_graph` first: this function assumes the contract holds
    and does not re-report problems. Circuits are ordered by the order of their
    trunk edges in the diagram's edge list (the drawing's own order) and the
    stations inside a circuit follow the chain outward from the busbar —
    positions 0, 1, 2 ... map to segments 1, 2, 3 ...
    """
    nodes, edges = _parse_structure(diagram, [])
    poc_id = next(nid for nid, n in nodes.items() if n["kind"] == "poc")
    busbar_id = next(nid for nid, n in nodes.items() if n["kind"] == "busbar")
    tree = _root_tree(nodes, edges, poc_id)

    v_lv = _tier_kv(diagram, "lv")
    v_mv = _tier_kv(diagram, "mv")
    v_hv = _tier_kv(diagram, "hv")

    # Export step: the block hanging off the POC is either the MV/HV transformer
    # (HV interconnection) or the busbar itself (MV interconnection).
    poc_child, export_edge = tree.children[poc_id][0]
    hv_tx_id = poc_child if nodes[poc_child]["kind"] == "hv_tx" else None
    hv_mode = "none"
    hv_transformer = None
    hv_n_parallel = 1
    if hv_tx_id is not None:
        props = _props(nodes[hv_tx_id])
        hv_mode = props.get("mode") or "auto"
        hv_transformer = _hv_transformer(nodes[hv_tx_id], db, v_hv, v_mv)
        hv_n_parallel = int(_num(props.get("n_parallel", 1)) or 1)
    export_length_km = _length_km(export_edge) or 0.0
    export_sizing = _dict(export_edge.get("sizing"))
    export_cable = (db.cables.get(export_sizing.get("cable"))
                    if export_sizing.get("mode") == "forced" else None)

    # Circuits: one per station hanging off the busbar, walked outward.
    circuits: list[list[Transformer]] = []
    station_ids: list[list[str]] = []
    segment_edge_ids: dict[tuple[int, int], str] = {}
    segment_lengths: dict[tuple[int, int], float] = {}
    segment_candidates: dict[tuple[int, int], list[Cable]] = {}
    aux_ids: list[str] = []
    aux_p_kw = aux_q_kvar = 0.0

    for child, edge in tree.children[busbar_id]:
        if nodes[child]["kind"] == "aux":
            props = _props(nodes[child])
            aux_ids.append(child)
            aux_p_kw += _num(props.get("p_kw", 0.0)) or 0.0
            aux_q_kvar += _num(props.get("q_kvar", 0.0)) or 0.0
            continue
        c_idx = len(circuits) + 1
        transformers: list[Transformer] = []
        ids: list[str] = []
        node_id, segment_edge = child, edge
        while True:
            k = len(transformers) + 1
            transformers.append(_station_transformer(nodes[node_id], db, v_mv, v_lv))
            ids.append(node_id)
            segment_edge_ids[(c_idx, k)] = segment_edge["id"]
            segment_lengths[(c_idx, k)] = _length_km(segment_edge)
            sizing = _dict(segment_edge.get("sizing"))
            if sizing.get("mode") == "forced":
                # A forced section is a one-cable catalogue: select_cable still
                # escalates parallel circuits, but never swaps the section.
                segment_candidates[(c_idx, k)] = [db.cables[sizing["cable"]]]
            downstream = [(n, e) for n, e in tree.children[node_id]
                          if nodes[n]["kind"] == "station"]
            if not downstream:
                break
            node_id, segment_edge = downstream[0]
        circuits.append(transformers)
        station_ids.append(ids)

    return GraphInputs(
        poc_id=poc_id,
        busbar_id=busbar_id,
        hv_tx_id=hv_tx_id,
        aux_ids=aux_ids,
        export_edge_id=export_edge["id"],
        station_ids=station_ids,
        segment_edge_ids=segment_edge_ids,
        p_poc_kw=(_num(_props(nodes[poc_id]).get("p_target_mw")) or 0.0) * 1000.0,
        pf_target=_num(_props(nodes[poc_id]).get("pf")) or 1.0,
        v_lv_kv=v_lv,
        v_mv_kv=v_mv,
        v_hv_kv=v_hv if hv_tx_id is not None else None,
        max_utilization=_rule(diagram, "max_utilization"),
        collection_loss_pct=_rule(diagram, "collection_loss_pct"),
        export_loss_pct_per_km=_rule(diagram, "export_loss_pct_per_km"),
        max_circuit_current_a=_rule(diagram, "max_circuit_current_a"),
        max_loading=_rule(diagram, "max_loading"),
        circuits=circuits,
        segment_lengths=segment_lengths,
        segment_candidates=segment_candidates,
        hv_mode=hv_mode,
        hv_transformer=hv_transformer,
        hv_n_parallel=hv_n_parallel,
        export_length_km=export_length_km,
        export_cable=export_cable,
        aux_p_kw=aux_p_kw,
        aux_q_kvar=aux_q_kvar,
    )


# --- engine results -> canvas ------------------------------------------------

def _segment_payload(segment, forced: bool) -> dict:
    selection = segment.selection
    return {
        "cable": selection.cable.name if selection else None,
        "cable_label": segment.cable_label,
        "n_parallel": selection.n_parallel if selection else 0,
        "forced": forced,
        "sized": selection is not None,
        "length_m": segment.length_km * 1000.0,
        "p_kw": segment.p_kw,
        "q_kvar": segment.q_kvar,
        "s_kva": segment.s_kva,
        "dp_kw": segment.dp_kw,
        "dq_series_kvar": segment.dq_series_kvar,
        "q_charging_kvar": segment.q_charging_kvar,
        "current_a": selection.current_per_circuit_a if selection else None,
        "utilization": selection.utilization if selection else None,
        "loss_percent": selection.loss_percent if selection else None,
        "vdrop_percent": selection.vdrop_percent if selection else None,
    }


def map_results(inputs: GraphInputs, stage1: SizingResult,
                arch: PlantArchitecture) -> dict:
    """Key the engine results back to the canvas: ``{edges, nodes, summary,
    warnings}``, all plain JSON-able values.

    The mapping is purely positional (see the module docstring): circuit c,
    segment k of the architecture belongs to ``segment_edge_ids[(c, k)]`` and
    station position k - 1 to ``station_ids[c - 1][k - 1]``. Warnings are the
    engine's own flags — over-current circuits, an overloaded fleet, a failed
    power balance — re-pointed at the block or cable that shows them, so the
    editor can highlight the drawing instead of printing a note.
    """
    layout = arch.layout
    edges: dict[str, dict] = {}
    nodes: dict[str, dict] = {}
    warnings: list[GraphIssue] = []

    for circuit, plans, ids in zip(arch.circuits, layout.circuit_plans,
                                   inputs.station_ids):
        for segment in circuit.segments:
            key = (circuit.index, segment.index)
            edge_id = inputs.segment_edge_ids[key]
            edges[edge_id] = _segment_payload(
                segment, forced=key in inputs.segment_candidates)
        for station, plan, node_id in zip(circuit.stations, plans, ids):
            nodes[node_id] = {
                "kind": "station",
                "circuit": circuit.index,
                "position": station.index,
                "model": station.model,
                "s_rated_kva": station.s_rated_kva,
                "loading": station.loading,
                "p_lv_kw": station.p_lv_kw,
                "q_lv_kvar": station.q_lv_kvar,
                "s_lv_kva": station.s_lv_kva,
                "dp_tx_kw": station.dp_tx_kw,
                "dq_tx_kvar": station.dq_tx_kvar,
                "p_mv_kw": station.p_mv_kw,
                "q_mv_kvar": station.q_mv_kvar,
                "s_mv_kva": station.s_mv_kva,
                "i_a": plan.i_a,
            }
        if not circuit.current_ok:
            warnings.append(GraphIssue(
                "circuit_over_current",
                f"Circuit {circuit.index} draws {circuit.i_trunk_a:,.0f} A, above "
                f"the {layout.max_circuit_current_a:,.0f} A planning cap — move a "
                f"station to another circuit or raise the cap.",
                edge_id=inputs.segment_edge_ids[(circuit.index, 1)]))

    p_busbar = sum(c.p_busbar_kw for c in arch.circuits)
    q_busbar = sum(c.q_busbar_kvar for c in arch.circuits)
    nodes[inputs.busbar_id] = {
        "kind": "busbar",
        "p_kw": p_busbar,
        "q_kvar": q_busbar,
        "s_kva": math.hypot(p_busbar, q_busbar),
        "n_circuits": arch.n_circuits,
        "circuit_sizes": layout.circuit_sizes,
        "v_kv": layout.v_mv_kv,
    }
    for aux_id in inputs.aux_ids:
        nodes[aux_id] = {"kind": "aux"}
    if inputs.aux_ids:
        # The engine takes one lumped aux draw at the busbar; report the total
        # on the first aux block so the canvas has somewhere to show it.
        nodes[inputs.aux_ids[0]].update(p_kw=arch.aux_p_kw, q_kvar=arch.aux_q_kvar)

    export = arch.export
    if inputs.hv_tx_id is not None and export is not None:
        hv = export.hv_transformer
        nodes[inputs.hv_tx_id] = {
            "kind": "hv_tx",
            "mode": inputs.hv_mode,
            "name": hv.name if hv else None,
            "s_rated_kva": hv.s_rated_kva if hv else None,
            "n_parallel": export.hv_n_parallel,
            "s_through_kva": export.s_tx_through_kva,
            "dp_kw": export.dp_tx_kw,
            "dq_kvar": export.dq_tx_kvar,
            "v_hv_kv": export.v_hv_kv,
        }
    if inputs.export_edge_id is not None and inputs.export_length_km > 0:
        if export is not None and export.hv_cable is not None:
            edges[inputs.export_edge_id] = _segment_payload(
                export.hv_cable, forced=inputs.export_cable is not None)

    nodes[inputs.poc_id] = {
        "kind": "poc",
        "p_target_kw": inputs.p_poc_kw,
        "pf_target": inputs.pf_target,
        "p_delivered_kw": arch.p_poc_delivered_kw,
        "q_delivered_kvar": arch.q_poc_delivered_kvar,
        "p_refined_delivered_kw": arch.p_poc_refined_delivered_kw,
        "meets_target": (arch.p_poc_refined_delivered_kw is None
                         or arch.p_poc_refined_delivered_kw >= inputs.p_poc_kw - 1e-6),
    }

    if not layout.loading_ok:
        warnings.append(GraphIssue(
            "fleet_overloaded",
            f"The drawn stations carry {layout.fleet_loading * 100:.0f} % of their "
            f"combined rating — the required inverter power exceeds the installed "
            f"station capacity. Add stations or pick bigger units.",
            node_id=inputs.busbar_id))
    if not arch.power_balance_ok:
        warnings.append(GraphIssue(
            "power_balance",
            "Internal power-balance check failed — the results are not trustworthy.",
            node_id=inputs.busbar_id))
    if (export is not None and export.hv_cable is not None
            and not export.hv_cable_sized):
        warnings.append(GraphIssue(
            "hv_cable_not_sized",
            "The catalogue has no cables at the export voltage — the export span "
            "is shown but not sized (zero losses assumed).",
            edge_id=inputs.export_edge_id))

    p_inv_refined = arch.p_inv_refined_kw
    summary = {
        "p_inv_kw": stage1.p_inv_kw,
        "q_inv_kvar": stage1.q_inv_kvar,
        "s_inv_kva": stage1.s_inv_kva,
        "pf_inv": stage1.pf_inv,
        "p_inv_refined_kw": p_inv_refined,
        "q_inv_refined_kvar": arch.q_inv_refined_kvar,
        "s_inv_refined_kva": arch.s_inv_refined_kva,
        "correction_factor": arch.correction_factor,
        "p_poc_target_kw": arch.p_poc_target_kw,
        "p_poc_delivered_kw": arch.p_poc_delivered_kw,
        "q_poc_delivered_kvar": arch.q_poc_delivered_kvar,
        "p_poc_refined_delivered_kw": arch.p_poc_refined_delivered_kw,
        "n_stations": layout.n_transformers,
        "n_circuits": arch.n_circuits,
        "circuit_sizes": layout.circuit_sizes,
        "s_fleet_kva": layout.s_fleet_kva,
        "fleet_loading": layout.fleet_loading,
        "loading_ok": layout.loading_ok,
        "total_cable_loss_kw": arch.total_cable_loss_kw,
        "total_transformer_loss_kw": arch.total_transformer_loss_kw,
        "total_active_loss_kw": arch.total_active_loss_kw,
        "loss_percent_of_p_inv": (arch.total_active_loss_kw / p_inv_refined * 100.0
                                  if p_inv_refined else None),
        "worst_trunk_current_a": max((c.i_trunk_a for c in arch.circuits), default=0.0),
        "max_circuit_current_a": layout.max_circuit_current_a,
        "all_current_ok": arch.all_current_ok,
        "power_balance_ok": arch.power_balance_ok,
        "v_mv_kv": layout.v_mv_kv,
        "v_hv_kv": export.v_hv_kv if export is not None else None,
    }

    return {
        "edges": edges,
        "nodes": nodes,
        "summary": summary,
        "warnings": [w.as_dict() for w in warnings],
    }
