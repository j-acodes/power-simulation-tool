"""Tests for the Markdown sizing-report generator."""

import math

from powertool import (
    Cable,
    Transformer,
    arrange_plant,
    build_report,
    size_architecture,
)
from powertool.sizing import SizingResult


def _tx(s_rated, brand):
    return Transformer(f"TX_{s_rated}", s_rated_kva=s_rated, uk_percent=8.0,
                       pk_kw=0.01 * s_rated, p0_kw=0.001 * s_rated, i0_percent=0.0,
                       lv_kv=0.8, brand=brand)


def _catalogue():
    return [
        Cable("AL_95", r_ohm_per_km=0.32, x_ohm_per_km=0.125, b_us_per_km=42.0,
              cross_section_mm2=95, material="aluminium", rated_current_a=235,
              rated_voltage_kv=20),
        Cable("AL_400", r_ohm_per_km=0.0778, x_ohm_per_km=0.105, b_us_per_km=60.0,
              cross_section_mm2=400, material="aluminium", rated_current_a=565,
              rated_voltage_kv=20),
    ]


def _stage1(p, q):
    s = math.hypot(p, q)
    return SizingResult(p_poc_kw=0.0, q_poc_kvar=0.0, pf_target=0.95,
                        p_inv_kw=p, q_inv_kvar=q, s_inv_kva=s, pf_inv=p / s,
                        losses=[], power_balance_ok=True)


def _hv_catalogue():
    return [Cable("AL_630_132kV", r_ohm_per_km=0.06, x_ohm_per_km=0.18,
                  b_us_per_km=40.0, cross_section_mm2=630, material="aluminium",
                  rated_current_a=700, rated_voltage_kv=132)]


def _arch(hv=True):
    stage1 = _stage1(14_500, 2_000)
    layout = arrange_plant(
        stage1, [(_tx(9000, "BrandA"), 1), (_tx(3300, "BrandB"), 2)],
        max_circuit_current_a=500.0,
        trunk_length_km=0.8, spacing_km=0.35, v_mv_kv=20.0,
    )
    arch = size_architecture(
        layout, stage1, _catalogue(),
        auto_hv=hv, v_hv_kv=132.0 if hv else None,
        hv_cable_candidates=_hv_catalogue() if hv else [],
        hv_cable_length_km=4.0 if hv else 0.0,
        aux_p_kw=120.0, aux_q_kvar=40.0,
        p_poc_target_kw=14_000.0)
    return stage1, arch


def test_report_has_all_sections():
    stage1, arch = _arch()
    md = build_report(stage1, arch, plant_name="Test Plant")
    assert md.startswith("# Test Plant — Sizing Report")
    for section in ("## 0. Plant summary", "## 1. Methodology",
                    "## 2. Stage 1 results", "## 3. Stage 2 results",
                    "### 3.2 Transformer losses", "### 3.3 Cable-run losses"):
        assert section in md, section


def test_report_methodology_mentions_key_rules():
    stage1, arch = _arch()
    md = build_report(stage1, arch)
    # Methodology must explain the load-bound rules and conventions.
    assert "worst case" in md.lower()
    assert "never" in md.lower() and "charging" in md.lower()  # sign convention
    assert "biggest stations" in md.lower()  # arrangement ordering
    assert "per-unit loading" in md.lower()  # mixed fleet


def test_report_tables_list_every_run_and_transformer():
    stage1, arch = _arch()
    md = build_report(stage1, arch)
    # Every cable segment appears by its run id, plus the export run.
    for circuit in arch.circuits:
        for seg in circuit.segments:
            assert f"C{circuit.index}·S{seg.index}" in md
    assert "Export" in md
    # Both station models and the auto-sized MV/HV transformer appear.
    assert "9000 kVA - BrandA" in md
    assert "3300 kVA - BrandB" in md
    assert "(MV/HV)" in md


def test_report_mv_interconnection_no_hv_transformer():
    stage1, arch = _arch(hv=False)
    md = build_report(stage1, arch)
    assert "MV, at 20 kV busbar" in md
    assert "(MV/HV)" not in md
