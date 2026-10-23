"""Tests for the BESS efficiency run from a design (ticket 16).

The design's own loss chain (station transformers, collection cables, HV
transformer, export cable) is reused from the engine's forward calculation;
auxiliary consumption is drawn at the MV busbar; in a hybrid, PV is at zero.
Fixtures are seeded through backend.seed exactly as tests/test_seed_bess.py
and tests/test_seed_hybrid.py do.
"""

import csv
import json
from dataclasses import replace

import pytest

from backend.main import db as _db
from backend.seed import seed_diagram
from powertool import ComponentDatabase, efficiency_cli
from powertool.architecture import _delivered_with_frozen_cables
from powertool.graph import graph_to_inputs
from powertool.plant import solve_architecture
from powertool.efficiency import (DesignConfiguration, EfficiencyRunError, TypedConfiguration,
                                  resolve_design, run_efficiency)


@pytest.fixture(scope="module")
def db() -> ComponentDatabase:
    return _db


# A seeded 100 MW / 4 h BESS-only design behind a 132/33 kV HV transformer:
# the seed places 58 ST6900UX-4H containers on 15 MVS7400-LS stations.
BESS_PARAMS = {
    "technology": "bess",
    "pf_target": 1.0,
    "interconnection": "HV",
    "v_mv_kv": 33.0,
    "v_hv_kv": 132.0,
    "export_m": 5000.0,
    "bess_station_model": "SUNGROW_MVS7400_LS",
    "bess_solution": "sungrow-st6900ux-4h",
    "discharge_hours": 4.0,
    "p_poc_bess_mw": 100.0,
    "max_loading_bess": 1.0,
    "trunk_bess_m": 500.0,
    "spacing_bess_m": 200.0,
}


@pytest.fixture(scope="module")
def bess_design(db) -> dict:
    return seed_diagram(BESS_PARAMS, db)


def test_a_seeded_bess_design_supplies_station_count_solution_and_poc_capacity(db, bess_design):
    fleet = resolve_design(bess_design, db)

    assert fleet.solution == "sungrow-st6900ux-4h"
    assert fleet.stations == 15
    assert fleet.containers == 58
    assert fleet.poc_capacity_kw == 100_000.0


def test_a_seeded_bess_design_runs(db, bess_design):
    config = DesignConfiguration(diagram=bess_design, cycles_per_day=1)

    result = run_efficiency([("t", 25.0)], config, db)

    (row,) = result.rows
    # Below the container-only 92.08 % (losses and auxiliaries), well above 80 %.
    assert 80.0 < row.operating_rte_pct < 92.08
    assert row.idle_loss_kwh_per_h > 0
    assert row.pcs_power_pct == 100.0


def _bess_branch(diagram, db):
    """The design's solved BESS branch and shared export step, straight from
    the engine's own diagram solve."""
    inputs = graph_to_inputs(diagram, db)
    _s, _l, arch = solve_architecture(inputs, db)
    (i,) = [i for i, b in enumerate(inputs.branches) if b.kind == "bess"]
    return arch.branches[i], arch.export


@pytest.mark.parametrize("p_ac_kw", [20_000.0, 60_000.0, 99_992.0])
def test_discharge_losses_are_the_engine_forward_calculation(db, bess_design, p_ac_kw):
    branch, export = _bess_branch(bess_design, db)
    # The engine's own forward cascade with no auxiliary load at the busbar,
    # the containers' AC power split as the design allocates it.
    branch = replace(branch, sections=[replace(s, aux_p_kw=0.0, aux_q_kvar=0.0)
                                       for s in branch.sections])
    p_lv_total = sum(p.p_lv_kw for plans in branch.layout.circuit_plans for p in plans)
    engine_kw, *_ = _delivered_with_frozen_cables(
        [branch], export, [p_ac_kw / p_lv_total], q_k=[0.0])

    chain = resolve_design(bess_design, db).chain

    assert chain.export_kw(p_ac_kw, 0.0) == pytest.approx(engine_kw, rel=1e-12)


@pytest.mark.parametrize("p_kw", [20_000.0, 99_992.0])
def test_charge_losses_are_the_same_kw_loss_function_as_discharge(db, bess_design, p_kw):
    chain = resolve_design(bess_design, db).chain

    discharge_loss = p_kw - chain.export_kw(p_kw, 0.0)
    charge_loss = chain.import_kw(p_kw, 0.0) - p_kw

    # Same element losses at the same power; they differ only by the loss on
    # the loss (each element sees the other leg's losses on its far side).
    assert charge_loss == pytest.approx(discharge_loss, rel=0.02)
    assert chain.ac_from_import(chain.import_kw(p_kw, 0.0), 0.0) == pytest.approx(p_kw)
    assert chain.ac_for_export(chain.export_kw(p_kw, 0.0), 0.0) == pytest.approx(p_kw)


