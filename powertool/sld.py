"""Single-line diagram (SLD) export — an IEC-style drawing of the *solved*
plant, generated from the sizing result rather than the canvas.

Two layers, mirroring :mod:`powertool.pdf_report`'s split between content and
presentation:

  1. A pure **layout model** (:func:`sld_sheets`): every decision — which
     symbols exist, their tags, their order, which sheet they land on — comes
     from here. Nothing below this layer decides anything; it only draws.
  2. A thin **renderer** (:func:`sheet_to_drawing`) turning one :class:`Sheet`
     into a ReportLab ``Drawing`` (vector graphics, so it stays sharp when
     scaled — standalone PDF today, embedded in the sizing report later).

``build_sld_pdf`` assembles one A3-landscape page per sheet.

One sheet per busbar, for every topology the tool solves: several busbars
per fleet, PV and BESS fleets (a hybrid's shared POC and HV transformer repeat
on each sheet), and HV or MV interconnection. Each sheet draws the grid-side
chain, the busbar, and every circuit as a column of stations in chain order,
labelled with the sized figures — POC voltage/MW, HV transformer model/MVA,
busbar voltage, each feeder's switchgear rated current, every cable segment's
size/material/parallel-run/length, each station's transformer model/kVA and
its inverter count (PV) or PCS count and battery MWh (BESS) — plus a symbol
legend, the indicative-protection note, and † marks (with sheet-level notes)
on any value that rests on an engine fallback.

Model names on the drawing are always CATALOGUE MODEL KEYS (``Transformer.name``
/ the inverter's ``PvInverter.name``), never the display labels
(``StationResult.model``, ``PvInverter.display_name``) used elsewhere.

``fleets`` is the same per-branch records :func:`powertool.graph.
branches_summary` builds for the PDF report — the caller (``backend.solve.
sld_pdf``) calls that function and merges in two extra keys of its own on a
LOCAL copy (:func:`powertool.graph.sld_fleets`, kept separate from
``branches_summary`` because that function's own shape is pinned by the
golden snapshot): ``pv_inverter_model`` (catalogue key),
``pv_inverter_count`` and ``bess_stations`` — diagram-layer information
``PlantArchitecture`` itself does not carry (Stage 1 only knows aggregate
conversion power).
``fleets[i]["busbars"][j]["feeder_switchgear_pins_a"]`` (present already in
``branches_summary``'s own shape) supplies a user-pinned feeder rating, read
the same way :func:`powertool.pdf_report._busbar_switchgear_rows` does, so
the drawing never disagrees with the report. Without ``fleets`` (or without
these keys) a station's inverter/PCS/battery lines are simply omitted and every feeder
reads as sized (never pinned) — the rest of the drawing still builds, which
keeps every engine-level (diagram-free) test fixture working.

† marking: driven by the same two engine fallbacks
:func:`powertool.graph.fallback_notices` reports — a station's transformer
whose RMU switchgear rating is unpublished (``Transformer.
switchgear_rating_published`` False, defaulting to
``DEFAULT_SWITCHGEAR_RATED_CURRENT_A``) marks that STATION's own tag (never
the feeder: the feeder is busbar switchgear, a different piece of equipment,
sized off the ladder or the engineer's own pin — see ``busbar_switchgear_
rating`` — never a value this module assumes); one whose cable entry is
unpublished (``Transformer.cable_entry_published`` False) marks that
station's own circuit segment. Both list their reason in the sheet's
``notes``, worded like the graph module's notices but naming catalogue keys
(this module stays independent of :mod:`powertool.graph`, so it derives the
same fallback facts straight off ``PlantArchitecture`` rather
than importing that function).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .architecture import PlantArchitecture
from .sizing import _MATERIAL_SYMBOL
from .components import (
    DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE,
    DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2,
    DEFAULT_SWITCHGEAR_RATED_CURRENT_A,
    busbar_switchgear_rating,
)

_INDICATIVE_NOTE = (
    "Protection devices are indicative; the tool does not size them."
)

# Legend caption per symbol kind — only the kinds a given sheet actually uses
# are listed (:func:`sld_sheets` builds each sheet's own subset), one entry
# PER SYMBOL: hv_breaker/mv_breaker/feeder_breaker draw the identical IEC
# breaker square regardless of which role they sit in, so they share one
# "Circuit breaker" caption rather than three near-duplicate entries (the
# legend is built by dedup-on-caption — see ``sld_sheets``' ``_add_legend``).
_LEGEND_LABEL = {
    "poc": "Point of connection",
    "metering": "Metering",
    "disconnector": "Disconnector",
    "hv_breaker": "Circuit breaker",
    "mv_breaker": "Circuit breaker",
    "feeder_breaker": "Circuit breaker",
    "hv_transformer": "HV transformer",
    "busbar": "Busbar",
    "station": "Transformer station",
    "bess_station": "BESS station (transformer, PCS, battery)",
    "cable_label": "Cable (drawn as the connecting line)",
}

# ---------------------------------------------------------------------------
# Layout model
# ---------------------------------------------------------------------------


@dataclass
class SldElement:
    """One symbol on a sheet.

    ``x``/``y`` are layout-space coordinates (arbitrary units, not points):
    the renderer fits the whole sheet's bounding box to the page. ``labels``
    holds every line of text tagged onto this element: its tag (TS/C/BB) when
    it has one, plus the sized figures (voltage, MVA/kVA, rated current,
    cable size/length, inverter count/model — see the module docstring).
    """

    id: str
    kind: str
    x: float
    y: float
    tag: str | None = None
    labels: list[str] = field(default_factory=list)


@dataclass
class SldConnection:
    """One drawn line between two elements, by id."""

    from_id: str
    to_id: str


@dataclass
class Sheet:
    """One busbar's complete SLD sheet."""

    busbar_tag: str
    elements: list[SldElement] = field(default_factory=list)
    connections: list[SldConnection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    legend: list[tuple[str, str]] = field(default_factory=list)
    continuation: str | None = None
    scale: float = 1.0


# The grid-side chain, POC to busbar, in drawing order: with an HV
# transformer, and for an MV interconnection (no HV transformer).
_HV_CHAIN_KINDS = [
    "poc", "metering", "disconnector", "hv_breaker", "hv_transformer",
    "export_cable", "mv_breaker",
]
_MV_CHAIN_KINDS = ["poc", "metering", "mv_breaker", "export_cable"]

# Kept tight (vs. ticket 01's 70/55) so the fixed A3 sheet spends more of its
# vertical budget on station rows, where ticket 02's figure labels now live —
# the grid-side chain is 7 fixed steps regardless of plant size, while a
# circuit's station count is not.
_CHAIN_STEP = 42.0
# Wide enough that a station's transformer+inverter branch (see _BRANCH_DX,
# reaching ~50 units to the right at scale 1) and its figure labels never
# reach the next circuit's trunk line.
_CIRCUIT_DX = 170.0
_FEEDER_GAP = 38.0
_STATION_DY = 60.0


def _cable_lines(segment, *, assumed: bool) -> list[str]:
    """Size, material and parallel-run count (already combined in
    ``cable_label``) plus length — every cable segment's label (stories 20,
    26; export spans and circuit segments alike)."""
    suffix = "†" if assumed else ""
    sel = segment.selection
    if sel is None or sel.cable.cross_section_mm2 is None:
        text = segment.cable_label  # unsized ("catalogue pending") keeps its own wording
    else:
        material = _MATERIAL_SYMBOL.get((sel.cable.material or "").lower(), sel.cable.material or "?")
        text = f"{material} 3×{sel.cable.cross_section_mm2:g} mm²"
        if sel.n_parallel > 1:
            text = f"{sel.n_parallel} × {text}"
    return [f"{text}{suffix}", f"{segment.length_km:g} km"]


def sld_sheets(arch: PlantArchitecture, fleets: list[dict] | None = None) -> list[Sheet]:
    """Build one :class:`Sheet` per busbar from a solved plant architecture,
    in plant order: fleet (branch) by fleet, each fleet's busbars in drawn
    order. BB, C and TS tags are numbered plant-wide in that same order
    (busbar → circuit → position), so they continue across sheets.

    Every sheet carries the whole grid-side chain up to the POC, so a hybrid's
    shared POC and HV transformer repeat on each fleet's sheets.

    ``fleets`` — one dict per branch, the shape :func:`powertool.graph.
    branches_summary` returns (optionally with :func:`powertool.graph.
    sld_fleets`' keys merged in — see the module docstring) — supplies
    the PV inverter model/count, each BESS station's PCS count and MWh
    (``bess_stations``) and any pinned feeder rating
    (``fleets[i]["busbars"][j]["feeder_switchgear_pins_a"]``). Omit it, or
    omit those keys, and those lines are left off and every feeder reads as
    sized.
    """
    sheets: list[Sheet] = []
    counters = {"BB": 0, "C": 0, "TS": 0}
    for b_i, branch in enumerate(arch.branches):
        fleet = fleets[b_i] if fleets and b_i < len(fleets) else {}
        for s_i, section in enumerate(branch.sections):
            sheets.append(_busbar_sheet(arch, branch, section, fleet, s_i, counters))
    return sheets


def _busbar_sheet(arch: PlantArchitecture, branch, section, fleet: dict, s_i: int,
                  counters: dict[str, int]) -> Sheet:
    """One busbar's sheet; ``counters`` carries the plant-wide tag numbering
    from one sheet to the next."""
    by_index = {c.index: c for c in branch.circuits}
    circuits = [by_index[i] for i in section.circuit_indices]
    export = arch.export
    hv_tx = export.hv_transformer if export is not None else None
    if hv_tx is not None:
        chain_kinds = _HV_CHAIN_KINDS
        poc_kv = export.v_hv_kv
        export_segment = export.hv_cable
    else:
        # MV interconnection: this busbar's own MV export run when it has one
        # (several busbars), else the plant's single shared export run.
        chain_kinds = _MV_CHAIN_KINDS
        poc_kv = section.v_mv_kv
        export_segment = section.mv_export or (export.hv_cable if export is not None else None)

    inverter_model = fleet.get("pv_inverter_model")
    inverter_count = fleet.get("pv_inverter_count")
    bess_stations = fleet.get("bess_stations") or []
    # This busbar's own feeder pins, in the busbar's own circuit order — the
    # same records powertool.pdf_report._busbar_switchgear_rows reads, so a
    # user-pinned feeder rating draws exactly what the report shows (never
    # re-derived from the ladder alone).
    busbars = fleet.get("busbars") or []
    feeder_pins = busbars[s_i].get("feeder_switchgear_pins_a") if s_i < len(busbars) else None

    # † notes list only what appears on THIS sheet (the spec's "on the sheet
    # it appears on"), so the fallback models come from this busbar's own
    # stations, not the whole fleet.
    plans_on_sheet = [p for c in circuits for p in branch.layout.circuit_plans[c.index - 1]]
    defaulted_switchgear = {p.transformer.name for p in plans_on_sheet
                            if not p.transformer.switchgear_rating_published}
    defaulted_cable_entry = {p.transformer.name for p in plans_on_sheet
                             if not p.transformer.cable_entry_published}

    notes: list[str] = [_INDICATIVE_NOTE]
    if defaulted_switchgear:
        names = ", ".join(sorted(defaulted_switchgear))
        notes.append(
            f"No switchgear rated current is published for {names} — the "
            f"stations marked † use the standard "
            f"{DEFAULT_SWITCHGEAR_RATED_CURRENT_A:,.0f} A ring main unit "
            f"rating."
        )
    if defaulted_cable_entry:
        names = ", ".join(sorted(defaulted_cable_entry))
        notes.append(
            f"No cable entry is published for {names} — the cable segment(s) "
            f"marked † use the standard {DEFAULT_CABLE_ENTRY_CABLES_PER_PHASE} x "
            f"{DEFAULT_CABLE_ENTRY_MAX_CROSS_SECTION_MM2:.0f} mm^2 cable entry "
            f"for those stations' circuit cables."
        )

    elements: list[SldElement] = []
    connections: list[SldConnection] = []
    legend_kinds: list[str] = []
    legend_captions_seen: set[str] = set()

    def _add_legend(kind: str) -> None:
        # Dedup on the CAPTION, not the kind: several kinds draw the same
        # symbol (every breaker role) and must collapse to one legend entry.
        caption = _LEGEND_LABEL.get(kind, kind)
        if caption not in legend_captions_seen:
            legend_captions_seen.add(caption)
            legend_kinds.append(kind)

    # --- grid-side chain: POC at the top, down to the busbar -------------
    y = 0.0
    prev_id: str | None = None
    for kind in chain_kinds:
        eid = f"chain_{kind}"
        labels: list[str] = []
        if kind == "poc":
            mw = arch.p_poc_delivered_kw / 1000.0
            labels = [f"{poc_kv:g} kV", f"{mw:.2f} MW"]
        elif kind == "hv_transformer":
            mva = hv_tx.s_rated_kva_at_40c / 1000.0
            labels = [hv_tx.name, f"{mva:.1f} MVA"]
        elif kind == "export_cable" and export_segment is not None:
            labels = _cable_lines(export_segment, assumed=False)
        elements.append(SldElement(id=eid, kind=kind, x=0.0, y=y, labels=labels))
        if kind != "export_cable":  # a cable span has no discrete symbol
            _add_legend(kind)
        if prev_id is not None:
            connections.append(SldConnection(prev_id, eid))
        prev_id = eid
        y -= _CHAIN_STEP

    counters["BB"] += 1
    busbar_tag = f"BB{counters['BB']}"
    busbar_id = "busbar"
    busbar_y = y
    elements.append(SldElement(
        id=busbar_id, kind="busbar", x=0.0, y=busbar_y,
        tag=busbar_tag, labels=[busbar_tag, f"{section.v_mv_kv:g} kV"],
    ))
    _add_legend("busbar")
    connections.append(SldConnection(prev_id, busbar_id))

    # --- circuits: vertical columns hanging from the busbar ---------------
    n_circuits = len(circuits)
    x_start = -(n_circuits - 1) * _CIRCUIT_DX / 2.0
    for i, circuit in enumerate(circuits):
        counters["C"] += 1
        c_tag = f"C{counters['C']}"
        x = x_start + i * _CIRCUIT_DX
        feeder_id = f"feeder_{circuit.index}"
        feeder_y = busbar_y - _FEEDER_GAP

        plans = branch.layout.circuit_plans[circuit.index - 1]
        # The feeder is BUSBAR switchgear, sized off the ladder (or the
        # engineer's own pin, checked rather than resized) — never a value
        # this module assumes, so it never carries a † (see fix note below
        # for where the RMU switchgear fallback actually lands).
        pin = feeder_pins[i] if feeder_pins and i < len(feeder_pins) else None
        rating_a = busbar_switchgear_rating(circuit.i_trunk_a, pin)
        if rating_a is None:
            rating_line = f"not sized — {circuit.i_trunk_a:,.0f} A"
        else:
            rating_line = f"{rating_a:,.0f} A"
        elements.append(SldElement(
            id=feeder_id, kind="feeder_breaker", x=x, y=feeder_y,
            tag=c_tag, labels=[c_tag, rating_line],
        ))
        _add_legend("feeder_breaker")
        connections.append(SldConnection(busbar_id, feeder_id))

        # Segments share their circuit's own order with its stations (index 1
        # = trunk, nearest the busbar) — see CircuitResult's docstring.
        segments_by_station_index = {
            k: seg for k, seg in enumerate(circuit.segments, start=1)
        }
        bess_row = (bess_stations[circuit.index - 1]
                    if circuit.index - 1 < len(bess_stations) else [])

        prev_station_id = feeder_id
        prev_y = feeder_y
        # Position 1 is nearest the busbar (StationResult.index), the chain
        # order this ticket draws top (busbar) to bottom (far station).
        for station, plan in zip(circuit.stations, plans):
            counters["TS"] += 1
            ts_tag = f"TS{counters['TS']}"
            st_id = f"station_{circuit.index}_{station.index}"
            st_y = feeder_y - station.index * _STATION_DY

            # The RMU switchgear fallback is the STATION's own assumed rated
            # current (never the feeder — that's busbar switchgear, sized off
            # the ladder/pin above) — so the † lands on the station itself,
            # on its displayed tag line (the canonical ``.tag`` stays bare,
            # for cross-referencing — "TS3 on C2" — per the SLD spec).
            station_assumed = plan.transformer.name in defaulted_switchgear
            tag_line = f"{ts_tag}†" if station_assumed else ts_tag
            labels = [tag_line, plan.transformer.name, f"{station.s_rated_kva:,.0f} kVA"]
            if station.kind == "bess":
                st_kind = "bess_station"
                bess = bess_row[station.index - 1] if station.index - 1 < len(bess_row) else None
                if bess is not None:
                    labels += [f"× {bess['pcs_count']} {bess['pcs_model']}",
                               f"{bess['battery_mwh']:.2f} MWh"]
            else:
                st_kind = "station"
                if inverter_model:
                    labels.append(f"× {inverter_count} {inverter_model}")
            elements.append(SldElement(
                id=st_id, kind=st_kind, x=x, y=st_y,
                tag=ts_tag, labels=labels,
            ))
            _add_legend(st_kind)
            connections.append(SldConnection(prev_station_id, st_id))

            segment = segments_by_station_index.get(station.index)
            if segment is not None:
                seg_assumed = plan.transformer.name in defaulted_cable_entry
                seg_id = f"segment_{circuit.index}_{station.index}"
                # Offset to the LEFT of the trunk line (the station's own
                # transformer/inverter branch extends right, see
                # _station_symbols), on the span this segment actually covers.
                elements.append(SldElement(
                    id=seg_id, kind="cable_label", x=x - 10.0, y=(st_y + prev_y) / 2.0,
                    labels=_cable_lines(segment, assumed=seg_assumed),
                ))

            prev_station_id = st_id
            prev_y = st_y

    return Sheet(
        busbar_tag=busbar_tag, elements=elements, connections=connections,
        notes=notes, legend=[(k, _LEGEND_LABEL.get(k, k)) for k in legend_kinds],
    )


# ---------------------------------------------------------------------------
# Renderer: Sheet -> ReportLab Drawing
# ---------------------------------------------------------------------------

_PAGE_SIZE = landscape(A3)
_MARGIN = 10 * mm
_TITLE_H = 28 * mm  # fits five lines when the project name is present
_STAMP_H = 9 * mm
_INK = colors.HexColor("#1a2333")
_STAMP_RED = colors.HexColor("#c1121f")
_MUTED = colors.HexColor("#6b7688")

_KIND_CAPTION = {
    "poc": "POC",
    "metering": "Metering",
    "disconnector": "Disconnector",
    "hv_breaker": "HV breaker",
    "hv_transformer": "HV transformer",
    "mv_breaker": "MV incomer breaker",
}


def _symbol(kind: str, px: float, py: float, scale: float) -> list:
    """The small IEC-60617-style shapes for one grid-side/busbar-feeder
    element, centred on (px, py). Deliberately simple line-art, per the
    spec's "drawn simply" — this is a preliminary drawing, not a CAD export.
    """
    r = 6.0 * min(scale, 1.4)
    shapes: list = []
    if kind == "poc":
        shapes.append(Circle(px, py, r, strokeColor=_INK, fillColor=None, strokeWidth=1.2))
        for dx in (-r * 0.6, 0, r * 0.6):
            shapes.append(Line(px + dx, py - r, px + dx, py - r * 2.0,
                               strokeColor=_INK, strokeWidth=1.0))
    elif kind == "metering":
        shapes.append(Circle(px, py, r, strokeColor=_INK, fillColor=None, strokeWidth=1.2))
        shapes.append(String(px, py - 3, "M", fontName="Helvetica", fontSize=7,
                             fillColor=_INK, textAnchor="middle"))
    elif kind == "disconnector":
        shapes.append(Line(px - r, py - r, px + r, py + r,
                           strokeColor=_INK, strokeWidth=1.4))
        shapes.append(Circle(px - r, py - r, 1.2, strokeColor=_INK, fillColor=_INK))
    elif kind in ("hv_breaker", "mv_breaker", "feeder_breaker"):
        s = r * 0.9
        shapes.append(Rect(px - s / 2, py - s / 2, s, s,
                           strokeColor=_INK, fillColor=colors.white, strokeWidth=1.3))
    elif kind == "hv_transformer":
        shapes.append(Circle(px, py - r * 0.5, r, strokeColor=_INK, fillColor=None,
                             strokeWidth=1.2))
        shapes.append(Circle(px, py + r * 0.5, r, strokeColor=_INK, fillColor=None,
                             strokeWidth=1.2))
    elif kind == "busbar":
        pass  # drawn as a thick line by the caller, not a point symbol
    return shapes


# Data-space reach of a station's transformer+inverter branch off the MV
# trunk — kept well inside half of _CIRCUIT_DX so a circuit's branches never
# reach its neighbour's trunk line (see the layout constants above).
_BRANCH_DX = 26.0


_LABEL_SIZE = 5.4
_LABEL_PITCH = 6.2  # pt between stacked label lines — tight but legible


def _draw_label_block(drawing: Drawing, x: float, y: float, lines: list[str], *,
                      anchor: str = "start", bold_first: bool = False,
                      size: float = _LABEL_SIZE, color=None) -> None:
    """Stack ``lines`` downward from ``(x, y)``, one ``String`` per line."""
    ty = y
    for i, text in enumerate(lines):
        drawing.add(String(x, ty, text, textAnchor=anchor,
                           fontName="Helvetica-Bold" if (bold_first and i == 0) else "Helvetica",
                           fontSize=size, fillColor=color or _INK))
        ty -= _LABEL_PITCH


def _station_symbols(px: float, py: float, scale: float, labels: list[str],
                     battery: bool = False) -> list:
    """One station's symbols, plus its figure labels (model, kVA, inverter —
    everything in ``labels`` after the tag, which the caller draws
    separately). The load-break switch sits ON the vertical MV trunk, in
    line with the cable running station to station — a circuit is a daisy
    chain THROUGH each station's own MV switchgear. The transformer (two
    overlapping circles) and the single inverter symbol branch OFF that
    point on a short tee to the side, ending at the inverter: a station taps
    the chain, it is never wired in series with the next station's transformer
    or inverter (see the spec's circuit convention). The figure labels stack
    below the inverter, on the same right-hand side — clear of the trunk
    line and of the previous/next segment's cable label, which sit to the
    LEFT of the trunk (see ``sld_sheets``)."""
    r = 6.0 * min(scale, 1.4)
    branch = _BRANCH_DX * min(scale, 1.4)
    shapes: list = []

    # Load-break switch, in line with the vertical MV trunk — the trunk
    # itself is drawn separately as the station-to-station connection line.
    shapes.append(Line(px - r * 0.7, py - r * 0.7, px + r * 0.7, py + r * 0.7,
                       strokeColor=_INK, strokeWidth=1.3))
    shapes.append(Circle(px - r * 0.7, py - r * 0.7, 1.1, strokeColor=_INK,
                         fillColor=_INK))

    # Tee off the trunk to this station's transformer + inverter branch.
    bx = px + branch
    shapes.append(Line(px, py, bx, py, strokeColor=_INK, strokeWidth=1.0))

    tx_center = bx + r * 0.9
    shapes.append(Circle(tx_center - r * 0.5, py, r, strokeColor=_INK, fillColor=None,
                         strokeWidth=1.1))
    shapes.append(Circle(tx_center + r * 0.5, py, r, strokeColor=_INK, fillColor=None,
                         strokeWidth=1.1))

    inv_x = tx_center + r * 2.6
    s = r * 1.3
    shapes.append(Line(tx_center + r * 1.5, py, inv_x - s / 2, py,
                       strokeColor=_INK, strokeWidth=1.0))
    shapes.append(Rect(inv_x - s / 2, py - s / 2, s, s, strokeColor=_INK,
                       fillColor=colors.white, strokeWidth=1.1))
    shapes.append(Line(inv_x - s / 2, py - s / 2, inv_x + s / 2, py + s / 2,
                       strokeColor=_INK, strokeWidth=0.8))
    shapes.append(String(inv_x, py - s * 1.3, "~/=", fontName="Helvetica",
                         fontSize=5, fillColor=_MUTED, textAnchor="middle"))
    if battery:
        # A BESS station's DC side: the IEC battery cell (long and short
        # plates) beyond the PCS.
        bat_x = inv_x + s * 1.6
        shapes.append(Line(inv_x + s / 2, py, bat_x, py, strokeColor=_INK, strokeWidth=1.0))
        shapes.append(Line(bat_x, py - r, bat_x, py + r, strokeColor=_INK, strokeWidth=1.3))
        shapes.append(Line(bat_x + r * 0.5, py - r * 0.5, bat_x + r * 0.5, py + r * 0.5,
                           strokeColor=_INK, strokeWidth=2.2))
    ty = py - s * 1.3 - 7.5
    for text in labels:
        shapes.append(String(tx_center - r * 1.4, ty, text, textAnchor="start",
                             fontName="Helvetica", fontSize=_LABEL_SIZE, fillColor=_INK))
        ty -= _LABEL_PITCH
    return shapes


def _title_block(drawing: Drawing, width: float, height: float, *, project_name: str,
                 design_name: str, sheet: Sheet, generated_at: datetime) -> None:
    x0 = width - _MARGIN - 78 * mm
    y0 = height - _MARGIN - _TITLE_H
    w, h = 78 * mm, _TITLE_H
    drawing.add(Rect(x0, y0, w, h, strokeColor=_INK, fillColor=colors.white,
                     strokeWidth=1.0))
    lines = [
        (design_name or "Plant", 9.5, True),
        (project_name, 8.0, False) if project_name else None,
        (f"Sheet {sheet.busbar_tag} — Single-line diagram", 7.5, False),
        (generated_at.strftime("%Y-%m-%d"), 7.5, False),
        ("Generated by Power Simulation Tool", 6.8, False),
    ]
    ty = y0 + h - 7 * mm
    for line in lines:
        if line is None:
            continue
        text, size, bold = line
        drawing.add(String(x0 + 3 * mm, ty, text,
                           fontName="Helvetica-Bold" if bold else "Helvetica",
                           fontSize=size, fillColor=_INK))
        ty -= (size + 4)


def _stamp(drawing: Drawing, width: float, height: float) -> None:
    x0 = _MARGIN
    y0 = height - _MARGIN - _STAMP_H
    w = width - 2 * _MARGIN - 78 * mm - 4 * mm
    drawing.add(Rect(x0, y0, w, _STAMP_H, strokeColor=_STAMP_RED, fillColor=colors.white,
                     strokeWidth=1.4))
    drawing.add(String(x0 + w / 2, y0 + _STAMP_H / 2 - 3, "PRELIMINARY — NOT FOR CONSTRUCTION",
                       fontName="Helvetica-Bold", fontSize=11, fillColor=_STAMP_RED,
                       textAnchor="middle"))


_FOOTER_H = 34 * mm  # legend row(s) + wrapped notes, reserved below the diagram
_LEGEND_COL_W = 170.0
_LEGEND_ROW_H = 13.0


def _footer(drawing: Drawing, sheet: Sheet, x0: float, x1: float, y_top: float) -> None:
    """The legend and notes strip at the bottom of the sheet — every symbol
    kind the sheet actually used, plus every note (the indicative-protection
    note first, then any † fallback reasons), wrapped to the page width."""
    lx, ty = x0, y_top
    for kind, caption in sheet.legend:
        if lx + _LEGEND_COL_W > x1:
            lx = x0
            ty -= _LEGEND_ROW_H
        cx, cy = lx + 7, ty - 4
        if kind in ("station", "bess_station"):
            for shape in _station_symbols(cx - 4, cy, 0.5, [], battery=kind == "bess_station"):
                drawing.add(shape)
            text_x = cx + (42 if kind == "bess_station" else 34)
        elif kind == "busbar":
            drawing.add(Line(cx - 5, cy, cx + 5, cy, strokeColor=_INK, strokeWidth=2.2))
            text_x = cx + 10
        elif kind == "cable_label":
            drawing.add(Line(cx - 5, cy, cx + 5, cy, strokeColor=_INK, strokeWidth=1.0))
            text_x = cx + 10
        else:
            for shape in _symbol(kind, cx, cy, 0.5):
                drawing.add(shape)
            text_x = cx + 10
        drawing.add(String(text_x, cy - 2, caption, fontName="Helvetica",
                           fontSize=6.0, fillColor=_INK))
        lx += _LEGEND_COL_W
    ty -= _LEGEND_ROW_H + 3

    for note in sheet.notes:
        for line in textwrap.wrap(note, width=175) or [note]:
            drawing.add(String(x0, ty, line, fontName="Helvetica",
                               fontSize=6.2, fillColor=_MUTED))
            ty -= 7.5


def sheet_to_drawing(
    sheet: Sheet,
    *,
    project_name: str = "",
    design_name: str = "Plant",
    generated_at: datetime | None = None,
) -> Drawing:
    """Render one :class:`Sheet` as a full A3-landscape-page ``Drawing`` —
    frame, title block, stamp and every element/connection, fitted to the
    page. Vector throughout, so it stays sharp scaled down (report
    embedding, ticket 06) as well as printed full size."""
    width, height = _PAGE_SIZE
    when = generated_at or datetime.now()
    drawing = Drawing(width, height)
    drawing.add(Rect(_MARGIN, _MARGIN, width - 2 * _MARGIN, height - 2 * _MARGIN,
                     strokeColor=_INK, fillColor=None, strokeWidth=1.2))
    _title_block(drawing, width, height, project_name=project_name,
                design_name=design_name, sheet=sheet, generated_at=when)
    _stamp(drawing, width, height)

    content_left = _MARGIN + 6 * mm
    content_right = width - _MARGIN - 6 * mm
    content_top = height - _MARGIN - _TITLE_H - 6 * mm
    content_bottom = _MARGIN + 6 * mm + _FOOTER_H
    _footer(drawing, sheet, content_left, content_right, content_bottom - 8)

    if not sheet.elements:
        return drawing

    xs = [e.x for e in sheet.elements]
    ys = [e.y for e in sheet.elements]
    half_w = max(max(abs(min(xs)), abs(max(xs))), 1.0)
    # A station's own symbols (switch/transformer/inverter) extend below its
    # y — reserve room for that footprint so the lowest row is not clipped by
    # the frame.
    y_span = max(max(ys) - min(ys) + _STATION_DY, 1.0)
    avail_w = content_right - content_left
    avail_h = content_top - content_bottom
    scale = min(avail_w / 2 / half_w, avail_h / y_span, 1.4)
    scale = max(scale, 0.15)

    mid_x = (content_left + content_right) / 2.0
    top_y = max(ys)

    def to_page(x: float, y: float) -> tuple[float, float]:
        return mid_x + x * scale, content_top - (top_y - y) * scale

    by_id = {e.id: e for e in sheet.elements}

    # Busbar: one thick horizontal line spanning the feeders, drawn before
    # the other symbols so feeder lines land on top of it.
    busbar = next((e for e in sheet.elements if e.kind == "busbar"), None)
    if busbar is not None:
        feeder_xs = [to_page(e.x, e.y)[0] for e in sheet.elements if e.kind == "feeder_breaker"]
        bx, by = to_page(busbar.x, busbar.y)
        left = min(feeder_xs + [bx]) - 10
        right = max(feeder_xs + [bx]) + 10
        drawing.add(Line(left, by, right, by, strokeColor=_INK, strokeWidth=2.4))
        _draw_label_block(drawing, right + 4, by - 3, busbar.labels or [busbar.tag or ""],
                          bold_first=True, size=7.0)

    for conn in sheet.connections:
        src, dst = by_id[conn.from_id], by_id[conn.to_id]
        if src.kind == "busbar":
            x1, y1 = to_page(dst.x, src.y)
        else:
            x1, y1 = to_page(src.x, src.y)
        x2, y2 = to_page(dst.x, dst.y)
        drawing.add(Line(x1, y1, x2, y2, strokeColor=_INK, strokeWidth=1.0))

    for e in sheet.elements:
        if e.kind in ("busbar",):
            continue
        px, py = to_page(e.x, e.y)

        if e.kind == "cable_label":
            # No discrete symbol — just its figure lines, right-aligned so
            # they end clear of the trunk line they sit beside (see
            # ``sld_sheets``, which offsets this element to the LEFT of x).
            _draw_label_block(drawing, px, py + _LABEL_PITCH, e.labels,
                              anchor="end", size=_LABEL_SIZE, color=_MUTED)
            continue

        if e.kind in ("station", "bess_station"):
            # The tag sits to the upper-left of the switch, clear of the
            # transformer/inverter branch (which reaches to the right); the
            # rest of the labels (model, kVA, inverter) are drawn stacked
            # below the inverter symbol by _station_symbols itself, since
            # only it knows where that symbol landed. Draw labels[0], not the
            # canonical (always-bare) e.tag: sld_sheets appends † there for a
            # station on a switchgear-rating fallback.
            for shape in _station_symbols(px, py, scale, e.labels[1:],
                                          battery=e.kind == "bess_station"):
                drawing.add(shape)
            tag_text = e.labels[0] if e.labels else e.tag
            if tag_text:
                drawing.add(String(px - 8, py + 9, tag_text, fontSize=7,
                                   fontName="Helvetica-Bold", fillColor=_INK,
                                   textAnchor="end"))
            continue

        for shape in _symbol(e.kind, px, py, scale):
            drawing.add(shape)
        if e.labels:
            # For a feeder this list is [tag, rating] — the tag as the bold
            # first line IS its tag, so nothing further to draw. Every other
            # kind reaching here (the grid-side chain) carries no tag at all.
            _draw_label_block(drawing, px + 10, py - 3, e.labels, bold_first=True, size=6.0)
        else:
            caption = _KIND_CAPTION.get(e.kind)
            if caption:
                drawing.add(String(px + 10, py - 3, caption, fontName="Helvetica",
                                   fontSize=6.2, fillColor=_MUTED))

    return drawing


def build_sld_pdf(
    sheets: list[Sheet],
    *,
    project_name: str = "",
    design_name: str = "Plant",
    generated_at: datetime | None = None,
) -> bytes:
    """The standalone SLD PDF: one A3-landscape page per sheet."""
    when = generated_at or datetime.now()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=_PAGE_SIZE)
    for sheet in sheets:
        drawing = sheet_to_drawing(sheet, project_name=project_name,
                                   design_name=design_name, generated_at=when)
        renderPDF.draw(drawing, c, 0, 0)
        c.showPage()
    c.save()
    return buf.getvalue()
