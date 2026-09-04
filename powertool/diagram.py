"""Single-line diagram rendering: PlantArchitecture -> Graphviz DOT string.

Pure string building, stdlib only. The output is consumable by Streamlit's
built-in ``st.graphviz_chart`` or the ``dot`` CLI — no new dependency.

Vertical layout (top to bottom) like a substation drawing: POC at the top,
then the export side (HV cable span, MV/HV transformer) when present, the MV
busbar, and one daisy chain of stations per MV circuit below it. Cable spans
are EDGES labelled with their run id (``C1·S2`` — circuit 1, segment 2; the
same ids appear in the editable lengths table in the app), the selected cable
(``Al_3x{circuits}x{section}_{voltage}kV``) and the span length. Edges are
undirected (no arrowheads) as in a conventional SLD.

Colours follow the RP Global premium/minimal theme so the diagram blends into
the app: transparent background, white filled nodes with navy text and borders,
Energy-Green accented busbar/POC, in a clean sans-serif font.
"""

from __future__ import annotations

from .architecture import PlantArchitecture

# RP Global premium/minimal palette (light theme).
_NODE_FILL = "#ffffff"   # white nodes
_NODE_BORDER = "#011d3f"  # Business Blue
_TEXT = "#011d3f"        # Business Blue
_EDGE = "#99a9bc"        # Medium Blue
_EDGE_TEXT = "#011d3f"   # Business Blue
_ACCENT = "#00a438"      # Energy Green — POC / busbar pop
_FONT = "Helvetica"      # clean sans-serif


def _edge_label(run_id: str, cable_label: str, length_km: float) -> str:
    return f"{run_id}\\n{cable_label}\\n{length_km * 1000:g} m"


def architecture_to_dot(arch: PlantArchitecture) -> str:
    """Render the plant architecture as a Graphviz DOT single-line diagram."""
    if len(arch.branches) != 1:
        # This diagram is single-branch only, mirroring build_report — a
        # hybrid's single-line drawing is not produced yet. Refuse and name
        # the fleets found rather than drawing one fleet as the whole plant.
        kinds = ", ".join(sorted({
            st.kind for b in arch.branches for c in b.circuits for st in c.stations
        }))
        raise ValueError(
            f"This design has {len(arch.branches)} fleets ({kinds}) and the "
            f"single-line diagram is still single-fleet — it would draw only "
            f"the first and silently omit the rest."
        )
    branch = arch.branches[0]
    refinement = arch.branch_refinements[0]
    layout = branch.layout
    lines: list[str] = [
        "graph plant {",
        "  rankdir=TB;",
        "  splines=line;",  # straight edges, no curves — like a real SLD
        '  bgcolor="transparent";',
        f'  node [fontname="{_FONT}", fontsize=11, style=filled, '
        f'fillcolor="{_NODE_FILL}", color="{_NODE_BORDER}", fontcolor="{_TEXT}"];',
        f'  edge [fontname="{_FONT}", fontsize=9, color="{_EDGE}", '
        f'fontcolor="{_EDGE_TEXT}", penwidth=1.2];',
    ]

    # POC, annotated with the target (when given) and the voltage at the POC —
    # the HV grid voltage for HV interconnection, else the MV busbar voltage.
    poc_v_kv = arch.export.v_hv_kv if arch.export is not None else layout.v_mv_kv
    poc_label = "POC"
    if refinement.p_poc_target_kw is not None:
        poc_label += f"\\n{refinement.p_poc_target_kw / 1000:g} MW"
    poc_label += f"\\n{poc_v_kv:g} kV"
    lines.append(
        f'  POC [shape=doublecircle, color="{_ACCENT}", label="{poc_label}"];'
    )

    # MV busbar: a thin accent-coloured bar.
    lines.append(
        f'  BUS [shape=box, fillcolor="{_ACCENT}", color="{_ACCENT}", '
        f'fontcolor="white", height=0.12, label="MV busbar {layout.v_mv_kv:g} kV"];'
    )

    # Export side: POC -- (HV cable) -- MV/HV transformer -- busbar.
    export = arch.export
    if export is not None and export.hv_transformer is not None:
        tx = export.hv_transformer
        units = f" x{export.hv_n_parallel}" if export.hv_n_parallel > 1 else ""
        lines.append(
            f'  HVTX [shape=box, label="{tx.name}\\n'
            f'{tx.s_rated_kva / 1000:g} MVA{units}"];'
        )
        if export.hv_cable is not None:
            lines.append(
                f'  POC -- HVTX [label="'
                f'{_edge_label("Export", export.hv_cable.cable_label, export.hv_cable.length_km)}"];'
            )
        else:
            lines.append("  POC -- HVTX;")
        lines.append("  HVTX -- BUS;")
    elif export is not None and export.hv_cable is not None:
        # Export cable without a transformer (MV interconnection over distance).
        lines.append(
            f'  POC -- BUS [label="'
            f'{_edge_label("Export", export.hv_cable.cable_label, export.hv_cable.length_km)}"];'
        )
    else:
        lines.append("  POC -- BUS;")

    # Auxiliary load hanging off the busbar.
    if branch.aux_p_kw or branch.aux_q_kvar:
        lines.append(
            f'  AUX [shape=ellipse, label="Aux\\n{branch.aux_p_kw:g} kW"];'
        )
        lines.append("  BUS -- AUX [style=dashed];")

    # One daisy chain per circuit: BUS -- C1S1 -- C1S2 -- ... Each edge is the
    # cable span feeding the station at its far end; segment 1 is the trunk.
    # Station boxes carry their own model label (mixed fleets supported); the
    # biggest stations sit nearest the busbar by layout convention.
    for circuit in branch.circuits:
        prev = "BUS"
        for station, segment in zip(circuit.stations, circuit.segments):
            node = f"C{circuit.index}S{station.index}"
            lines.append(
                f'  {node} [shape=box, label="TX {circuit.index}.{station.index}\\n'
                f'{station.model}"];'
            )
            run_id = f"C{circuit.index}·S{segment.index}"
            lines.append(
                f'  {prev} -- {node} [label="'
                f'{_edge_label(run_id, segment.cable_label, segment.length_km)}"];'
            )
            prev = node

    lines.append("}")
    return "\n".join(lines)
