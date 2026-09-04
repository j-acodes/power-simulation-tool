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
from .components import conversion_label, fleet_label
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
def _fleet_name(fleet: dict | None, n_fleets: int) -> str | None:
    """"PV fleet" / "BESS fleet" when a report covers more than one, else None.

    A single-fleet report keeps the headings it always had: naming the fleet is
    only informative when there is another one to tell it apart from, and a
    PV-only report must read exactly as it did before hybrids existed.

    The bare name is returned rather than a ready-made prefix, because the two
    call sites want it differently — one as a section heading of its own, one
    joined onto a row label — and a string shaped for one of them had to be
    reverse-parsed by the other.
    """
    if fleet is None or n_fleets < 2:
        return None
    return f"{fleet_label(fleet['kind'])} fleet"


def _fleet_kind(fleet: dict | None) -> str:
    return fleet["kind"] if fleet else "pv"


def _summary(stage1s: list[SizingResult], arch: PlantArchitecture,
             fleets: list[dict] | None) -> list:
    export = arch.export
    v_mv = arch.branches[0].layout.v_mv_kv
    if export is None:
        interconn = f"MV, at {v_mv:g} kV busbar"
    else:
        hv = export.hv_transformer
        interconn = (f"HV, at {export.v_hv_kv:g} kV"
                     + (f" via {hv.s_rated_kva / 1000:g} MVA auto-sized MV/HV transformer"
                        if hv is not None else ""))
    target = sum(r.p_poc_target_kw or 0.0 for r in arch.branch_refinements)
    rows = [
        ["POC active-power target", f"{_fmt(target / 1000)} MW" if target else "—"],
        ["Power-factor target (injected Q)", f"{stage1s[0].pf_target:.3f}"],
        ["Interconnection", interconn],
        ["MV collection voltage", f"{v_mv:g} kV"],
    ]
    # One fleet: the plant IS the fleet, so its figures belong in this table
    # exactly as they always did. More than one: they move into the per-fleet
    # sections, and merging them here would produce a station list belonging to
    # no fleet in particular.
    for i, branch in enumerate(arch.branches):
        name = _fleet_name(fleets[i] if fleets else None, len(arch.branches))
        prefix = f"{name} — " if name else ""
        rows.append([f"{prefix}Station fleet",
                     " + ".join(f"{n}× {tx.display_name}" for tx, n in branch.layout.fleet)])
        rows.append([f"{prefix}Installed station capacity",
                     f"{_fmt(branch.layout.s_fleet_kva / 1000)} MVA"])
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


def _stage1(stage1: SizingResult, fleet: dict | None, n_fleets: int) -> list:
    # "PCS" on a battery fleet, "inverter" on PV. The FIELDS are untouched —
    # p_inv_kw holds a PCS's converted power just as it holds an inverter's,
    # because it is the same quantity computed the same way. Only the word
    # changes, because a battery project's reviewer expects to read "PCS".
    device = conversion_label(_fleet_kind(fleet))
    name = _fleet_name(fleet, n_fleets)
    prefix = f"{name} — " if name else ""
    f = [Paragraph(f"{prefix}Stage 1 results — required {device} rating", _H2)]
    rows = [
        [f"P at {device}", f"{_fmt(stage1.p_inv_kw / 1000)} MW"],
        [f"Q at {device}", f"{_fmt(stage1.q_inv_kvar / 1000)} Mvar"],
        [f"S at {device}", f"{_fmt(stage1.s_inv_kva / 1000)} MVA"],
        [f"Power factor at {device}", f"{stage1.pf_inv:.3f}"],
        [f"Total active losses (POC→{device})",
         f"{stage1.total_active_loss_kw / stage1.p_inv_kw * 100:.2f}% of P_inv"],
        ["Power-balance check", "OK" if stage1.power_balance_ok else "FAILED"],
    ]
    f.append(_table(["Quantity", "Value"], rows, [0.45, 0.55]))
    f.append(Paragraph(f"Conceptual loss breakdown (POC → {device})", _H3))
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


