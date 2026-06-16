"""Markdown report generator: methodology + detailed loss tables.

Produces a self-contained Markdown document that explains how every figure was
computed and tabulates the losses of each cable run and each transformer. The
output is plain text (no rendering dependency); the Streamlit app offers it as a
download and it converts cleanly to PDF via any Markdown tool.
"""

from __future__ import annotations

from datetime import datetime

from .architecture import PlantArchitecture
from .sizing import SizingResult


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


# ---------------------------------------------------------------------------
# Methodology — static text describing the engine (kept in sync with the code).
# ---------------------------------------------------------------------------
_METHODOLOGY = r"""## 1. Methodology

### 1.1 Conventions and assumptions

All quantities are three-phase, balanced, positive-sequence, RMS, steady-state.
Voltages are line-to-line in kV; active power *P* in kW, reactive *Q* in kvar,
apparent *S* in kVA. Line current for a section at voltage *V* is

$$I = \frac{S}{\sqrt{3}\,V}.$$

**Worst-case reactive sign convention.** The plant is assumed to *inject*
reactive power at the Point of Connection (POC) — the worst case for inverter
sizing, because it maximises the reactive the inverters must produce. Every
element's reactive contribution is its series loss only (kept ≥ 0). Cable
capacitive charging is computed and reported for information but is **never**
netted against the series reactive, which would optimistically under-size the
inverters.

### 1.2 Component loss models

**Cable** (per section, length *L*, resistance *r* and reactance *x* per km, with
*n* parallel circuits sharing the current):

$$\Delta P = \frac{3 I^2 (rL)}{n}\;[\text{kW}], \qquad
  \Delta Q_\text{series} = \frac{3 I^2 (xL)}{n}\;[\text{kvar}], \qquad
  Q_\text{charging} = n\,V^2 (bL)\;[\text{kvar}].$$

**Transformer** (rated power *S*r, short-circuit voltage *uk*%, load loss *Pk*,
no-load loss *P0*, magnetising current *i0*%):

$$\Delta P = P_k\left(\tfrac{S}{S_r}\right)^2 + P_0, \qquad
  \Delta Q = \frac{u_x}{100}\,\frac{S^2}{S_r} + \frac{i_0}{100}\,S_r,$$

with the reactive part of the short-circuit voltage $u_x = \sqrt{u_k^2 - u_r^2}$
and the resistive part $u_r = 100\,P_k/S_r$. A fleet of mixed parallel units
shares the load at equal per-unit loading $r = S/\sum S_r$ — each unit carries a
share of *S* proportional to its rating — and the losses are summed.

### 1.3 Stage 1 — Conceptual inverter sizing

The electrical path from the POC to the inverter is walked **backward**,
accumulating losses into a running (P, Q). Starting from the POC target and the
reactive implied by the power-factor target, each element adds its losses, so the
final (P, Q) is what the inverters must deliver. The MV/HV interconnection
transformer is **sized automatically** (smallest IEC-preferred rating ≥ the plant
apparent power) rather than picked from the catalogue.

**Worst-case cable sizing.** At the conceptual stage the collection cable lengths
are unknown, so instead of assuming a length the tool assumes the cable consumes
its **full admissible loss budget** (the most conservative case). The cross-section
and number of parallel circuits are set by ampacity (fewest circuits whose
per-circuit current stays within the utilisation limit, then the smallest
section); the *implied* length — the length at which that cable exactly exhausts
the budget — is reported. The export cable, whose length is known, is sized
normally against its per-km budget.

### 1.4 Stage 2 — Plant architecture

The required inverter power is organised into the station fleet defined in
Stage 1. Every station runs at the same per-unit loading, so its LV share is
proportional to its rating; its MV-side output (share minus its own transformer
losses) sets its current. Stations are grouped into MV collector circuits with
the fewest circuits whose total current respects the per-feeder cap, balanced by
a longest-processing-time heuristic; within each circuit the **biggest stations
sit nearest the substation**, which minimises the power flowing through the long
tail segments and therefore the cable losses.

Each daisy-chain segment is then sized **independently** for the cumulative power
it actually carries (the trunk carries the whole circuit, the far segment one
station), walking from the far station toward the substation and subtracting the
losses consumed en route — the mirror image of the Stage-1 backward cascade.

**Refined inverter requirement (never fall short).** Because losses grow with the
square of load, a single proportional correction would deliver slightly *under*
target. Instead the inverter power is scaled by a factor that is iterated against
the loss cascade — with the cable selections frozen, so the discrete picks cannot
flap — until the delivered POC power is at or above the target. Overshoot is
curtailable; shortfall is not accepted."""


