"""Streamlit web UI for the PV inverter-sizing engine.

Run from the project root with:

    streamlit run app/streamlit_app.py

This file is *only* glue: it collects inputs, builds a Chain, calls the engine in
powertool.sizing, and displays the result. All the physics lives in powertool/.

Two stages:
  * Stage 1 — conceptual: required inverter P/Q/S to meet the POC target over a
    lumped chain. Cable lengths are NOT asked for: every cable section is taken
    at its worst case, consuming the full admissible loss budget (conservative).
  * Stage 2 — plant architecture: the required power organized into LV/MV
    transformer stations, grouped into daisy-chained MV circuits capped by a
    max current per circuit, every cable segment sized for the power it
    actually carries, MV or HV interconnection (HV transformer auto-sized),
    and the single-line diagram with editable run lengths.
"""

import hashlib
import re
import sys
from pathlib import Path

# Make the project root (for powertool) and this app dir (for theme) importable
# regardless of where streamlit is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from theme import inject_theme  # noqa: E402

from powertool import (  # noqa: E402
    AutoCable,
    AuxLoad,
    Chain,
    ChainElement,
    ComponentDatabase,
    TransformerGroup,
    architecture_to_dot,
    arrange_plant,
    auto_hv_transformer,
    build_pdf_report,
    size_architecture,
    size_pv_inverters,
)

# Stage-2 planning constants (fixed by design, not edited per study):
MAX_LOADING = 1.0  # admissible fleet loading; above this the UI warns
I_MAX_CIRCUIT_A = 400.0  # max current per MV collector circuit (feeder planning cap)

st.set_page_config(page_title="PV Plant Sizing", page_icon="⚡", layout="wide")
inject_theme()

db = ComponentDatabase.load()

# ----------------------------------------------------------------------------
# Session state: the chain is a list of plain dicts we render and edit.
# ----------------------------------------------------------------------------
if "elements" not in st.session_state:
    st.session_state.elements = []
# Interconnection defaults (Stage 1); widgets are key-driven so load_example
# can set them without clashing with inline widget defaults.
st.session_state.setdefault("s1_interconnection", "HV")
st.session_state.setdefault("s1_v_export", 132.0)
st.session_state.setdefault("s1_export_m", 0.0)


def load_example() -> None:
    """Populate a representative 45 MW HV-interconnected plant with a MIXED
    station fleet (the two adjacent transformer blocks operate in parallel).
    The MV/HV transformer is NOT an element: the Interconnection section
    auto-sizes it."""
    st.session_state.elements = [
        {"type": "Cable section", "v_kv": 20.0, "label": "MV collector"},
        {"type": "Transformer", "component": "HUAWEI_JUPITER9000", "v_kv": 20.0,
         "n_parallel": 5, "label": "MV/LV stations (big)"},
        {"type": "Transformer", "component": "HUAWEI_JUPITER3000", "v_kv": 20.0,
         "n_parallel": 3, "label": "MV/LV stations (small)"},
        {"type": "Aux load", "v_kv": 20.0, "p_kw": 120.0, "q_kvar": 40.0,
         "label": "Substation aux"},
    ]
    st.session_state.s1_interconnection = "HV"
    st.session_state.s1_v_export = 132.0
    st.session_state.s1_export_m = 0.0


def tx_keys_by_power(branded_only: bool = False) -> list[str]:
    """Transformer catalogue keys, ascending by rated power.

    ``branded_only`` keeps just the manufacturer PV stations (those with a brand),
    used for the Stage-2 LV/MV station picker.
    """
    items = [
        (k, t) for k, t in db.transformers.items()
        if t.brand or not branded_only
    ]
    items.sort(key=lambda kt: (kt[1].s_rated_kva, kt[1].brand or ""))
    return [k for k, _ in items]


def tx_label(key: str) -> str:
    """Dropdown label for a transformer key: 'POWER kVA - BRAND'."""
    return db.transformers[key].display_name