def _transformer_rows(branch, export, p_inv: float, include_export: bool,
                      shared: bool):
    agg: dict[str, dict] = {}
    for circuit in branch.circuits:
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
    # The MV/HV transformer is shared by every fleet, so it is listed once — with
    # the last fleet in a hybrid, and with the only one otherwise. Repeating it
    # per fleet would double-count it to anyone adding the column up. The
    # annotation is only written where it is TRUE: on a single-fleet plant there
    # is nothing to share it with, and saying so would be both wrong and wider
    # than the column.
    if include_export and export is not None and export.hv_transformer is not None:
        hv = export.hv_transformer
        loading = export.s_tx_through_kva / (hv.s_rated_kva * export.hv_n_parallel)
        rows.append([
            f"{hv.name} (MV/HV{', shared' if shared else ''})",
            str(export.hv_n_parallel), _fmt(hv.s_rated_kva, 0),
            f"{loading * 100:.0f}%", _fmt(export.s_tx_through_kva, 1),
            f"{(export.dp_tx_kw / export.hv_n_parallel) / p_inv * 100:.3f}%",
            f"{export.dp_tx_kw / p_inv * 100:.3f}%", _fmt(export.dq_tx_kvar),
        ])
    return rows


def _cable_rows(branch, export, p_inv: float, include_export: bool,
                shared: bool):
    rows = []
    for circuit in branch.circuits:
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
    # Shared, like the MV/HV transformer above: listed once, not once per fleet,
    # and annotated only where there is in fact another fleet sharing it.
    if include_export and export is not None and export.hv_cable is not None:
        seg = export.hv_cable
        sel = seg.selection
        rows.append([
            "Export (shared)" if shared else "Export",
            "POC", _fmt(seg.length_km * 1000, 0), _fmt(seg.s_kva, 1),
            seg.cable_label, str(sel.n_parallel) if sel else "—",
            f"{sel.utilization * 100:.0f}%" if sel else "—",
            f"{sel.loss_percent:.2f}" if sel else "—",
            f"{sel.vdrop_percent:.2f}" if sel else "—",
            f"{seg.dp_kw / p_inv * 100:.3f}%", _fmt(seg.dq_series_kvar),
            _fmt(seg.q_charging_kvar),
        ])
    return rows


def _energy_rows(fleet: dict) -> list[list[str]]:
    """Containers and the delivered-energy verdict, for a BESS fleet.

    Container counts are the supplier's own figures, read from the solution's
    duration table — which is exactly why they belong in a document that has to
    stand on its own in a design review. The verdict is stated rather than left
    to be re-derived from the two energy figures beside it.
    """
    rows: list[list[str]] = []
    if fleet.get("containers") is not None:
        rows.append(["Containers", str(fleet["containers"])])
    delivered, required = fleet.get("e_delivered_kwh"), fleet.get("e_required_kwh")
    if delivered is not None and required is not None:
        verdict = "OK" if fleet.get("energy_ok") else f"SHORT by {_fmt((required - delivered) / 1000, 1)} MWh"
        rows.append(["Delivered energy",
                     f"{_fmt(delivered / 1000, 1)} MWh (needs {_fmt(required / 1000, 1)} MWh) — {verdict}"])
    aux_p = fleet.get("bess_aux_p_kw") or 0.0
    if aux_p:
        rows.append(["Container auxiliaries",
                     f"{_fmt(aux_p, 0)} kW / {_fmt(fleet.get('bess_aux_q_kvar') or 0.0, 0)} kvar"
                     " — separately supplied, not carried by the PCS"])
    return rows