def _summary_section(stage1: SizingResult, arch: PlantArchitecture) -> str:
    export = arch.export
    if export is None:
        interconn = f"MV, at {arch.layout.v_mv_kv:g} kV busbar"
    else:
        hv = export.hv_transformer
        interconn = (
            f"HV, at {export.v_hv_kv:g} kV"
            + (f" via {hv.s_rated_kva / 1000:g} MVA auto-sized MV/HV transformer"
               if hv is not None else "")
        )
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
    return "## 0. Plant summary\n\n" + _table(["Item", "Value"], rows)


def _stage1_section(stage1: SizingResult) -> str:
    out = ["## 2. Stage 1 results — required inverter rating", ""]
    rows = [
        ["P at inverter", f"{_fmt(stage1.p_inv_kw / 1000)} MW"],
        ["Q at inverter", f"{_fmt(stage1.q_inv_kvar / 1000)} Mvar"],
        ["S at inverter", f"{_fmt(stage1.s_inv_kva / 1000)} MVA"],
        ["Power factor at inverter", f"{stage1.pf_inv:.3f}"],
        ["Total active losses (POC→inverter)", f"{_fmt(stage1.total_active_loss_kw)} kW"],
        ["Power-balance check", "OK" if stage1.power_balance_ok else "FAILED"],
    ]
    out.append(_table(["Quantity", "Value"], rows))
    out += ["", "### 2.1 Conceptual loss breakdown (POC → inverter)", ""]
    headers = ["Element", "Type", "Selected cable", "Length [m]", "Util.",
               "Loss %", "V-drop %", "S [kVA]", "ΔP [kW]", "ΔQ [kvar]"]
    trows = []
    for e in stage1.losses:
        trows.append([
            e.name, e.kind,
            e.cable_label or "—",
            f"{_fmt(e.length_km * 1000, 0)}" if e.length_km is not None else "—",
            f"{e.utilization * 100:.0f}%" if e.utilization is not None else "—",
            f"{e.loss_percent:.2f}" if e.loss_percent is not None else "—",
            f"{e.vdrop_percent:.2f}" if e.vdrop_percent is not None else "—",
            _fmt(e.s_through_kva, 1), _fmt(e.dp_kw), _fmt(e.dq_kvar),
        ])
    out.append(_table(headers, trows))
    out.append("")
    out.append("*Worst-case cable lengths are IMPLIED — the length at which the "
               "selected cable exactly exhausts its loss budget; the export cable "
               "uses its real length.*")
    return "\n".join(out)


def _transformer_table(arch: PlantArchitecture) -> str:
    # Aggregate stations by model (identical units have identical losses), then
    # add the auto-sized MV/HV transformer.
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
    headers = ["Transformer", "Units", "Rating [kVA]", "Loading", "S/unit [kVA]",
               "ΔP/unit [kW]", "ΔP total [kW]", "ΔQ total [kvar]"]
    rows = []
    for model, a in sorted(agg.items(), key=lambda kv: -kv[1]["s_rated"]):
        rows.append([
            model, str(a["count"]), _fmt(a["s_rated"], 0), f"{a['loading'] * 100:.0f}%",
            _fmt(a["s_lv"], 1), _fmt(a["dp"] / a["count"]),
            _fmt(a["dp"]), _fmt(a["dq"]),
        ])
    export = arch.export
    if export is not None and export.hv_transformer is not None:
        hv = export.hv_transformer
        loading = export.s_tx_through_kva / (hv.s_rated_kva * export.hv_n_parallel)
        rows.append([
            f"{hv.name} (MV/HV)", str(export.hv_n_parallel), _fmt(hv.s_rated_kva, 0),
            f"{loading * 100:.0f}%", _fmt(export.s_tx_through_kva, 1),
            _fmt(export.dp_tx_kw / export.hv_n_parallel),
            _fmt(export.dp_tx_kw), _fmt(export.dq_tx_kvar),
        ])
    return _table(headers, rows)


