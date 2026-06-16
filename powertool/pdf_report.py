"""PDF sizing report — premium/minimal layout (RP Global brand colours).

Renders the same content as :mod:`powertool.report` (methodology + detailed loss
tables) as a styled PDF using ReportLab, so the download matches the look of the
app. Pure-Python: ReportLab needs no system libraries.

Math is presented as cleanly formatted text (Unicode + sub/superscripts) rather
than typeset LaTeX — readable and dependency-light. The prose explaining each
formula is kept faithful to ``report.py`` (the two are intended to stay in sync).
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .architecture import PlantArchitecture
from .sizing import SizingResult

# RP Global "Colour Codes" brand sheet.
_NAVY = colors.HexColor("#011d3f")   # Business Blue
_INK = colors.HexColor("#3b4a63")    # softened navy — body
_GREEN = colors.HexColor("#00a438")  # Energy Green
_LINE = colors.HexColor("#e6e8ed")   # Light Blue — hairlines
_TINT = colors.HexColor("#f4f6f9")   # very light row tint
_MUTED = colors.HexColor("#7c8aa0")

_MARGIN = 16 * mm
_USABLE_W = A4[0] - 2 * _MARGIN

# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------
_H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, textColor=_NAVY,
                     leading=26, spaceAfter=2)
_SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, textColor=_MUTED,
                      leading=12, spaceAfter=4)
_H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, textColor=_NAVY,
                     leading=18, spaceBefore=18, spaceAfter=6)
_H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, textColor=_NAVY,
                     leading=14, spaceBefore=12, spaceAfter=4)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=_INK,
                       leading=14, spaceAfter=6)
_EQ = ParagraphStyle("eq", fontName="Helvetica-Oblique", fontSize=9.5, textColor=_NAVY,
                     leading=15, alignment=TA_CENTER, backColor=_TINT,
                     borderColor=_LINE, borderWidth=0.5, borderPadding=7,
                     borderRadius=6, spaceBefore=4, spaceAfter=10)
_NOTE = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=8,
                       textColor=_MUTED, leading=11, spaceBefore=2, spaceAfter=4)
_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, textColor=_INK,
                       leading=9.5)
_CELL_H = ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=7.5,
                         textColor=colors.white, leading=9.5)


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"


def _table(headers: list[str], rows: list[list[str]],
           weights: list[float] | None = None) -> Table:
    """Styled table; cells are Paragraphs so long values wrap inside the page."""
    head = [Paragraph(h, _CELL_H) for h in headers]
    body = [[Paragraph(str(c), _CELL) for c in r] for r in rows]
    n = len(headers)
    w = weights or [1.0] * n
    scale = _USABLE_W / sum(w)
    col_w = [x * scale for x in w]
    t = Table([head] + body, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _TINT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ---------------------------------------------------------------------------
# Sections (mirrors powertool.report)
# ---------------------------------------------------------------------------
def _summary(stage1: SizingResult, arch: PlantArchitecture) -> list:
    export = arch.export
    if export is None:
        interconn = f"MV, at {arch.layout.v_mv_kv:g} kV busbar"
    else:
        hv = export.hv_transformer
        interconn = (f"HV, at {export.v_hv_kv:g} kV"
                     + (f" via {hv.s_rated_kva / 1000:g} MVA auto-sized MV/HV transformer"
                        if hv is not None else ""))
    target = arch.p_poc_target_kw
    rows = [
        ["POC active-power target", f"{_fmt(target / 1000)} MW" if target else "—"],
        ["Power-factor target (injected Q)", f"{stage1.pf_target:.3f}"],
        ["Interconnection", interconn],
        ["MV collection voltage", f"{arch.layout.v_mv_kv:g} kV"],
        ["Station fleet",
         " + ".join(f"{n}× {tx.display_name}" for tx, n in arch.layout.fleet)],
        ["Installed station capacity", f"{_fmt(arch.layout.s_fleet_kva / 1000)} MVA"],
    ]
    return [Paragraph("Plant summary", _H2), _table(["Item", "Value"], rows, [0.45, 0.55])]


def _methodology() -> list:
    f = []
    f.append(Paragraph("Methodology", _H2))

    f.append(Paragraph("Conventions and assumptions", _H3))
    f.append(Paragraph(
        "All quantities are three-phase, balanced, positive-sequence, RMS, "
        "steady-state. Voltages are line-to-line in kV; active power <i>P</i> in kW, "
        "reactive <i>Q</i> in kvar, apparent <i>S</i> in kVA. Line current for a "
        "section at voltage <i>V</i> is", _BODY))
    f.append(Paragraph("I = S / (&radic;3 · V)", _EQ))
    f.append(Paragraph(
        "<b>Worst-case reactive sign convention.</b> The plant is assumed to "
        "<i>inject</i> reactive power at the Point of Connection (POC) — the worst "
        "case for inverter sizing, because it maximises the reactive the inverters "
        "must produce. Every element's reactive contribution is its series loss only "
        "(kept &ge; 0). Cable capacitive charging is computed and reported for "
        "information but is <b>never</b> netted against the series reactive, which "
        "would optimistically under-size the inverters.", _BODY))

    f.append(Paragraph("Component loss models", _H3))
    f.append(Paragraph(
        "<b>Cable</b> (per section, length <i>L</i>, resistance <i>r</i> and "
        "reactance <i>x</i> per km, with <i>n</i> parallel circuits sharing the "
        "current):", _BODY))
    f.append(Paragraph(
        "&Delta;P = 3·I<super>2</super>·rL / n  [kW]<br/>"
        "&Delta;Q<sub>series</sub> = 3·I<super>2</super>·xL / n  [kvar]<br/>"
        "Q<sub>charging</sub> = n·V<super>2</super>·bL  [kvar]", _EQ))
    f.append(Paragraph(
        "<b>Transformer</b> (rated power <i>S</i><sub>r</sub>, short-circuit voltage "
        "<i>u</i><sub>k</sub>%, load loss <i>P</i><sub>k</sub>, no-load loss "
        "<i>P</i><sub>0</sub>, magnetising current <i>i</i><sub>0</sub>%):", _BODY))
    f.append(Paragraph(
        "&Delta;P = P<sub>k</sub>·(S/S<sub>r</sub>)<super>2</super> + P<sub>0</sub>"
        "&nbsp;&nbsp;&nbsp;&nbsp;"
        "&Delta;Q = (u<sub>x</sub>/100)·(S<super>2</super>/S<sub>r</sub>) + "
        "(i<sub>0</sub>/100)·S<sub>r</sub>", _EQ))
    f.append(Paragraph(
        "with the reactive part of the short-circuit voltage "
        "u<sub>x</sub> = &radic;(u<sub>k</sub><super>2</super> &minus; "
        "u<sub>r</sub><super>2</super>) and the resistive part "
        "u<sub>r</sub> = 100·P<sub>k</sub>/S<sub>r</sub>. A fleet of mixed parallel "
        "units shares the load at equal per-unit loading r = S/&Sigma;S<sub>r</sub> — "
        "each unit carries a share of <i>S</i> proportional to its rating — and the "
        "losses are summed.", _BODY))

    f.append(Paragraph("Stage 1 — Conceptual inverter sizing", _H3))
    f.append(Paragraph(
        "The electrical path from the POC to the inverter is walked <b>backward</b>, "
        "accumulating losses into a running (P, Q). Starting from the POC target and "
        "the reactive implied by the power-factor target, each element adds its "
        "losses, so the final (P, Q) is what the inverters must deliver. The MV/HV "
        "interconnection transformer is <b>sized automatically</b> (smallest "
        "IEC-preferred rating &ge; the plant apparent power).", _BODY))
    f.append(Paragraph(
        "<b>Worst-case cable sizing.</b> At the conceptual stage the collection cable "
        "lengths are unknown, so instead of assuming a length the tool assumes the "
        "cable consumes its <b>full admissible loss budget</b> (the most conservative "
        "case). The cross-section and number of parallel circuits are set by ampacity; "
        "the <i>implied</i> length — the length at which that cable exactly exhausts "
        "the budget — is reported. The export cable, whose length is known, is sized "
        "normally against its per-km budget.", _BODY))

    f.append(Paragraph("Stage 2 — Plant architecture", _H3))
    f.append(Paragraph(
        "The required inverter power is organised into the station fleet defined in "
        "Stage 1. Every station runs at the same per-unit loading, so its LV share is "
        "proportional to its rating; its MV-side output sets its current. Stations are "
        "grouped into MV collector circuits with the fewest circuits whose total "
        "current respects the per-feeder cap, balanced by a longest-processing-time "
        "heuristic; within each circuit the <b>biggest stations sit nearest the "
        "substation</b>, which minimises the power flowing through the long tail "
        "segments and therefore the cable losses.", _BODY))
    f.append(Paragraph(
        "Each daisy-chain segment is then sized <b>independently</b> for the "
        "cumulative power it actually carries, walking from the far station toward the "
        "substation and subtracting the losses consumed en route — the mirror image "
        "of the Stage-1 backward cascade.", _BODY))
    f.append(Paragraph(
        "<b>Refined inverter requirement (never fall short).</b> Because losses grow "
        "with the square of load, a single proportional correction would deliver "
        "slightly <i>under</i> target. Instead the inverter power is scaled by a "
        "factor iterated against the loss cascade — with the cable selections frozen "
        "so the discrete picks cannot flap — until the delivered POC power is at or "
        "above the target. Overshoot is curtailable; shortfall is not accepted.", _BODY))
    return f


def _stage1(stage1: SizingResult) -> list:
    f = [Paragraph("Stage 1 results — required inverter rating", _H2)]
    rows = [
        ["P at inverter", f"{_fmt(stage1.p_inv_kw / 1000)} MW"],
        ["Q at inverter", f"{_fmt(stage1.q_inv_kvar / 1000)} Mvar"],
        ["S at inverter", f"{_fmt(stage1.s_inv_kva / 1000)} MVA"],
        ["Power factor at inverter", f"{stage1.pf_inv:.3f}"],
        ["Total active losses (POC→inverter)",
         f"{stage1.total_active_loss_kw / stage1.p_inv_kw * 100:.2f}% of P_inv"],
        ["Power-balance check", "OK" if stage1.power_balance_ok else "FAILED"],
    ]
    f.append(_table(["Quantity", "Value"], rows, [0.45, 0.55]))
    f.append(Paragraph("Conceptual loss breakdown (POC → inverter)", _H3))
    headers = ["Element", "Type", "Selected cable", "Length [m]", "Util.",
               "Loss %", "V-drop %", "S [kVA]", "ΔP [% P_inv]", "ΔQ [kvar]"]
    trows = []
    for e in stage1.losses:
        trows.append([
            e.name, e.kind, e.cable_label or "—",
            f"{_fmt(e.length_km * 1000, 0)}" if e.length_km is not None else "—",
            f"{e.utilization * 100:.0f}%" if e.utilization is not None else "—",
            f"{e.loss_percent:.2f}" if e.loss_percent is not None else "—",
            f"{e.vdrop_percent:.2f}" if e.vdrop_percent is not None else "—",
            _fmt(e.s_through_kva, 1),
            f"{e.dp_kw / stage1.p_inv_kw * 100:.3f}%", _fmt(e.dq_kvar),
        ])
    f.append(_table(headers, trows, [1.5, 0.9, 1.5, 0.9, 0.7, 0.7, 0.8, 1.1, 0.9, 0.9]))
    f.append(Paragraph(
        "Worst-case cable lengths are IMPLIED — the length at which the selected cable "
        "exactly exhausts its loss budget; the export cable uses its real length.", _NOTE))
    return f


def _transformer_rows(arch: PlantArchitecture, p_inv: float):
    agg: dict[str, dict] = {}
    for circuit in arch.circuits:
        for st in circuit.stations:
            a = agg.setdefault(st.model, {
                "count": 0, "s_rated": st.s_rated_kva, "loading": st.loading,
                "dp": 0.0, "dq": 0.0, "s_lv": st.s_lv_kva,
            })
            a["count"] += 1
            a["dp"] += st.dp_tx_kw
            a["dq"] += st.dq_tx_kvar
    rows = []
    for model, a in sorted(agg.items(), key=lambda kv: -kv[1]["s_rated"]):
        rows.append([
            model, str(a["count"]), _fmt(a["s_rated"], 0), f"{a['loading'] * 100:.0f}%",
            _fmt(a["s_lv"], 1), f"{(a['dp'] / a['count']) / p_inv * 100:.3f}%",
            f"{a['dp'] / p_inv * 100:.3f}%", _fmt(a["dq"]),
        ])
    export = arch.export
    if export is not None and export.hv_transformer is not None:
        hv = export.hv_transformer
        loading = export.s_tx_through_kva / (hv.s_rated_kva * export.hv_n_parallel)
        rows.append([
            f"{hv.name} (MV/HV)", str(export.hv_n_parallel), _fmt(hv.s_rated_kva, 0),
            f"{loading * 100:.0f}%", _fmt(export.s_tx_through_kva, 1),
            f"{(export.dp_tx_kw / export.hv_n_parallel) / p_inv * 100:.3f}%",
            f"{export.dp_tx_kw / p_inv * 100:.3f}%", _fmt(export.dq_tx_kvar),
        ])
    return rows


def _cable_rows(arch: PlantArchitecture, p_inv: float):
    rows = []
    for circuit in arch.circuits:
        for seg in circuit.segments:
            sel = seg.selection
            rows.append([
                f"C{circuit.index}·S{seg.index}",
                circuit.stations[seg.index - 1].model,
                _fmt(seg.length_km * 1000, 0), _fmt(seg.s_kva, 1),
                seg.cable_label, str(sel.n_parallel),
                f"{sel.utilization * 100:.0f}%", f"{sel.loss_percent:.2f}",
                f"{sel.vdrop_percent:.2f}", f"{seg.dp_kw / p_inv * 100:.3f}%",
                _fmt(seg.dq_series_kvar), _fmt(seg.q_charging_kvar),
            ])
    export = arch.export
    if export is not None and export.hv_cable is not None:
        seg = export.hv_cable
        sel = seg.selection
        rows.append([
            "Export", "POC", _fmt(seg.length_km * 1000, 0), _fmt(seg.s_kva, 1),
            seg.cable_label, str(sel.n_parallel) if sel else "—",
            f"{sel.utilization * 100:.0f}%" if sel else "—",
            f"{sel.loss_percent:.2f}" if sel else "—",
            f"{sel.vdrop_percent:.2f}" if sel else "—",
            f"{seg.dp_kw / p_inv * 100:.3f}%", _fmt(seg.dq_series_kvar),
            _fmt(seg.q_charging_kvar),
        ])
    return rows


def _stage2(stage1: SizingResult, arch: PlantArchitecture) -> list:
    layout = arch.layout
    p_inv = arch.p_inv_refined_kw  # base for loss percentages (refined inverter power)
    f = [Paragraph("Stage 2 results — plant architecture", _H2)]
    rows = [
        ["LV/MV transformers", str(layout.n_transformers)],
        ["MV circuits", layout.circuit_sizes_label],
        ["Fleet loading", f"{layout.fleet_loading * 100:.0f}%"
         + ("" if layout.loading_ok else "  ⚠ fleet undersized")],
        ["Worst trunk current", f"{_fmt(max(c.i_trunk_a for c in arch.circuits), 0)} A"
         f" (cap {_fmt(layout.max_circuit_current_a, 0)} A)"],
        ["Total cable losses", f"{arch.total_cable_loss_kw / p_inv * 100:.2f}% of P_inv"],
        ["Total transformer losses",
         f"{arch.total_transformer_loss_kw / p_inv * 100:.2f}% of P_inv"],
        ["Total active losses", f"{arch.total_active_loss_kw / p_inv * 100:.2f}% of P_inv"],
        ["Power-balance check", "OK" if arch.power_balance_ok else "FAILED"],
    ]
    f.append(_table(["Quantity", "Value"], rows, [0.45, 0.55]))

    f.append(Paragraph("Refined inverter requirement", _H3))
    delta = (arch.s_inv_refined_kva / stage1.s_inv_kva - 1) * 100
    rrows = [
        ["S at inverter — Stage 1 (lumped)", f"{_fmt(stage1.s_inv_kva / 1000)} MVA"],
        ["S at inverter — refined",
         f"{_fmt(arch.s_inv_refined_kva / 1000)} MVA ({delta:+.2f}%)"],
        ["P / Q refined", f"{_fmt(arch.p_inv_refined_kw / 1000)} MW / "
         f"{_fmt(arch.q_inv_refined_kvar / 1000)} Mvar"],
    ]
    if arch.p_poc_refined_delivered_kw is not None and arch.p_poc_target_kw is not None:
        rrows.append([
            "POC delivered with refined S (≥ target by rule)",
            f"{_fmt(arch.p_poc_refined_delivered_kw / 1000)} MW "
            f"(target {_fmt(arch.p_poc_target_kw / 1000)} MW)"])
    f.append(_table(["Quantity", "Value"], rrows, [0.45, 0.55]))

    f.append(Paragraph("Transformer losses", _H3))
    f.append(_table(
        ["Transformer", "Units", "Rating [kVA]", "Loading", "S/unit [kVA]",
         "ΔP/unit [% P_inv]", "ΔP total [% P_inv]", "ΔQ total [kvar]"],
        _transformer_rows(arch, p_inv), [1.8, 0.7, 1.0, 0.8, 1.0, 1.0, 1.0, 1.0]))

    f.append(Paragraph("Cable-run losses", _H3))
    f.append(_table(
        ["Run", "Feeds", "Length [m]", "S [kVA]", "Selected cable", "Circuits",
         "Util.", "Loss %", "V-drop %", "ΔP [% P_inv]", "ΔQ ser [kvar]", "Q chg [kvar]"],
        _cable_rows(arch, p_inv),
        [0.8, 1.3, 0.85, 1.05, 1.5, 0.85, 0.7, 0.7, 0.8, 0.75, 0.9, 0.9]))
    f.append(Paragraph(
        "Segment 1 of each circuit is the trunk (substation side). Charging is "
        "reported for information and is never netted into the reactive (worst-case "
        "convention).", _NOTE))
    return f


def build_pdf_report(
    stage1: SizingResult,
    arch: PlantArchitecture,
    *,
    plant_name: str = "PV Plant",
    generated_at: datetime | None = None,
) -> bytes:
    """Full PDF sizing report: methodology + detailed loss tables. Returns bytes."""
    when = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"{plant_name} — Sizing Report",
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=14 * mm, bottomMargin=14 * mm)

    story: list = [
        Paragraph(f"{plant_name} — Sizing Report", _H1),
        Paragraph(f"Generated {when} · PV plant sizing tool", _SUB),
        HRFlowable(width="100%", thickness=2, color=_GREEN, spaceBefore=4,
                   spaceAfter=10),
    ]
    story += _summary(stage1, arch)
    story += _methodology()
    story += _stage1(stage1)
    story += _stage2(stage1, arch)
    story += [
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.5, color=_LINE, spaceAfter=6),
        Paragraph(
            "Component parameters come from data/*.yaml. Transformer load/no-load "
            "losses for the PV stations are design assumptions (the datasheets publish "
            "only impedance and an EN 50588-1 efficiency tier); see the catalogue "
            "comments for provenance.", _NOTE),
    ]
    doc.build(story)
    return buf.getvalue()
