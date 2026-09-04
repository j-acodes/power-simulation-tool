"""Tests for the single-line diagram DOT rendering."""

from dataclasses import replace

import pytest

from powertool import Cable, Transformer
from powertool.architecture import arrange_plant, size_architecture
from powertool.diagram import architecture_to_dot
from powertool.sizing import SizingResult

import math


def _tx_2500() -> Transformer:
    return Transformer("TX_2500", s_rated_kva=2500, uk_percent=6.0, pk_kw=24.0,
                       p0_kw=2.5, i0_percent=0.8, hv_kv=20, lv_kv=0.8)


def _hv_tx() -> Transformer:
    return Transformer("HV_50MVA", s_rated_kva=50_000, uk_percent=12.5, pk_kw=180.0,
                       p0_kw=30.0, i0_percent=0.3, hv_kv=132, lv_kv=20)


def _catalogue() -> list[Cable]:
    return [
        Cable("AL_95", r_ohm_per_km=0.32, x_ohm_per_km=0.125, b_us_per_km=42.0,
              cross_section_mm2=95, material="aluminium", rated_current_a=235,
              rated_voltage_kv=20),
        Cable("AL_400", r_ohm_per_km=0.0778, x_ohm_per_km=0.105, b_us_per_km=60.0,
              cross_section_mm2=400, material="aluminium", rated_current_a=565,
              rated_voltage_kv=20),
    ]


def _stage1(p_inv_kw: float, q_inv_kvar: float) -> SizingResult:
    s = math.hypot(p_inv_kw, q_inv_kvar)
    return SizingResult(
        p_poc_kw=0.0, q_poc_kvar=0.0, pf_target=1.0,
        p_inv_kw=p_inv_kw, q_inv_kvar=q_inv_kvar, s_inv_kva=s,
        pf_inv=p_inv_kw / s, losses=[], power_balance_ok=True,
    )


def _arch(hv: bool = True):
    stage1 = _stage1(43_000, 9_000)
    layout = arrange_plant(
        stage1, [(_tx_2500(), 18)],
        max_circuit_current_a=380.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    return size_architecture(
        layout, stage1, _catalogue(),
        hv_transformer=_hv_tx() if hv else None,
        aux_p_kw=120.0, aux_q_kvar=40.0,
        p_poc_target_kw=42_000.0,
    )


def test_dot_structure_full_plant():
    dot = architecture_to_dot(_arch(hv=True))

    assert dot.startswith("graph plant {")
    assert dot.endswith("}")
    assert "rankdir=TB" in dot  # vertical, like a substation drawing
    assert "splines=line" in dot  # straight edges, no curves
    # Premium/minimal brand styling so the SLD blends into the app.
    assert 'bgcolor="transparent"' in dot
    assert "#ffffff" in dot and "#011d3f" in dot and "#00a438" in dot
    # One node per station (18 stations -> 18 "TX c.k" labels) plus the HV box;
    # each station box carries its own model label (mixed fleets supported).
    assert sum(1 for line in dot.splitlines() if 'label="TX ' in line) == 18
    assert "TX_2500" in dot
    assert "HVTX" in dot and "HV_50MVA" in dot
    assert "MV busbar 20 kV" in dot
    assert 'POC\\n42 MW' in dot
    # Every cable edge carries its run id (matching the lengths editor), the
    # agreed cable label convention, and the span length in metres.
    assert "C1·S1" in dot and "C1·S2" in dot
    assert "Al_3x" in dot
    assert "800 m" in dot and "350 m" in dot
    # Aux load hangs off the busbar.
    assert "AUX" in dot
    # Trunk edges leave the busbar; one per circuit.
    assert sum(1 for line in dot.splitlines() if line.strip().startswith("BUS -- C")) == 4


def test_dot_renders_without_hv_transformer():
    dot = architecture_to_dot(_arch(hv=False))

    assert "HVTX" not in dot
    assert "POC -- BUS" in dot  # delivered straight at the MV busbar
    assert sum(1 for line in dot.splitlines() if 'label="TX ' in line) == 18


def test_dot_is_parseable_when_graphviz_available():
    # Optional sanity check: only runs if the dot CLI is installed.
    import shutil
    import subprocess

    if shutil.which("dot") is None:
        return
    dot = architecture_to_dot(_arch(hv=True))
    proc = subprocess.run(["dot", "-Tcanon"], input=dot.encode(), capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode()


def test_dot_refuses_a_hybrid_rather_than_drawing_one_fleet():
    # Same stance as build_report: the single-line drawing is single-fleet, so
    # a second branch must refuse rather than silently omit a fleet.
    arch = _arch(hv=True)
    hybrid = replace(arch, branches=arch.branches * 2,
                     branch_refinements=arch.branch_refinements * 2)
    with pytest.raises(ValueError, match="2 fleets"):
        architecture_to_dot(hybrid)