def _stage2(stage1s: list[SizingResult], arch: PlantArchitecture,
            fleets: list[dict] | None) -> list:
    # Loss percentages are quoted against the whole plant's refined conversion
    # power, so the columns of a hybrid's two fleet tables share one base and
    # can be read against each other.
    p_inv = sum(r.p_inv_refined_kw for r in arch.branch_refinements)
    n = len(arch.branches)
    f = [Paragraph("Stage 2 results — plant architecture", _H2)]
    plant_rows = [
        ["Total cable losses", f"{arch_total(arch, 'cable') / p_inv * 100:.2f}% of P_inv"],
        ["Total transformer losses",
         f"{arch_total(arch, 'transformer') / p_inv * 100:.2f}% of P_inv"],
        ["Total active losses",
         f"{(arch_total(arch, 'cable') + arch_total(arch, 'transformer')) / p_inv * 100:.2f}% of P_inv"],
        ["Power-balance check", "OK" if arch.power_balance_ok else "FAILED"],
    ]
    # With one fleet the plant IS the fleet, so its figures and the plant totals
    # belong in ONE table, in the order they have always been in — a single-fleet
    # report must read exactly as it did before hybrids existed. Splitting them
    # only earns its keep when there are two fleets to keep apart.
    if n > 1:
        f.append(_table(["Quantity", "Value"], plant_rows, [0.45, 0.55]))

    for i, branch in enumerate(arch.branches):
        fleet = fleets[i] if fleets else None
        refinement = arch.branch_refinements[i]
        layout = branch.layout
        name = _fleet_name(fleet, n)
        device = conversion_label(_fleet_kind(fleet))
        if name:
            f.append(Paragraph(name, _H2))

        # The fleet's own maximum is worth stating only where there is a second
        # fleet held to a different one; on a single-fleet report it is noise
        # that was not there before.
        against_max = (f" (max {fleet['max_loading'] * 100:.0f}%)"
                       if n > 1 and fleet and fleet.get("max_loading") is not None else "")
        brows = [
            ["LV/MV transformers", str(layout.n_transformers)],
            ["MV circuits", layout.circuit_sizes_label],
            ["Fleet loading", f"{layout.fleet_loading * 100:.0f}%" + against_max
             + ("" if layout.loading_ok else "  ⚠ fleet undersized")],
            ["Worst trunk current",
             f"{_fmt(max(c.i_trunk_a for c in branch.circuits), 0)} A"
             f" (cap {_fmt(layout.max_circuit_current_a, 0)} A)"],
        ]
        if fleet:
            brows += _energy_rows(fleet)
        if n == 1:
            brows += plant_rows
        f.append(_table(["Quantity", "Value"], brows, [0.45, 0.55]))

        f.append(Paragraph(f"Refined {device} requirement", _H3))
        delta = (refinement.s_inv_refined_kva / stage1s[i].s_inv_kva - 1) * 100
        rrows = [
            [f"S at {device} — Stage 1 (lumped)", f"{_fmt(stage1s[i].s_inv_kva / 1000)} MVA"],
            [f"S at {device} — refined",
             f"{_fmt(refinement.s_inv_refined_kva / 1000)} MVA ({delta:+.2f}%)"],
            ["P / Q refined", f"{_fmt(refinement.p_inv_refined_kw / 1000)} MW / "
             f"{_fmt(refinement.q_inv_refined_kvar / 1000)} Mvar"],
        ]
        if (refinement.p_poc_refined_delivered_kw is not None
                and refinement.p_poc_target_kw is not None):
            rrows.append([
                "POC delivered with refined S (≥ target by rule)",
                f"{_fmt(refinement.p_poc_refined_delivered_kw / 1000)} MW "
                f"(target {_fmt(refinement.p_poc_target_kw / 1000)} MW)"])
        f.append(_table(["Quantity", "Value"], rrows, [0.45, 0.55]))

        last = i == n - 1
        f.append(Paragraph("Transformer losses", _H3))
        f.append(_table(
            ["Transformer", "Units", "Rating [kVA]", "Loading", "S/unit [kVA]",
             "ΔP/unit [% P_inv]", "ΔP total [% P_inv]", "ΔQ total [kvar]"],
            _transformer_rows(branch, arch.export, p_inv, last, n > 1),
            [1.8, 0.7, 1.0, 0.8, 1.0, 1.0, 1.0, 1.0]))

        f.append(Paragraph("Cable-run losses", _H3))
        f.append(_table(
            ["Run", "Feeds", "Length [m]", "S [kVA]", "Selected cable", "Circuits",
             "Util.", "Loss %", "V-drop %", "ΔP [% P_inv]", "ΔQ ser [kvar]", "Q chg [kvar]"],
            _cable_rows(branch, arch.export, p_inv, last, n > 1),
            [0.8, 1.3, 0.85, 1.05, 1.5, 0.85, 0.7, 0.7, 0.8, 0.75, 0.9, 0.9]))

    f.append(Paragraph(
        "Segment 1 of each circuit is the trunk (substation side). Charging is "
        "reported for information and is never netted into the reactive (worst-case "
        "convention).", _NOTE))
    return f


