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

One busbar per fleet kind ("pv" / "bess") is allowed, each parented by the
shared MV/HV transformer (or directly by the POC for an MV interconnection) —
a hybrid plant is two independent MV cascades sharing one export step. A
station's own fleet kind must agree with the busbar its circuit hangs from
(``busbar_kind_mismatch``); an aux load may hang from any busbar.

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


def _rule_opt(diagram: dict, key: str) -> float | None:
    """A rule's value as the design sets it, or None when it does not.

    Split out of :func:`_rule` for the rules that have no entry in
    ``DEFAULT_RULES`` because their fallback is another rule rather than a
    constant — the per-fleet maximum loadings.
    """
    rules = _dict(_dict(diagram.get("settings")).get("rules"))
    return _num(rules.get(key))


def _rule(diagram: dict, key: str) -> float:
    value = _rule_opt(diagram, key)
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


def _stations_under(nodes: dict[str, dict], edges: list[dict],
                    busbar_id: str) -> list[str]:
    """The stations reachable from a busbar through station-to-station links.

    Undirected on purpose: edges are drawn either way round and this runs
    before the tree is rooted, so it cannot lean on parentage.
    """
    found: list[str] = []
    seen = {busbar_id}
    frontier = [busbar_id]
    while frontier:
        current = frontier.pop()
        for edge in edges:
            for near, far in ((edge.get("source"), edge.get("target")),
                              (edge.get("target"), edge.get("source"))):
                if near != current or far in seen or far not in nodes:
                    continue
                if nodes[far]["kind"] != "station":
                    continue
                seen.add(far)
                found.append(far)
                frontier.append(far)
    return found


def _busbars(nodes: dict[str, dict], edges: list[dict],
             issues: list[GraphIssue]) -> dict[str, str]:
    """One busbar id per fleet kind ("pv" / "bess") — the relaxed single-busbar
    rule: a second busbar of a kind already seen is a ``duplicate_busbar``,
    naming the extra one and excluding it from the map, rather than the old
    plant-wide ``multiple_busbar``.

    The kind is the EFFECTIVE one (see :func:`_effective_busbar_kind`), not the
    declared one, so the slot a busbar occupies here is the same answer as the
    fleet it is later sized as. Reading the bare "pv" default instead would put
    a pre-hybrid BESS plant's undeclared busbar in the PV slot while
    :func:`graph_to_inputs` solved that same busbar as a BESS branch — and
    adding a PV busbar to upgrade that plant to a hybrid would come back as a
    duplicate of a busbar that is not PV at all.

    Station membership is walked over the raw edges rather than the rooted
    tree: this runs before the tree exists, because the tree needs a POC and
    this check gates it.
    """
    by_kind: dict[str, str] = {}
    for nid, node in nodes.items():
        if node["kind"] != "busbar":
            continue
        kind = _effective_busbar_kind(nodes, nid, _stations_under(nodes, edges, nid))
        if kind in by_kind:
            issues.append(GraphIssue(
                "duplicate_busbar",
                f"A {kind!r} MV busbar already exists — remove '{nid}'.",
                node_id=nid))
            continue
        by_kind[kind] = nid
    return by_kind


# --- validation --------------------------------------------------------------

def _effective_busbar_kind(nodes, busbar_id: str, station_ids) -> str:
    """The fleet kind a busbar actually stands for.

    An explicit ``fleet_kind`` on the busbar wins. Otherwise the busbar adopts
    the kind of the stations hanging from it — which is what makes every design
    saved before this ticket keep working: none of them declares a busbar kind,
    and a single-fleet BESS plant drawn under ticket 02 must still report its
    stations as BESS rather than silently reading as PV. Falling back to the
    bare ``"pv"`` default here instead would leave the fleet kind dead for
    exactly the designs it was introduced for.

    A busbar whose stations disagree among themselves has no single kind; "pv"
    is returned and the disagreement is reported per station by the caller.
    """
    props = _props(nodes[busbar_id])
    if "fleet_kind" in props:
        return _fleet_kind(props)
    kinds = {_fleet_kind(_props(nodes[sid])) for sid in station_ids}
    return kinds.pop() if len(kinds) == 1 else "pv"