def build_chain(max_utilization: float, collection_loss_pct: float,
                export_loss_pct_per_km: float, interconnection: str,
                v_export_kv: float, export_m: float,
                p_poc_kw: float, pf_target: float) -> Chain:
    """Turn the session-state element dicts into a Chain of ChainElements.

    The interconnection is prepended at the POC end: the export cable (real
    length, export %/km budget — skipped when the catalogue has no cables at
    that voltage) and, for HV interconnection, ONE auto-sized MV/HV
    transformer. In MV interconnection with no export length given, the MV
    busbar -> POC cable is still sized at the worst case (full collection
    budget) so its losses are not ignored. Collection cable sections likewise
    carry no length: the solver runs them at the worst case, consuming the full
    admissible loss budget (conservative by design).

    ADJACENT transformer elements at the SAME voltage are merged into one
    parallel TransformerGroup sharing the load — a mixed station fleet. Without
    this, the linear chain would push the full plant power through each block
    in series, wildly overstating the losses.
    """
    raw = st.session_state.elements

    elements = []
    export_candidates = db.cables_for_voltage(v_export_kv)
    if export_m > 0:
        if export_candidates:
            auto = AutoCable(candidates=export_candidates,
                             max_utilization=max_utilization,
                             max_loss_percent_base=0.0,
                             max_loss_percent_per_km=export_loss_pct_per_km,
                             name="Export cable")
            elements.append(ChainElement(auto, v_kv=v_export_kv,
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
        elements.append(ChainElement(auto, v_kv=v_export_kv,
                                     label="MV interconnection cable"))
    if interconnection == "HV":
        # Conceptual auto-sizing from the POC apparent power; Stage 2 re-sizes
        # it precisely from the actual busbar power.
        tx_voltages = [e["v_kv"] for e in raw if e["type"] == "Transformer"]
        v_mv_guess = min(tx_voltages) if tx_voltages else 20.0
        hv_tx = auto_hv_transformer(p_poc_kw / pf_target, v_export_kv, v_mv_guess)
        elements.append(ChainElement(hv_tx, v_kv=v_export_kv,
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
                comp = db.transformer(e["component"])
                elements.append(ChainElement(comp, v_kv=e["v_kv"],
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
                elements.append(ChainElement(group, v_kv=e["v_kv"], label=label))
            i = j
        elif e["type"] == "Cable section":
            candidates = db.cables_for_voltage(e["v_kv"])
            auto = AutoCable(candidates=candidates, max_utilization=max_utilization,
                             max_loss_percent_base=collection_loss_pct,
                             name=e["label"])
            elements.append(ChainElement(auto, v_kv=e["v_kv"], label=e["label"]))
            i += 1
        else:  # Aux load
            comp = AuxLoad(e["label"] or "Aux load", p_kw=e["p_kw"], q_kvar=e["q_kvar"])
            elements.append(ChainElement(comp, v_kv=e["v_kv"], label=e["label"]))
            i += 1
    return Chain(elements, name="UI chain")


def detect_stage1_context() -> dict:
    """Pull Stage-2 defaults out of the free-form Stage-1 chain dicts.

    Degrades gracefully: anything not found simply has no default.
    """
    ctx: dict = {"aux_p_kw": 0.0, "aux_q_kvar": 0.0}
    transformers = [e for e in st.session_state.elements if e["type"] == "Transformer"]
    cables = [e for e in st.session_state.elements if e["type"] == "Cable section"]
    for e in st.session_state.elements:
        if e["type"] == "Aux load":
            ctx["aux_p_kw"] += e["p_kw"]
            ctx["aux_q_kvar"] += e["q_kvar"]
    if cables:
        ctx["v_mv_kv"] = min(c["v_kv"] for c in cables)
    if transformers:
        # Station fleet = every transformer element at the LOWEST transformer
        # voltage (the MV station level); duplicate models merge their counts.
        v_station = min(e["v_kv"] for e in transformers)
        fleet: dict[str, int] = {}
        for e in transformers:
            if e["v_kv"] == v_station:
                fleet[e["component"]] = fleet.get(e["component"], 0) + e["n_parallel"]
        ctx["fleet"] = list(fleet.items())
    return ctx


# ----------------------------------------------------------------------------
# Sidebar: POC inputs + cable-sizing rules.
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("Project")
    project_name = st.text_input(
        "Project name", value="PV Plant",
        help="Used as the report title and in the downloaded PDF file name.")

    st.header("Point of Connection")
    p_poc_mw = st.number_input("Active power at POC [MW]", min_value=0.1,
                               value=45.0, step=1.0)
    pf_target = st.number_input("Power-factor target", min_value=0.01, max_value=1.0,
                                value=0.95, step=0.01)
    st.caption("Reactive power is taken as **injected** at the POC — the worst case "
               "for inverter sizing.")

    st.divider()
    st.header("Cable sizing rules")
    max_utilization = st.slider("Max cable utilization (ampacity) [%]", 50, 100, 80) / 100.0
    collection_loss_pct = st.number_input(
        "Collection loss budget [%]", min_value=0.05, max_value=10.0, value=1.30, step=0.05,
        help="Admissible cable loss as % of the local active power. Stage-1 cable "
             "sections are assumed to consume the FULL budget (worst case, no length "
             "needed); Stage-2 segments are sized against it with their real lengths.")
    export_loss_pct_per_km = st.number_input(
        "Export loss budget [%/km]", min_value=0.0, max_value=5.0, value=0.10, step=0.05,
        help="Admissible cable loss per km for the export span between the MV busbar "
             "(or HV transformer) and the POC — used in Stage 2.")
    st.caption("Each cable section's cross-section and parallel-circuit count are chosen "
               "automatically: fewest circuits for ampacity, then the smallest cross-section "
               "within the loss budget.")
    st.caption("Component values come from `data/*.yaml` (placeholder datasheet values).")


st.title("PV Plant Sizing")
tab1, tab2 = st.tabs(["Stage 1 · Conceptual sizing", "Stage 2 · Plant architecture"])

# ============================================================================
# Stage 1 — conceptual inverter sizing over the lumped chain.
# ============================================================================
with tab1:
    st.caption("Backward loss cascade from the Point of Connection to the inverter. "
               "Collection cable sections are taken at the worst case (full loss "
               "budget, no length needed); the export cable uses its real length "
               "with the %/km budget.")

    st.subheader("1 · Interconnection (MV busbar → POC)")
    x = st.columns(3)
    interconnection = x[0].radio(
        "Interconnection", ["HV", "MV"], horizontal=True, key="s1_interconnection",
        help="HV: ONE MV/HV transformer is sized automatically for the plant power "
             "and added to the cascade — do not add it as a chain element. "
             "MV: the plant connects at MV, no transformer.")
    v_export_kv = x[1].number_input(
        "Interconnection voltage [kV]", min_value=1.0, step=1.0,
        key="s1_v_export",
        help="Voltage of the export side: the HV grid voltage (HV mode) or the MV "
             "interconnection voltage (MV mode). The export cable runs at it.")
    export_m = x[2].number_input(
        "Export cable length [m] (0 = none)", min_value=0.0, step=100.0,
        key="s1_export_m",
        help="Span between the substation and the POC, sized with its real length "
             "against the export %/km loss budget.")
    if interconnection == "HV":
        st.info("ℹ️ The MV/HV transformer is **sized automatically** for the plant "
                "power — don't add it to the chain below.")

    st.subheader("2 · Build the electrical chain (MV busbar → inverter)")

    top = st.columns([1, 1, 4])
    top[0].button("Load example plant", on_click=load_example)
    top[1].button("Clear chain", on_click=lambda: st.session_state.update(elements=[]))

    with st.expander("➕ Add an element", expanded=not st.session_state.elements):
        etype = st.selectbox("Element type", ["Transformer", "Cable section", "Aux load"])
        c = st.columns(4)
        new: dict = {"type": etype}

        if etype == "Transformer":
            new["component"] = c[0].selectbox("Transformer", tx_keys_by_power(),
                                              format_func=tx_label)
            new["v_kv"] = c[1].number_input("Section voltage [kV]", min_value=0.1, value=20.0)
            new["n_parallel"] = c[2].number_input("Parallel units", min_value=1, value=1, step=1)
            new["label"] = c[3].text_input("Label (optional)", value="")
        elif etype == "Cable section":
            new["v_kv"] = c[0].number_input("Section voltage [kV]", min_value=0.1, value=20.0)
            new["label"] = c[1].text_input("Label (optional)", value="")
            c[2].caption("No length needed — the section is sized at the worst case "
                         "(full loss budget consumed).")
        else:  # Aux load
            new["label"] = c[0].text_input("Name", value="Aux load")
            new["p_kw"] = c[1].number_input("P [kW]", value=100.0)
            new["q_kvar"] = c[2].number_input("Q [kvar]", value=0.0)
            new["v_kv"] = c[3].number_input("Section voltage [kV]", min_value=0.1, value=20.0)

        if st.button("Add to chain", type="secondary"):
            st.session_state.elements.append(new)
            st.rerun()

    # Show the current chain as an editor: any row can be deleted (select it
    # and press the trash icon / Delete) and rows are rearranged by editing
    # the Order number.
    if st.session_state.elements:
        rows = []
        for i, e in enumerate(st.session_state.elements):
            if e["type"] == "Transformer":
                detail = f"{tx_label(e['component'])} (x{e['n_parallel']})"
            elif e["type"] == "Cable section":
                detail = "auto-sized (worst-case budget)"
            else:
                detail = f"P={e['p_kw']} kW, Q={e['q_kvar']} kvar"
            rows.append({
                "Order": i + 1,
                "Element": e["label"] or e["type"],
                "Type": e["type"],
                "Detail": detail,
                "V [kV]": e["v_kv"],
                "id": i,
            })
        # Key tied to the chain content: applying an edit rebuilds a fresh
        # editor, so stale widget edits never re-apply to the new ordering.
        sig = hashlib.md5(str(st.session_state.elements).encode()).hexdigest()[:8]
        edited = st.data_editor(
            pd.DataFrame(rows),
            key=f"s1_chain_{sig}",
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            disabled=["Element", "Type", "Detail", "V [kV]", "id"],
            column_config={
                "Order": st.column_config.NumberColumn(
                    min_value=1, step=1,
                    help="Edit to rearrange the chain (POC side first)."),
                "id": None,  # internal row identity, hidden
            },
        )
        kept = edited.dropna(subset=["id"]).sort_values(by="Order", kind="stable")
        new_seq = [int(i) for i in kept["id"]]
        if new_seq != list(range(len(st.session_state.elements))):
            st.session_state.elements = [st.session_state.elements[i] for i in new_seq]
            st.rerun()
        st.caption("Delete any row (select it, then the 🗑 icon or Delete key) · edit "
                   "**Order** to rearrange · add elements with the ➕ form above. "
                   "Adjacent transformers at the same voltage operate **in parallel** "
                   "and share the load (a mixed station fleet).")
    else:
        st.info("No elements yet. Use **Load example plant** or add elements above.")

    st.subheader("3 · Results")

    if st.button("Calculate inverter sizing", type="primary",
                 disabled=not st.session_state.elements):
        try:
            chain = build_chain(max_utilization, collection_loss_pct,
                                export_loss_pct_per_km, interconnection,
                                v_export_kv, export_m,
                                p_poc_kw=p_poc_mw * 1000, pf_target=pf_target)
            res = size_pv_inverters(chain, p_poc_kw=p_poc_mw * 1000, pf_target=pf_target)
        except Exception as exc:  # surface modelling/data errors plainly
            st.error(f"Could not compute: {exc}")
        else:
            # Keep the result AND the interconnection choices for Stage 2.
            st.session_state.stage1 = {
                "result": res,
                "p_poc_kw": p_poc_mw * 1000,
                "interconnection": interconnection,
                "v_export_kv": v_export_kv,
                "export_m": export_m,
            }
            if (export_m > 0 or interconnection == "MV") and \
                    not db.cables_for_voltage(v_export_kv):
                st.info(f"No cables in the catalogue at {v_export_kv:g} kV — the "
                        "cable to the POC is not sized (zero losses assumed) "
                        "until the catalogue is populated.")

            m = st.columns(4)
            m[0].metric("P at inverter [MW]", f"{res.p_inv_kw / 1000:.2f}")
            m[1].metric("Q at inverter [Mvar]", f"{res.q_inv_kvar / 1000:.2f}")
            m[2].metric("S at inverter [MVA]", f"{res.s_inv_kva / 1000:.2f}")
            m[3].metric("PF at inverter", f"{res.pf_inv:.3f}")

            st.markdown("**Loss breakdown (POC → inverter):**")
            breakdown = pd.DataFrame([{
                "Element": e.name,
                "Type": e.kind,
                "Selected cable": (e.cable_label if e.cable_label else "—"),
                "Length [m]": (f"{e.length_km * 1000:,.0f}"
                               if e.length_km is not None else "—"),
                "Utilization": (f"{e.utilization * 100:.0f}%" if e.utilization is not None else "—"),
                "Loss": (f"{e.loss_percent:.2f}%" if e.loss_percent is not None else "—"),
                "V-drop": (f"{e.vdrop_percent:.2f}%" if e.vdrop_percent is not None else "—"),
                "S through [kVA]": round(e.s_through_kva, 1),
                "ΔP [% P_inv]": (f"{e.dp_kw / res.p_inv_kw * 100:.3f}%"
                                 if res.p_inv_kw else "—"),
                "ΔQ [kvar]": round(e.dq_kvar, 2),
            } for e in res.losses])
            st.dataframe(breakdown, use_container_width=True, hide_index=True)

            st.caption(
                f"Total active losses: {res.total_active_loss_kw / res.p_inv_kw * 100:.2f}% of P_inv  ·  "
                f"Q at POC (injected): {res.q_poc_kvar:,.1f} kvar  ·  "
                f"Power-balance check: {'✅ OK' if res.power_balance_ok else '❌ FAILED'}"
            )
            st.caption("Assumptions: 3-phase balanced, positive-sequence, RMS, steady-state; "
                       "losses computed at nominal section voltage. For worst-case cable "
                       "sections the length shown is IMPLIED — the length at which the "
                       "selected cable exactly exhausts the loss budget; the export cable "
                       "uses its real length.")
            st.success("Stage 1 stored — open **Stage 2 · Plant architecture** to organize "
                       "this power into transformer blocks and MV circuits.")

# ============================================================================
# Stage 2 — plant architecture: stations, circuits, per-segment cables, SLD.
# ============================================================================
with tab2:
    if "stage1" not in st.session_state:
        st.info("Run **Stage 1** first — the architecture organizes the required "
                "inverter power into transformer blocks and MV circuits.")
    else:
        stage1 = st.session_state.stage1["result"]
        p_poc_target_kw = st.session_state.stage1["p_poc_kw"]
        ctx = detect_stage1_context()

        st.caption(
            f"Organizing **S_inv = {stage1.s_inv_kva / 1000:.2f} MVA** "
            f"(P = {stage1.p_inv_kw / 1000:.2f} MW, Q = {stage1.q_inv_kvar / 1000:.2f} Mvar) "
            f"for a POC target of **{p_poc_target_kw / 1000:g} MW**. "
            "The tool arranges the plant; tweak any input and it re-arranges."
        )

        st.markdown("**Stations & circuits**")
        fleet_ctx = ctx.get("fleet", [])
        if not fleet_ctx:
            st.warning("The Stage-1 chain has no LV/MV transformer stations — add "
                       "them in Stage 1 and recalculate.")
            st.stop()
        fleet = [(db.transformer(key), n) for key, n in fleet_ctx]
        fleet_label = " + ".join(f"{n}× {tx.display_name}" for tx, n in fleet)
        s_fleet = sum(tx.s_rated_kva * n for tx, n in fleet)
        st.caption(f"Station fleet from Stage 1: **{fleet_label}** "
                   f"(Σ {s_fleet / 1000:.2f} MVA). Change it in the Stage-1 chain.")

        g = st.columns(3)
        trunk_m = g[0].number_input("Trunk length: substation → first station [m]",
                                    min_value=1.0, value=800.0, step=50.0, key="s2_trunk")
        spacing_m = g[1].number_input("Station-to-station spacing [m]",
                                      min_value=1.0, value=350.0, step=25.0, key="s2_spacing")
        v_mv_kv = g[2].number_input("MV collection voltage [kV]", min_value=1.0,
                                    value=float(ctx.get("v_mv_kv", 20.0)), key="s2_v_mv")

        # Interconnection comes from Stage 1 (toggle + voltage + export length).
        interconnection = st.session_state.stage1.get("interconnection", "MV")
        export_v_kv = st.session_state.stage1.get("v_export_kv", v_mv_kv)
        export_cable_m = st.session_state.stage1.get("export_m", 0.0)
        parts = [f"**{interconnection}** at {export_v_kv:g} kV"]
        if export_cable_m > 0:
            parts.append(f"export cable {export_cable_m:g} m")
        if ctx.get("aux_p_kw") or ctx.get("aux_q_kvar"):
            parts.append(f"aux load {ctx['aux_p_kw']:g} kW / {ctx['aux_q_kvar']:g} kvar")
        st.caption("From Stage 1 — interconnection: " + " · ".join(parts)
                   + f". Circuits planned for max {I_MAX_CIRCUIT_A:g} A per feeder, "
                     f"biggest stations nearest the substation.")

        try:
            candidates = db.cables_for_voltage(v_mv_kv)
            export_candidates = (db.cables_for_voltage(export_v_kv)
                                 if export_cable_m > 0 else [])

            layout = arrange_plant(
                stage1, fleet,
                max_loading=MAX_LOADING,
                max_circuit_current_a=I_MAX_CIRCUIT_A,
                trunk_length_km=trunk_m / 1000.0,
                spacing_km=spacing_m / 1000.0,
                v_mv_kv=v_mv_kv,
            )
        except Exception as exc:
            st.error(f"Could not arrange the plant: {exc}")
        else:
            # Containers let the metrics live above the SLD even though they
            # need the sizing result, which needs the editable lengths below.
            notice_box = st.container()
            metrics_box = st.container()

            st.subheader("Single-line diagram")
            col_sld, col_edit = st.columns([3, 2], gap="medium")

            # --- Editable cable run lengths (right of the SLD) -------------
            with col_edit:
                st.markdown("**Cable run lengths** — edit to update the sizing")
                default_rows = []
                for c_idx, n_stations in enumerate(layout.circuit_sizes, start=1):
                    for s_idx in range(1, n_stations + 1):
                        default_rows.append({
                            "Run": f"C{c_idx}·S{s_idx}",
                            "From": "Busbar" if s_idx == 1 else f"TX {c_idx}.{s_idx - 1}",
                            "To": f"TX {c_idx}.{s_idx}",
                            "Length [m]": float(trunk_m if s_idx == 1 else spacing_m),
                        })
                # The key encodes the arrangement: a new arrangement (or new
                # default lengths) resets the editor to fresh defaults.
                editor_key = (f"s2_lengths_{'-'.join(map(str, layout.circuit_sizes))}"
                              f"_{trunk_m:g}_{spacing_m:g}")
                edited = st.data_editor(
                    pd.DataFrame(default_rows),
                    key=editor_key,
                    hide_index=True,
                    use_container_width=True,
                    height=min(420, 56 + 35 * len(default_rows)),
                    disabled=["Run", "From", "To"],
                    column_config={
                        "Length [m]": st.column_config.NumberColumn(
                            min_value=1.0, step=10.0, format="%.0f"),
                    },
                )
                overrides: dict[tuple[int, int], float] = {}
                for _, row in edited.iterrows():
                    c_str, s_str = row["Run"].split("·")
                    overrides[(int(c_str[1:]), int(s_str[1:]))] = row["Length [m]"] / 1000.0

            # --- Size the full architecture with the edited lengths --------
            try:
                arch = size_architecture(
                    layout, stage1, candidates,
                    max_utilization=max_utilization,
                    max_loss_percent_base=collection_loss_pct,
                    segment_lengths=overrides,
                    auto_hv=(interconnection == "HV"),
                    hv_cable_candidates=export_candidates,
                    hv_cable_length_km=export_cable_m / 1000.0,
                    v_hv_kv=export_v_kv,
                    export_loss_percent_per_km=export_loss_pct_per_km,
                    aux_p_kw=ctx["aux_p_kw"],
                    aux_q_kvar=ctx["aux_q_kvar"],
                    p_poc_target_kw=p_poc_target_kw,
                )
            except Exception as exc:
                st.error(f"Could not size the architecture: {exc}")
            else:
                with col_sld:
                    st.graphviz_chart(architecture_to_dot(arch), use_container_width=True)

                with notice_box:
                    if not layout.loading_ok:
                        st.warning(
                            f"Fleet loading {layout.fleet_loading * 100:.0f}% — the "
                            f"required inverter power exceeds the installed station "
                            f"capacity, so every station would run above its rating. "
                            f"Add stations or bigger units in the Stage-1 chain.")
                    if not arch.all_current_ok:
                        st.warning(f"At least one circuit's trunk current exceeds the "
                                   f"{I_MAX_CIRCUIT_A:g} A planning cap — check the inputs.")
                    if candidates:
                        v_class = candidates[0].rated_voltage_kv
                        if v_class != v_mv_kv:
                            st.caption(f"MV segments sized with the {v_class:g} kV cable "
                                       f"class (lowest class covering {v_mv_kv:g} kV).")
                    if (export_cable_m > 0 and arch.export is not None
                            and not arch.export.hv_cable_sized):
                        st.info("No cables in the catalogue at the export voltage — the "
                                "export span is shown but not sized (zero losses assumed).")
                    if arch.export is not None and arch.export.hv_transformer is not None:
                        hv = arch.export.hv_transformer
                        st.caption(f"Auto-sized MV/HV transformer: **{hv.name}** — "
                                   f"{hv.s_rated_kva / 1000:g} MVA, one unit, for "
                                   f"{arch.export.s_tx_through_kva / 1000:.1f} MVA through.")

                with metrics_box:
                    m = st.columns(4)
                    m[0].metric("LV/MV transformers", f"{layout.n_transformers}")
                    m[1].metric("MV circuits", layout.circuit_sizes_label)
                    m[2].metric(
                        "Fleet loading", f"{layout.fleet_loading * 100:.0f}%",
                        help="Required inverter power ÷ installed station capacity "
                             "(Σ ratings). Above 100% the Stage-1 fleet is undersized: "
                             "every station would run over its rating — add stations "
                             "or bigger units in Stage 1.")
                    worst_trunk = max(c.i_trunk_a for c in arch.circuits)
                    m[3].metric("Worst trunk current", f"{worst_trunk:,.0f} A",
                                delta=f"cap {I_MAX_CIRCUIT_A:g} A", delta_color="off")

                    r = st.columns(5)
                    r[0].metric("S_inv — Stage 1 [MVA]", f"{stage1.s_inv_kva / 1000:.2f}")
                    delta_pct = (arch.s_inv_refined_kva / stage1.s_inv_kva - 1) * 100
                    r[1].metric("S_inv — refined [MVA]",
                                f"{arch.s_inv_refined_kva / 1000:.2f}",
                                delta=f"{delta_pct:+.2f}%")
                    pf_inv = (arch.p_inv_refined_kw / arch.s_inv_refined_kva
                              if arch.s_inv_refined_kva > 0 else 1.0)
                    r[2].metric("PF at inverter", f"{pf_inv:.3f}")
                    r[3].metric("Total losses [% P_inv]",
                                f"{arch.total_active_loss_kw / arch.p_inv_refined_kw * 100:.2f}%")
                    if arch.p_poc_refined_delivered_kw is not None:
                        r[4].metric("POC with refined S_inv [MW]",
                                    f"{arch.p_poc_refined_delivered_kw / 1000:.2f}",
                                    delta=f"target {p_poc_target_kw / 1000:g} MW",
                                    delta_color="off")
                    st.caption("The refined inverter power is sized so the POC delivery "
                               "lands **at or above** the target — overshoot is "
                               "curtailable, shortfall is never accepted.")

                st.markdown("**Cable segments (per circuit, segment 1 = trunk):**")
                p_inv_ref = arch.p_inv_refined_kw
                seg_rows = []
                for circuit in arch.circuits:
                    for seg in circuit.segments:
                        sel = seg.selection
                        seg_rows.append({
                            "Run": f"C{circuit.index}·S{seg.index}",
                            "Feeds": circuit.stations[seg.index - 1].model,
                            "Length [m]": round(seg.length_km * 1000),
                            "S [kVA]": round(seg.s_kva, 1),
                            "Selected cable": seg.cable_label,
                            "Utilization": f"{sel.utilization * 100:.0f}%",
                            "Loss": f"{sel.loss_percent:.2f}%",
                            "V-drop": f"{sel.vdrop_percent:.2f}%",
                            "ΔP [% P_inv]": f"{seg.dp_kw / p_inv_ref * 100:.3f}%",
                            "ΔQ [kvar]": round(seg.dq_series_kvar, 2),
                        })
                if arch.export is not None and arch.export.hv_cable is not None:
                    hv_seg = arch.export.hv_cable
                    sel = hv_seg.selection
                    seg_rows.append({
                        "Run": "Export",
                        "Feeds": "POC",
                        "Length [m]": round(hv_seg.length_km * 1000),
                        "S [kVA]": round(hv_seg.s_kva, 1),
                        "Selected cable": hv_seg.cable_label,
                        "Utilization": f"{sel.utilization * 100:.0f}%" if sel else "—",
                        "Loss": f"{sel.loss_percent:.2f}%" if sel else "—",
                        "V-drop": f"{sel.vdrop_percent:.2f}%" if sel else "—",
                        "ΔP [% P_inv]": f"{hv_seg.dp_kw / p_inv_ref * 100:.3f}%",
                        "ΔQ [kvar]": round(hv_seg.dq_series_kvar, 2),
                    })
                st.dataframe(pd.DataFrame(seg_rows), use_container_width=True,
                             hide_index=True)

                st.caption(
                    f"Cable losses: {arch.total_cable_loss_kw / p_inv_ref * 100:.2f}% of P_inv  ·  "
                    f"Transformer losses: {arch.total_transformer_loss_kw / p_inv_ref * 100:.2f}% of P_inv  ·  "
                    f"POC delivered (Stage-1 S_inv): {arch.p_poc_delivered_kw / 1000:.2f} MW  ·  "
                    f"Power-balance check: {'✅ OK' if arch.power_balance_ok else '❌ FAILED'}"
                )

                st.subheader("Report")
                report_pdf = build_pdf_report(stage1, arch, plant_name=project_name)
                safe_name = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_") or "report"
                st.download_button(
                    "📄 Download sizing report (PDF)", data=report_pdf,
                    file_name=f"{safe_name}_sizing_report.pdf", mime="application/pdf",
                    help="Full methodology plus detailed per-cable-run and "
                         "per-transformer loss tables.")