def test_auxiliary_consumption_carries_hv_transformer_and_export_losses_only(db, bess_design):
    chain = resolve_design(bess_design, db).chain
    p_kw, aux_kw = 60_000.0, 1_000.0

    extra = chain.export_kw(p_kw, 0.0) - chain.export_kw(p_kw, aux_kw)

    # Less than the draw itself: drawn at the MV busbar, the auxiliary load
    # lightens the HV transformer (whose load loss falls with it); it never
    # passes through a station transformer or a collection cable.
    assert aux_kw * 0.99 < extra < aux_kw
    # Charging, the draw comes through the HV transformer and adds its load loss.
    extra_import = chain.import_kw(p_kw, aux_kw) - chain.import_kw(p_kw, 0.0)
    assert aux_kw < extra_import < aux_kw * 1.01


def test_cli_runs_from_a_design_diagram_file(tmp_path, bess_design, capsys):
    diagram = tmp_path / "design.json"
    diagram.write_text(json.dumps(bess_design))
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\nt0,25\n")
    target = tmp_path / "rte.csv"

    code = efficiency_cli.main([str(source), str(target), "--diagram", str(diagram),
                                "--cycles-per-day", "1"])

    assert code == 0
    with target.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["timestamp", "operating RTE %", "idle loss kWh/h", "PCS power % of rated"]
    assert rows[1][0] == "t0" and rows[1][3] == "100"


def test_cli_rejects_typed_station_figures_alongside_a_diagram(tmp_path, bess_design):
    diagram = tmp_path / "design.json"
    diagram.write_text(json.dumps(bess_design))

    with pytest.raises(SystemExit):
        efficiency_cli.main(["in.csv", "out.csv", "--diagram", str(diagram),
                             "--stations", "4"])


def test_design_idle_figure_uses_station_and_hv_transformer_no_load(db, bess_design):
    design = run_efficiency([("t", 25.0)], DesignConfiguration(bess_design, cycles_per_day=1), db)
    # The same fleet typed in with no no-load loss: the difference is the
    # design's no-load draw, 15 MVS7400-LS x 7.4 kW + the auto-sized 125 MVA
    # HV transformer's 0.06 % = 75 kW: 186 kWh per idle hour.
    typed = TypedConfiguration(
        solution="sungrow-st6900ux-4h", station_transformer="SUNGROW_MVS7400_LS",
        stations=15, containers=58, poc_capacity_kw=90_000.0,
        load_loss_pct=0.0, no_load_loss_pct=0.0, cycles_per_day=1)
    bare = run_efficiency([("t", 25.0)], typed, db)

    difference = design.rows[0].idle_loss_kwh_per_h - bare.rows[0].idle_loss_kwh_per_h
    assert difference == pytest.approx(186.0, abs=1e-6)


HYBRID_PARAMS = {
    "technology": "hybrid",
    "pf_target": 0.95,
    "interconnection": "HV",
    "v_mv_kv": 33.0,
    "v_hv_kv": 132.0,
    "export_m": 2000.0,
    "p_poc_mw": 20.0,
    "station_model": "SUNGROW_MVS3200",
    "pv_inverter": "sungrow-sg350hx-20",
    "inverter_count": 5,
    "max_loading": 0.85,
    "trunk_m": 300.0,
    "spacing_m": 100.0,
    "p_poc_bess_mw": 10.0,
    "discharge_hours": 4.0,
    "bess_solution": "sungrow-st6900ux-4h",
    "bess_station_model": "SUNGROW_MVS7400_LS",
    "max_loading_bess": 1.0,
    "trunk_bess_m": 300.0,
    "spacing_bess_m": 100.0,
}


def test_a_hybrid_design_runs_with_pv_at_zero_and_the_hv_no_load_in_full(db):
    diagram = seed_diagram(HYBRID_PARAMS, db)

    fleet = resolve_design(diagram, db)
    result = run_efficiency([("t", 25.0)], DesignConfiguration(diagram, cycles_per_day=1), db)

    # The BESS fleet alone: 2 MVS7400-LS stations, 7 containers, its own 10 MW.
    assert (fleet.stations, fleet.containers, fleet.poc_capacity_kw) == (2, 7, 10_000.0)
    # No PV station transformer counts; the shared 40 MVA HV transformer
    # (sized on PV and BESS together) counts in full: 2 x 7.4 + 0.06 % x 40 MVA.
    assert fleet.chain.no_load_kw == pytest.approx(2 * 7.4 + 24.0)
    assert 80.0 < result.rows[0].operating_rte_pct < 92.08


def test_a_design_without_a_bess_fleet_is_an_error(db):
    pv_params = {k: v for k, v in HYBRID_PARAMS.items()
                 if "bess" not in k and k != "discharge_hours"}
    pv_only = seed_diagram({**pv_params, "technology": "pv"}, db)

    with pytest.raises(EfficiencyRunError, match="no BESS fleet"):
        run_efficiency([("t", 25.0)], DesignConfiguration(pv_only, cycles_per_day=1), db)


def test_a_solution_that_conflicts_with_the_design_is_an_error(db, bess_design):
    config = DesignConfiguration(bess_design, solution="sungrow-st6680ux-2h", cycles_per_day=1)

    with pytest.raises(EfficiencyRunError, match="conflicts with the design"):
        run_efficiency([("t", 25.0)], config, db)


def test_a_design_that_does_not_validate_is_an_error(db):
    with pytest.raises(EfficiencyRunError, match="does not validate"):
        run_efficiency([("t", 25.0)], DesignConfiguration({"nodes": [], "edges": []}), db)