def arch_total(arch: PlantArchitecture, what: str) -> float:
    """Plant-wide cable or transformer active losses, over every branch.

    PlantArchitecture's own total_* properties read the sole-branch accessors and
    so raise on a hybrid; these sum across branches and add the shared export
    step once.
    """
    export = arch.export
    if what == "cable":
        total = sum(seg.dp_kw for b in arch.branches for c in b.circuits for seg in c.segments)
        if export is not None and export.hv_cable is not None:
            total += export.hv_cable.dp_kw
        return total
    total = sum(st.dp_tx_kw for b in arch.branches for c in b.circuits for st in c.stations)
    if export is not None:
        total += export.dp_tx_kw
    return total


def report_story(
    stage1s: list[SizingResult],
    arch: PlantArchitecture,
    *,
    fleets: list[dict] | None = None,
    plant_name: str = "Plant",
    when: str = "",
) -> list:
    """The report as a list of ReportLab flowables, before it becomes a PDF.

    Split out so the report's CONTENT can be read and asserted on directly. A
    PDF is opaque to a test: checking it would mean parsing the output or
    shelling out to an extractor, and neither tells you which section a missing
    figure went missing from.

    ``fleets`` carries the per-fleet reporting figures — kind, loading maximum,
    containers, delivered and required energy — as the same dicts the editor
    receives from :func:`powertool.graph.branches_summary`. Reusing that record
    rather than inventing a report-side type keeps the PDF and the screen from
    drifting apart, and keeps this module independent of the diagram layer.
    Omit it and the per-fleet sections are simply absent, which is what the
    engine-level callers want.
    """
    story: list = [
        Paragraph(f"{plant_name} — Sizing Report", _H1),
        Paragraph(f"Generated {when} · plant sizing tool", _SUB),
        HRFlowable(width="100%", thickness=2, color=_GREEN, spaceBefore=4,
                   spaceAfter=10),
    ]
    story += _summary(stage1s, arch, fleets)
    story += _methodology()
    for i, stage1 in enumerate(stage1s):
        story += _stage1(stage1, fleets[i] if fleets else None, len(stage1s))
    story += _stage2(stage1s, arch, fleets)
    story += [
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.5, color=_LINE, spaceAfter=6),
        Paragraph(
            "Component parameters come from data/*.yaml. Transformer load/no-load "
            "losses for the PV stations are design assumptions (the datasheets publish "
            "only impedance and an EN 50588-1 efficiency tier); see the catalogue "
            "comments for provenance.", _NOTE),
    ]
    return story


def build_pdf_report(
    stage1s: list[SizingResult],
    arch: PlantArchitecture,
    *,
    fleets: list[dict] | None = None,
    plant_name: str = "Plant",
    generated_at: datetime | None = None,
) -> bytes:
    """Full PDF sizing report: methodology + detailed loss tables. Returns bytes."""
    when = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, title=f"{plant_name} — Sizing Report",
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(report_story(stage1s, arch, fleets=fleets, plant_name=plant_name, when=when))
    return buf.getvalue()