def _cable_table(arch: PlantArchitecture) -> str:
    headers = ["Run", "Feeds", "Length [m]", "S [kVA]", "Selected cable",
               "Circuits", "Util.", "Loss %", "V-drop %", "ΔP [kW]",
               "ΔQ series [kvar]", "Q charging [kvar]"]
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
                f"{sel.vdrop_percent:.2f}", _fmt(seg.dp_kw),
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
            _fmt(seg.dp_kw), _fmt(seg.dq_series_kvar), _fmt(seg.q_charging_kvar),
        ])
    return _table(headers, rows)


def _stage2_section(stage1: SizingResult, arch: PlantArchitecture) -> str:
    layout = arch.layout
    out = ["## 3. Stage 2 results — plant architecture", ""]
    rows = [
        ["LV/MV transformers", str(layout.n_transformers)],
        ["MV circuits", layout.circuit_sizes_label],
        ["Fleet loading", f"{layout.fleet_loading * 100:.0f}%"
         + ("" if layout.loading_ok else "  ⚠ fleet undersized")],
        ["Worst trunk current", f"{_fmt(max(c.i_trunk_a for c in arch.circuits), 0)} A"
         f" (cap {_fmt(layout.max_circuit_current_a, 0)} A)"],
        ["Total cable losses", f"{_fmt(arch.total_cable_loss_kw)} kW"],
        ["Total transformer losses", f"{_fmt(arch.total_transformer_loss_kw)} kW"],
        ["Total active losses", f"{_fmt(arch.total_active_loss_kw)} kW"],
        ["Power-balance check", "OK" if arch.power_balance_ok else "FAILED"],
    ]
    out.append(_table(["Quantity", "Value"], rows))

    out += ["", "### 3.1 Refined inverter requirement", ""]
    delta = (arch.s_inv_refined_kva / stage1.s_inv_kva - 1) * 100
    rrows = [
        ["S at inverter — Stage 1 (lumped)", f"{_fmt(stage1.s_inv_kva / 1000)} MVA"],
        ["S at inverter — refined", f"{_fmt(arch.s_inv_refined_kva / 1000)} MVA "
         f"({delta:+.2f}%)"],
        ["P / Q refined",
         f"{_fmt(arch.p_inv_refined_kw / 1000)} MW / "
         f"{_fmt(arch.q_inv_refined_kvar / 1000)} Mvar"],
    ]
    if arch.p_poc_refined_delivered_kw is not None and arch.p_poc_target_kw is not None:
        rrows.append([
            "POC delivered with refined S (≥ target by rule)",
            f"{_fmt(arch.p_poc_refined_delivered_kw / 1000)} MW "
            f"(target {_fmt(arch.p_poc_target_kw / 1000)} MW)"])
    out.append(_table(["Quantity", "Value"], rrows))

    out += ["", "### 3.2 Transformer losses", "", _transformer_table(arch)]
    out += ["", "### 3.3 Cable-run losses", "", _cable_table(arch),
            "", "*Segment 1 of each circuit is the trunk (substation side). "
            "Charging is reported for information and is never netted into the "
            "reactive (worst-case convention).*"]
    return "\n".join(out)


def build_report(
    stage1: SizingResult,
    arch: PlantArchitecture,
    *,
    plant_name: str = "PV Plant",
    generated_at: datetime | None = None,
) -> str:
    """Full Markdown sizing report: methodology + detailed loss tables."""
    when = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    parts = [
        f"# {plant_name} — Sizing Report",
        f"*Generated {when} · PV plant sizing tool*",
        "",
        _summary_section(stage1, arch),
        "",
        _METHODOLOGY,
        "",
        _stage1_section(stage1),
        "",
        _stage2_section(stage1, arch),
        "",
        "---",
        "*Component parameters come from `data/*.yaml`. Transformer load/no-load "
        "losses for the PV stations are design assumptions (the datasheets publish "
        "only impedance and an EN 50588-1 efficiency tier); see the catalogue "
        "comments for provenance.*",
    ]
    return "\n".join(parts)
