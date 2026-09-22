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

This ticket (01) draws a single-busbar PV plant with an HV interconnection:
the grid-side chain, the busbar, and every circuit as a column of stations in
chain order. Labels are tags only (``TS1…``, ``C1…``, ``BB1``); figure labels,
the legend, † notes, multi-busbar/BESS/hybrid plants and MV interconnection
all land in later tickets. :func:`sld_sheets` still returns a ``list[Sheet]``
(one per busbar) and every element carries a ``labels`` field, so those land
without reshaping this module.
"""

from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Layout model
# ---------------------------------------------------------------------------


@dataclass
class SldElement:
    """One symbol on a sheet.

    ``x``/``y`` are layout-space coordinates (arbitrary units, not points):
    the renderer fits the whole sheet's bounding box to the page. ``labels``
    holds every line of text tagged onto this element — in this ticket, just
    its tag (TS/C/BB) when it has one; figure labels (ticket 02) append more
    lines later without changing the field's shape.
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


# The grid-side chain, POC to busbar, in drawing order (ticket 01: HV
# interconnection only — see the ValueError below for what else is deferred).
_CHAIN_KINDS = [
    "poc", "metering", "disconnector", "hv_breaker", "hv_transformer",
    "export_cable", "mv_breaker",
]

_CHAIN_STEP = 70.0
# Wide enough that a station's transformer+inverter branch (see _BRANCH_DX,
# reaching ~50 units to the right at scale 1) never nears the next circuit's
# trunk line.
_CIRCUIT_DX = 170.0
_FEEDER_GAP = 55.0
_STATION_DY = 60.0


def sld_sheets(arch: PlantArchitecture, fleets: list[dict] | None = None) -> list[Sheet]:
    """Build one :class:`Sheet` per busbar from a solved plant architecture.

    ``fleets`` (the same per-fleet reporting dicts :mod:`powertool.pdf_report`
    receives) is accepted for interface stability with later tickets; this
    ticket does not use it, since every label is a tag.

    Out of this ticket's scope — more than one fleet (hybrid), more than one
    busbar, a non-PV fleet (BESS), or an MV interconnection (no HV
    transformer) — raises ``ValueError`` with a message naming what is
    unsupported, so the caller can turn it into a 400 rather than draw
    something wrong.
    """
    if len(arch.branches) != 1:
        raise ValueError(
            "SLD export supports a single-fleet plant in this release "
            "(hybrid plants are not yet supported)."
        )
    branch = arch.branches[0]
    if any(st.kind != "pv" for c in branch.circuits for st in c.stations):
        raise ValueError(
            "SLD export supports PV plants only in this release "
            "(BESS is not yet supported)."
        )
    if len(branch.sections) != 1:
        raise ValueError(
            "SLD export supports a single busbar in this release "
            "(multi-busbar plants are not yet supported)."
        )
    if arch.export is None or arch.export.hv_transformer is None:
        raise ValueError(
            "SLD export supports an HV interconnection in this release "
            "(MV interconnection is not yet supported)."
        )

    section = branch.sections[0]
    by_index = {c.index: c for c in branch.circuits}
    circuits = [by_index[i] for i in section.circuit_indices]

    elements: list[SldElement] = []
    connections: list[SldConnection] = []

    # --- grid-side chain: POC at the top, down to the busbar -------------
    y = 0.0
    prev_id: str | None = None
    for kind in _CHAIN_KINDS:
        eid = f"chain_{kind}"
        elements.append(SldElement(id=eid, kind=kind, x=0.0, y=y))
        if prev_id is not None:
            connections.append(SldConnection(prev_id, eid))
        prev_id = eid
        y -= _CHAIN_STEP

    busbar_tag = "BB1"
    busbar_id = "busbar"
    busbar_y = y
    elements.append(SldElement(
        id=busbar_id, kind="busbar", x=0.0, y=busbar_y,
        tag=busbar_tag, labels=[busbar_tag],
    ))
    connections.append(SldConnection(prev_id, busbar_id))

    # --- circuits: vertical columns hanging from the busbar ---------------
    n_circuits = len(circuits)
    x_start = -(n_circuits - 1) * _CIRCUIT_DX / 2.0
    ts_counter = 0
    for i, circuit in enumerate(circuits):
        c_tag = f"C{i + 1}"
        x = x_start + i * _CIRCUIT_DX
        feeder_id = f"feeder_{circuit.index}"
        feeder_y = busbar_y - _FEEDER_GAP
        elements.append(SldElement(
            id=feeder_id, kind="feeder_breaker", x=x, y=feeder_y,
            tag=c_tag, labels=[c_tag],
        ))
        connections.append(SldConnection(busbar_id, feeder_id))

        prev_station_id = feeder_id
        # Position 1 is nearest the busbar (StationResult.index), the chain
        # order this ticket draws top (busbar) to bottom (far station).
        for station in sorted(circuit.stations, key=lambda s: s.index):
            ts_counter += 1
            ts_tag = f"TS{ts_counter}"
            st_id = f"station_{circuit.index}_{station.index}"
            st_y = feeder_y - station.index * _STATION_DY
            elements.append(SldElement(
                id=st_id, kind="station", x=x, y=st_y,
                tag=ts_tag, labels=[ts_tag],
            ))
            connections.append(SldConnection(prev_station_id, st_id))
            prev_station_id = st_id

    return [Sheet(busbar_tag=busbar_tag, elements=elements, connections=connections)]


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


def _station_symbols(px: float, py: float, scale: float) -> list:
    """One station's symbols. The load-break switch sits ON the vertical MV
    trunk, in line with the cable running station to station — a circuit is
    a daisy chain THROUGH each station's own MV switchgear. The transformer
    (two overlapping circles) and the single inverter symbol branch OFF that
    point on a short tee to the side, ending at the inverter: a station taps
    the chain, it is never wired in series with the next station's transformer
    or inverter (see the spec's circuit convention)."""
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
    content_bottom = _MARGIN + 6 * mm

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
        drawing.add(String(right + 4, by - 3, busbar.tag or "", fontSize=8,
                           fontName="Helvetica-Bold", fillColor=_INK))

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
        if e.kind == "station":
            for shape in _station_symbols(px, py, scale):
                drawing.add(shape)
        else:
            for shape in _symbol(e.kind, px, py, scale):
                drawing.add(shape)
            caption = _KIND_CAPTION.get(e.kind)
            if caption:
                drawing.add(String(px + 10, py - 3, caption, fontName="Helvetica",
                                   fontSize=6.2, fillColor=_MUTED))
        if e.tag:
            # A station's symbols branch to the RIGHT of its trunk point (see
            # _station_symbols), so its tag sits to the left instead, clear of
            # the transformer/inverter — every other tagged element (feeder,
            # busbar) keeps the original placement to its lower-right.
            if e.kind == "station":
                drawing.add(String(px - 8, py + 9, e.tag, fontSize=7,
                                   fontName="Helvetica-Bold", fillColor=_INK,
                                   textAnchor="end"))
            else:
                drawing.add(String(px + 10, py - 12, e.tag, fontSize=7,
                                   fontName="Helvetica-Bold", fillColor=_INK))

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