def _busbar_of(nid: str, tree, kind_of) -> str | None:
    """Walk up from a station to the busbar its circuit hangs from, or None if
    the walk never reaches one (already reported elsewhere as bad_topology)."""
    current = nid
    while True:
        entry = tree.parent.get(current)
        if entry is None:
            return None
        parent_id = entry[0]
        if kind_of.get(parent_id) == "busbar":
            return parent_id
        current = parent_id


def _check_roles(nodes, tree, poc_id, busbar_ids, issues) -> None:
    """Every block must sit where its kind belongs on the POC-rooted tree."""
    kind_of = {nid: node["kind"] for nid, node in nodes.items()}

    def children(nid: str) -> list[str]:
        return [child for child, _ in tree.children.get(nid, [])]

    def parent(nid: str) -> str | None:
        entry = tree.parent.get(nid)
        return entry[0] if entry else None

    poc_children = children(poc_id)
    hv_children = [c for c in poc_children if kind_of.get(c) == "hv_tx"]
    busbar_children = [c for c in poc_children if kind_of.get(c) == "busbar"]
    other_children = [c for c in poc_children
                      if kind_of.get(c) not in ("hv_tx", "busbar")]
    if (not poc_children or other_children or len(hv_children) > 1
            or (hv_children and busbar_children)):
        issues.append(GraphIssue(
            "bad_topology",
            "The Point of Connection must connect to the MV/HV transformer, or "
            "directly to one or more MV busbars for an MV interconnection.",
            node_id=poc_id))

    for nid, kind in kind_of.items():
        if nid not in tree.reached or nid == poc_id:
            continue
        kids = children(nid)
        up = parent(nid)
        if kind == "hv_tx":
            if up != poc_id or not kids or any(kind_of[k] != "busbar" for k in kids):
                issues.append(GraphIssue(
                    "bad_topology",
                    "The MV/HV transformer must sit between the Point of "
                    "Connection and the MV busbar(s).", node_id=nid))
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
            busbar_of = _busbar_of(nid, tree, kind_of)
            if busbar_of is not None:
                # The busbar's EFFECTIVE kind, not its declared one: an
                # undeclared busbar adopts its stations' kind, so a legacy
                # single-fleet BESS plant validates and reports as BESS. The
                # rule still bites where it should — a busbar carrying both
                # kinds has no single kind, and every station that disagrees
                # with the majority reading is named.
                stations_here = [
                    k for k, kk in kind_of.items()
                    if kk == "station" and _busbar_of(k, tree, kind_of) == busbar_of
                ]
                busbar_kind = _effective_busbar_kind(nodes, busbar_of, stations_here)
                station_kind = _fleet_kind(_props(nodes[nid]))
                if station_kind != busbar_kind:
                    issues.append(GraphIssue(
                        "busbar_kind_mismatch",
                        f"Station '{nid}' is fleet kind {station_kind!r} but "
                        f"hangs from the {busbar_kind!r} busbar "
                        f"'{busbar_of}'.", node_id=nid))
        elif kind == "aux":
            if up not in busbar_ids or kids:
                issues.append(GraphIssue(
                    "bad_topology",
                    "An aux load attaches to an MV busbar and feeds nothing.",
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
            p_bess_mw = _num(props.get("p_target_bess_mw", 0.0))
            if p_bess_mw is None or p_bess_mw < 0:
                issues.append(GraphIssue(
                    "bad_props",
                    "The Point of Connection's BESS target (p_target_bess_mw) "
                    "must be a non-negative number.", node_id=nid))
            if "q_share_pv" in props:
                q_share = _num(props.get("q_share_pv"))
                if q_share is None or not 0.0 <= q_share <= 1.0:
                    issues.append(GraphIssue(
                        "bad_q_share",
                        "The Point of Connection's PV reactive share "
                        "(q_share_pv) must be between 0 and 1.", node_id=nid))
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
    busbars = _busbars(nodes, edges, issues)
    if not busbars:
        issues.append(GraphIssue("no_busbar", "The diagram needs an MV busbar."))
    if poc_id is None or not busbars:
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
    busbar_ids = set(busbars.values())
    if not (busbar_ids & tree.reached):
        return issues  # nothing downstream can be judged

    _check_roles(nodes, tree, poc_id, busbar_ids, issues)
    _check_edges(diagram, nodes, tree, edges, db, issues)
    _check_props(nodes, tree, db, diagram, issues)
    return issues


# --- diagram -> engine inputs ------------------------------------------------

@dataclass
class BranchInputs:
    """One fleet's branch of a drawing: its own busbar, circuits and totals —
    everything :func:`powertool.architecture.size_branch` and
    :func:`~powertool.architecture.arrange_plant_manual` need for that fleet's
    independent MV cascade.

    The parallel lists/dicts are the same positional bijection as before, now
    scoped to this branch: ``circuits[c][k]`` is the transformer of
    ``station_ids[c][k]``, and the cable feeding it is
    ``segment_edge_ids[(c + 1, k + 1)]``.

    ``p_poc_target_kw`` is this branch's OWN point-of-connection active target
    (the PV or BESS figure off the POC props), read at parse time — it drives
    both the active pro-rata split and this branch's own refinement compliance
    target (ticket-05 decision: each fleet complies with the POC
    independently). ``q_poc_target_kvar`` is a PLACEHOLDER at parse time
    (0.0): the reactive duty a branch is actually assigned can only be known
    once the shared export chain has been sized (it depends on the combined
    flow's own losses), so :func:`backend.solve.solve_architecture` fills in
    the real value after running step 1 of the solve order — see the reactive
    split there.
    """

    kind: str
    busbar_id: str
    aux_ids: list[str]
    circuits: list[list[Transformer]]
    station_ids: list[list[str]]
    segment_edge_ids: dict[tuple[int, int], str]
    segment_lengths: dict[tuple[int, int], float]  # km, complete by construction
    segment_candidates: dict[tuple[int, int], list[Cable]]  # forced sections only
    aux_p_kw: float
    aux_q_kvar: float
    max_loading: float
    p_poc_target_kw: float
    q_poc_target_kvar: float = 0.0

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


@dataclass
class GraphInputs:
    """Everything the engine needs to solve a drawing, plus the canvas ids that
    every result maps back to.

    Plant-level concerns — point of connection, HV/tier voltages, the shared
    export step, and the sizing rules — stay flat here. Everything specific to
    one fleet (busbar identity, circuits, station identities, segment data,
    auxiliary totals, maximum loading, that branch's own active/reactive
    target) lives on :class:`BranchInputs`, one per drawn busbar whose fleet
    has a positive active target — see ``branches``.

    ``busbar_id``, ``aux_ids``, ``circuits``, ``station_ids``,
    ``segment_edge_ids``, ``segment_lengths``, ``segment_candidates``,
    ``aux_p_kw``, ``aux_q_kvar``, ``max_loading``, ``fleet`` and
    ``n_stations`` are kept as FIRST-BRANCH properties, mirroring
    ``PlantArchitecture._sole_branch`` (raise rather than silently prefer the
    first once there is more than one branch) — so the result-mapping layer
    migrates incrementally instead of needing every caller rewritten at once.
    """

    # canvas identity
    poc_id: str
    hv_tx_id: str | None
    export_edge_id: str | None
    # POC target
    pf_target: float
    q_share_pv: float | None  # None = default to pro-rata by active power
    # tier voltages
    v_lv_kv: float
    v_mv_kv: float
    v_hv_kv: float | None  # None = MV interconnection (no MV/HV transformer)
    # sizing rules
    max_utilization: float
    collection_loss_pct: float
    export_loss_pct_per_km: float
    max_circuit_current_a: float
    # export step
    hv_mode: str  # "none" | "auto" | "model" | "custom"
    hv_transformer: Transformer | None  # None for "none" and "auto"
    hv_n_parallel: int
    export_length_km: float
    export_cable: Cable | None  # forced export section, if any
    # branches
    branches: list[BranchInputs]

    @property
    def p_poc_kw(self) -> float:
        """Combined active target across every branch — what the shared
        export chain is sized against (step 1 of the solve order; see
        :func:`backend.solve.solve_architecture`). For a single-fleet design
        this is exactly that fleet's own target, unchanged from before this
        ticket."""
        return sum(b.p_poc_target_kw for b in self.branches)

    @property
    def _sole_branch(self) -> BranchInputs:
        """The only branch, for the single-fleet compatibility properties.

        Raises rather than quietly preferring the first — see
        ``PlantArchitecture._sole_branch`` for the house rationale. A caller
        still reading these once a second branch exists would otherwise get
        one fleet's figures presented as the whole drawing."""
        if len(self.branches) != 1:
            raise ValueError(
                f"This is a single-fleet accessor, but the drawing has "
                f"{len(self.branches)} branches. Read `branches` instead."
            )
        return self.branches[0]

    @property
    def busbar_id(self) -> str:
        return self._sole_branch.busbar_id

    @property
    def aux_ids(self) -> list[str]:
        return self._sole_branch.aux_ids

    @property
    def circuits(self) -> list[list[Transformer]]:
        return self._sole_branch.circuits

    @property
    def station_ids(self) -> list[list[str]]:
        return self._sole_branch.station_ids

    @property
    def segment_edge_ids(self) -> dict[tuple[int, int], str]:
        return self._sole_branch.segment_edge_ids

    @property
    def segment_lengths(self) -> dict[tuple[int, int], float]:
        return self._sole_branch.segment_lengths

    @property
    def segment_candidates(self) -> dict[tuple[int, int], list[Cable]]:
        return self._sole_branch.segment_candidates

    @property
    def aux_p_kw(self) -> float:
        return self._sole_branch.aux_p_kw

    @property
    def aux_q_kvar(self) -> float:
        return self._sole_branch.aux_q_kvar

    @property
    def max_loading(self) -> float:
        return self._sole_branch.max_loading

    @property
    def fleet(self) -> list[tuple[Transformer, int]]:
        return self._sole_branch.fleet

    @property
    def n_stations(self) -> int:
        return self._sole_branch.n_stations


def graph_to_inputs(diagram: dict, db) -> GraphInputs:
    """Read a VALID diagram into engine inputs.

    Call :func:`validate_graph` first: this function assumes the contract holds
    and does not re-report problems. Circuits are ordered by the order of their
    trunk edges in the diagram's edge list (the drawing's own order) and the
    stations inside a circuit follow the chain outward from the busbar —
    positions 0, 1, 2 ... map to segments 1, 2, 3 ...

    One :class:`BranchInputs` is built per busbar whose fleet has a positive
    active target. A busbar whose fleet's target is zero (the default for
    ``p_target_bess_mw``) contributes NO branch at all — not an error, the
    topology gate this ticket is built around: the design solves as
    single-fleet even though the busbar, its stations and its aux load are
    genuinely drawn on the canvas.
    """
    nodes, edges = _parse_structure(diagram, [])
    poc_id = next(nid for nid, n in nodes.items() if n["kind"] == "poc")
    tree = _root_tree(nodes, edges, poc_id)

    v_lv = _tier_kv(diagram, "lv")
    v_mv = _tier_kv(diagram, "mv")
    v_hv = _tier_kv(diagram, "hv")

    # Export step: the block hanging off the POC is either the MV/HV transformer
    # (HV interconnection) or a busbar directly (MV interconnection). Every
    # busbar hangs off this same block — see the topology contract.
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

    poc_props = _props(nodes[poc_id])
    p_target_pv_kw = (_num(poc_props.get("p_target_mw")) or 0.0) * 1000.0
    p_target_bess_kw = (_num(poc_props.get("p_target_bess_mw", 0.0)) or 0.0) * 1000.0
    q_share_pv = _num(poc_props.get("q_share_pv"))
    # Maximum loading is per fleet kind, falling back to the plant-wide rule —
    # a BESS fleet is routinely held to a different loading limit than a PV one,
    # but a design that only ever set the one value must keep meaning what it
    # meant. `_rule` supplies the DEFAULT_RULES value when neither is present.
    def _max_loading(kind: str) -> float:
        per_kind = _rule_opt(diagram, f"max_loading_{kind}")
        return _rule(diagram, "max_loading") if per_kind is None else per_kind

    busbar_parent = hv_tx_id if hv_tx_id is not None else poc_id
    busbar_children = [child for child, _edge in tree.children[busbar_parent]
                       if nodes[child]["kind"] == "busbar"]

    branches: list[BranchInputs] = []
    for busbar_id in busbar_children:
        # The busbar's effective kind decides which point-of-connection target
        # this branch answers to, so the stations under it have to be known
        # before the branch is built — an undeclared busbar takes their kind.
        stations_under: list[str] = []
        frontier = [busbar_id]
        while frontier:
            for child, _edge in tree.children[frontier.pop()]:
                if nodes[child]["kind"] == "station":
                    stations_under.append(child)
                    frontier.append(child)
        kind = _effective_busbar_kind(nodes, busbar_id, stations_under)
        # `p_target_mw` is the PV figure only where there is a second fleet to
        # tell it apart from. A design with ONE busbar has a single target and
        # no ambiguity, whatever kind that fleet is — which is what keeps a
        # single-fleet BESS plant (ticket 02) solving off the target it
        # actually carries instead of looking for a BESS field it never wrote.
        if len(busbar_children) == 1:
            p_target_kw = p_target_pv_kw
        else:
            p_target_kw = p_target_bess_kw if kind == "bess" else p_target_pv_kw
        if p_target_kw <= 0:
            continue  # the topology gate: a zero-target busbar is no branch

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
                    # A forced section is a one-cable catalogue: select_cable
                    # still escalates parallel circuits, but never swaps the
                    # section.
                    segment_candidates[(c_idx, k)] = [db.cables[sizing["cable"]]]
                downstream = [(n, e) for n, e in tree.children[node_id]
                              if nodes[n]["kind"] == "station"]
                if not downstream:
                    break
                node_id, segment_edge = downstream[0]
            circuits.append(transformers)
            station_ids.append(ids)

        branches.append(BranchInputs(
            kind=kind,
            busbar_id=busbar_id,
            aux_ids=aux_ids,
            circuits=circuits,
            station_ids=station_ids,
            segment_edge_ids=segment_edge_ids,
            segment_lengths=segment_lengths,
            segment_candidates=segment_candidates,
            aux_p_kw=aux_p_kw,
            aux_q_kvar=aux_q_kvar,
            max_loading=_max_loading(kind),
            p_poc_target_kw=p_target_kw,
        ))

    return GraphInputs(
        poc_id=poc_id,
        hv_tx_id=hv_tx_id,
        export_edge_id=export_edge["id"],
        pf_target=_num(poc_props.get("pf")) or 1.0,
        q_share_pv=q_share_pv,
        v_lv_kv=v_lv,
        v_mv_kv=v_mv,
        v_hv_kv=v_hv if hv_tx_id is not None else None,
        max_utilization=_rule(diagram, "max_utilization"),
        collection_loss_pct=_rule(diagram, "collection_loss_pct"),
        export_loss_pct_per_km=_rule(diagram, "export_loss_pct_per_km"),
        max_circuit_current_a=_rule(diagram, "max_circuit_current_a"),
        hv_mode=hv_mode,
        hv_transformer=hv_transformer,
        hv_n_parallel=hv_n_parallel,
        export_length_km=export_length_km,
        export_cable=export_cable,
        branches=branches,
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


def map_results(inputs: GraphInputs, stage1s: list[SizingResult],
                arch: PlantArchitecture) -> dict:
    """Key the engine results back to the canvas: ``{edges, nodes, summary,
    warnings}``, all plain JSON-able values.

    ``stage1s`` carries one Stage-1 result per branch, same order as
    ``inputs.branches`` and ``arch.branches`` — the shape
    :func:`backend.solve.solve_architecture` returns.

    The mapping is purely positional (see the module docstring): circuit c,
    segment k of a branch's architecture belongs to that branch's
    ``segment_edge_ids[(c, k)]`` and station position k - 1 to
    ``station_ids[c - 1][k - 1]``. Warnings are the engine's own flags —
    over-current circuits, an overloaded fleet, a failed power balance —
    re-pointed at the block or cable that shows them, so the editor can
    highlight the drawing instead of printing a note.

    For a SINGLE-branch plant the summary payload is byte-identical to what it
    was before branches existed — the golden-snapshot physics gate depends on
    that. A multi-branch plant cannot reuse ``PlantArchitecture``'s sole-branch
    compatibility properties (they raise), so its summary carries plant-wide
    totals plus an additive ``branches`` list of each fleet's own figures,
    rather than reshaping the existing single-fleet keys.
    """
    edges: dict[str, dict] = {}
    nodes: dict[str, dict] = {}
    warnings: list[GraphIssue] = []

    for branch_inputs, branch_arch in zip(inputs.branches, arch.branches):
        layout = branch_arch.layout
        for circuit, plans, ids in zip(branch_arch.circuits, layout.circuit_plans,
                                       branch_inputs.station_ids):
            for segment in circuit.segments:
                key = (circuit.index, segment.index)
                edge_id = branch_inputs.segment_edge_ids[key]
                edges[edge_id] = _segment_payload(
                    segment, forced=key in branch_inputs.segment_candidates)
            for station, plan, node_id in zip(circuit.stations, plans, ids):
                nodes[node_id] = {
                    # "kind" is the CANVAS node type, the discriminator the
                    # editor keys every node payload on — it stays "station".
                    # The fleet the station belongs to is a separate axis and
                    # gets its own key; collapsing the two would leave the
                    # frontend unable to tell a station from a busbar.
                    "kind": "station",
                    "fleet_kind": station.kind,
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
                    edge_id=branch_inputs.segment_edge_ids[(circuit.index, 1)]))

        p_busbar = sum(c.p_busbar_kw for c in branch_arch.circuits)
        q_busbar = sum(c.q_busbar_kvar for c in branch_arch.circuits)
        nodes[branch_inputs.busbar_id] = {
            "kind": "busbar",
            "p_kw": p_busbar,
            "q_kvar": q_busbar,
            "s_kva": math.hypot(p_busbar, q_busbar),
            "n_circuits": len(branch_arch.circuits),
            "circuit_sizes": layout.circuit_sizes,
            "v_kv": layout.v_mv_kv,
        }
        for aux_id in branch_inputs.aux_ids:
            nodes[aux_id] = {"kind": "aux"}
        if branch_inputs.aux_ids:
            # The engine takes one lumped aux draw per branch busbar; report
            # the total on the branch's first aux block so the canvas has
            # somewhere to show it.
            nodes[branch_inputs.aux_ids[0]].update(
                p_kw=branch_arch.aux_p_kw, q_kvar=branch_arch.aux_q_kvar)

        if not layout.loading_ok:
            warnings.append(GraphIssue(
                "fleet_overloaded",
                f"The drawn stations carry {layout.fleet_loading * 100:.0f} % of their "
                f"combined rating — the required inverter power exceeds the installed "
                f"station capacity. Add stations or pick bigger units.",
                node_id=branch_inputs.busbar_id))

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

    if len(arch.branches) == 1:
        p_refined_delivered_kw = arch.p_poc_refined_delivered_kw
    else:
        refined = [r.p_poc_refined_delivered_kw for r in arch.branch_refinements]
        p_refined_delivered_kw = (
            sum(refined) if all(r is not None for r in refined) else None
        )
    nodes[inputs.poc_id] = {
        "kind": "poc",
        "p_target_kw": inputs.p_poc_kw,
        "pf_target": inputs.pf_target,
        "p_delivered_kw": arch.p_poc_delivered_kw,
        "q_delivered_kvar": arch.q_poc_delivered_kvar,
        "p_refined_delivered_kw": p_refined_delivered_kw,
        "meets_target": (p_refined_delivered_kw is None
                         or p_refined_delivered_kw >= inputs.p_poc_kw - 1e-6),
    }

    if not arch.power_balance_ok:
        warnings.append(GraphIssue(
            "power_balance",
            "Internal power-balance check failed — the results are not trustworthy.",
            node_id=(inputs.branches[0].busbar_id if inputs.branches
                     else inputs.poc_id)))
    if (export is not None and export.hv_cable is not None
            and not export.hv_cable_sized):
        warnings.append(GraphIssue(
            "hv_cable_not_sized",
            "The catalogue has no cables at the export voltage — the export span "
            "is shown but not sized (zero losses assumed).",
            edge_id=inputs.export_edge_id))

    if len(arch.branches) == 1:
        # Exactly the pre-branch computation, unchanged — the golden-snapshot
        # gate (a physics diff against the pre-refactor engine) depends on
        # this being byte-identical for every single-fleet design.
        layout = arch.layout
        stage1 = stage1s[0]
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
    else:
        branches_summary = []
        for branch_inputs, branch_arch, refinement, stage1 in zip(
            inputs.branches, arch.branches, arch.branch_refinements, stage1s
        ):
            branches_summary.append({
                "kind": branch_inputs.kind,
                "p_inv_kw": stage1.p_inv_kw,
                "q_inv_kvar": stage1.q_inv_kvar,
                "s_inv_kva": stage1.s_inv_kva,
                "pf_inv": stage1.pf_inv,
                "p_inv_refined_kw": refinement.p_inv_refined_kw,
                "q_inv_refined_kvar": refinement.q_inv_refined_kvar,
                "s_inv_refined_kva": refinement.s_inv_refined_kva,
                "correction_factor": refinement.correction_factor,
                "p_poc_target_kw": refinement.p_poc_target_kw,
                "p_poc_delivered_kw": refinement.p_poc_delivered_kw,
                "p_poc_refined_delivered_kw": refinement.p_poc_refined_delivered_kw,
                "n_stations": branch_arch.layout.n_transformers,
                "n_circuits": len(branch_arch.circuits),
                "circuit_sizes": branch_arch.layout.circuit_sizes,
                "s_fleet_kva": branch_arch.layout.s_fleet_kva,
                "fleet_loading": branch_arch.layout.fleet_loading,
                "loading_ok": branch_arch.layout.loading_ok,
            })
        n_stations = sum(b.layout.n_transformers for b in arch.branches)
        n_circuits = sum(len(b.circuits) for b in arch.branches)
        circuit_sizes = [n for b in arch.branches for n in b.layout.circuit_sizes]
        s_fleet_kva = sum(b.layout.s_fleet_kva for b in arch.branches)
        worst_trunk_current_a = max(
            (c.i_trunk_a for b in arch.branches for c in b.circuits), default=0.0)
        all_current_ok = all(c.current_ok for b in arch.branches for c in b.circuits)
        p_inv_refined_total = sum(r.p_inv_refined_kw for r in arch.branch_refinements)
        # PlantArchitecture.total_cable_loss_kw / total_transformer_loss_kw are
        # sole-branch compat properties (they read `self.circuits`) and raise
        # here — computed directly from every branch plus the shared export
        # step instead.
        total_cable_loss_kw = sum(
            seg.dp_kw for b in arch.branches for c in b.circuits for seg in c.segments
        )
        total_transformer_loss_kw = sum(
            st.dp_tx_kw for b in arch.branches for c in b.circuits for st in c.stations
        )
        if arch.export is not None:
            if arch.export.hv_cable is not None:
                total_cable_loss_kw += arch.export.hv_cable.dp_kw
            total_transformer_loss_kw += arch.export.dp_tx_kw
        total_active_loss_kw = total_cable_loss_kw + total_transformer_loss_kw
        summary = {
            "p_inv_kw": sum(s.p_inv_kw for s in stage1s),
            "q_inv_kvar": sum(s.q_inv_kvar for s in stage1s),
            "s_inv_kva": math.hypot(sum(s.p_inv_kw for s in stage1s),
                                    sum(s.q_inv_kvar for s in stage1s)),
            "p_poc_delivered_kw": arch.p_poc_delivered_kw,
            "q_poc_delivered_kvar": arch.q_poc_delivered_kvar,
            "p_poc_refined_delivered_kw": p_refined_delivered_kw,
            "n_stations": n_stations,
            "n_circuits": n_circuits,
            "circuit_sizes": circuit_sizes,
            "s_fleet_kva": s_fleet_kva,
            "total_cable_loss_kw": total_cable_loss_kw,
            "total_transformer_loss_kw": total_transformer_loss_kw,
            "total_active_loss_kw": total_active_loss_kw,
            "loss_percent_of_p_inv": (total_active_loss_kw / p_inv_refined_total * 100.0
                                      if p_inv_refined_total else None),
            "worst_trunk_current_a": worst_trunk_current_a,
            "max_circuit_current_a": max(b.layout.max_circuit_current_a
                                         for b in arch.branches),
            "all_current_ok": all_current_ok,
            "power_balance_ok": arch.power_balance_ok,
            "v_mv_kv": arch.branches[0].layout.v_mv_kv,
            "v_hv_kv": export.v_hv_kv if export is not None else None,
            "branches": branches_summary,
        }

    return {
        "edges": edges,
        "nodes": nodes,
        "summary": summary,
        "warnings": [w.as_dict() for w in warnings],
    }
