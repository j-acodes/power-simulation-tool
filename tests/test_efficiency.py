"""Tests for the BESS efficiency run (powertool.efficiency), without a design.

Expected figures come from the spec's worked example
(.scratch/rte-efficiency/spec.md, "Further Notes"), computed by hand.
"""

import csv
from dataclasses import replace

import pytest

from powertool import ComponentDatabase, efficiency_cli
from powertool.components import MvsAuxBand
from powertool.efficiency import EfficiencyRunError, TypedConfiguration, run_efficiency


@pytest.fixture(scope="module")
def db() -> ComponentDatabase:
    return ComponentDatabase.load()


# The spec's worked example: 64 ST6900UX-4H containers behind 16 MVS7400-LS
# stations, 100 MW POC, load loss 1 %, no-load 0.1 %, 1 cycle/day.
WORKED = TypedConfiguration(
    solution="sungrow-st6900ux-4h",
    station_transformer="SUNGROW_MVS7400_LS",
    stations=16,
    containers=64,
    poc_capacity_kw=100_000.0,
    load_loss_pct=1.0,
    no_load_loss_pct=0.1,
    cycles_per_day=1,
)


def test_worked_example_at_25c_reproduces_the_hand_calculation(db):
    result = run_efficiency([("2026-07-01T00:00", 25.0)], WORKED, db)

    (row,) = result.rows
    assert row.timestamp == "2026-07-01T00:00"
    # Hand calculation: 88.64 % (spec, Further Notes).
    assert row.operating_rte_pct == pytest.approx(88.64, abs=0.01)


def _without_auxiliaries(db: ComponentDatabase) -> ComponentDatabase:
    """The real catalogue with every auxiliary-consumption figure at zero."""
    solution = db.bess_solution("sungrow-st6900ux-4h")
    zero_tables = tuple(
        replace(t, operating_kw=[0.0] * len(t.ambient_c), standby_kw=[0.0] * len(t.ambient_c))
        for t in solution.aux_consumption)
    station = replace(db.bess_transformer("SUNGROW_MVS7400_LS"), mvs_aux_consumption=(
        MvsAuxBand(-30, 50, 0.0, 0.0),))
    return ComponentDatabase(
        bess_solutions={**db.bess_solutions,
                        solution.name: replace(solution, aux_consumption=zero_tables)},
        bess_transformers={**db.bess_transformers, station.name: station},
        bess_pairings=db.bess_pairings,
    )


@pytest.mark.parametrize("ambient", [-30.0, 0.0, 25.0, 40.0])
def test_container_only_rte_is_cell_rte_times_conversion_squared(db, ambient):
    config = replace(WORKED, load_loss_pct=0.0, no_load_loss_pct=0.0)

    result = run_efficiency([("t", ambient)], config, _without_auxiliaries(db))

    # Spec: 0.95 x 0.98454^2 = 92.08 %, at every ambient.
    assert result.rows[0].operating_rte_pct == pytest.approx(92.08, abs=0.01)
    assert result.warnings == []


@pytest.mark.parametrize("change, message", [
    ({"containers": 65}, "exceed 16 stations x 4"),
    ({"poc_capacity_kw": 64 * 1724.0}, "below the installed rated active power"),
    ({"station_transformer": "GENERIC_BESS_TX_1750_LV100"}, "not paired"),
    ({"solution": "no-such-solution"}, "not found"),
])
def test_invalid_configuration_is_an_error(db, change, message):
    with pytest.raises(EfficiencyRunError, match=message):
        run_efficiency([("t", 25.0)], replace(WORKED, **change), db)


def _with_solution(db: ComponentDatabase, **changes) -> ComponentDatabase:
    solution = replace(db.bess_solution("sungrow-st6900ux-4h"), **changes)
    return ComponentDatabase(
        bess_solutions={solution.name: solution},
        bess_transformers=db.bess_transformers, bess_pairings=db.bess_pairings)


def test_solution_without_rated_active_power_is_an_error(db):
    with pytest.raises(EfficiencyRunError, match="rated active power"):
        run_efficiency([("t", 25.0)], WORKED, _with_solution(db, rated_active_power_kw=None))


def test_solution_without_container_table_is_an_error(db):
    with pytest.raises(EfficiencyRunError, match="auxiliary-consumption table"):
        run_efficiency([("t", 25.0)], WORKED, _with_solution(db, aux_consumption=()))


def test_station_without_mvs_table_counts_zero_and_warns(db):
    station = replace(db.bess_transformer("SUNGROW_MVS7400_LS"), mvs_aux_consumption=())
    catalogue = ComponentDatabase(
        bess_solutions=db.bess_solutions,
        bess_transformers={**db.bess_transformers, station.name: station},
        bess_pairings=db.bess_pairings)

    result = run_efficiency([("a", 25.0), ("b", 30.0)], WORKED, catalogue)
    with_table = run_efficiency([("a", 25.0)], WORKED, db)

    assert len(result.rows) == 2
    assert len(result.warnings) == 1
    assert "SUNGROW_MVS7400_LS" in result.warnings[0]
    # 16 x 4.02 kW less auxiliary draw: a slightly better RTE.
    assert result.rows[0].operating_rte_pct > with_table.rows[0].operating_rte_pct


WORKED_ARGS = [
    "--solution", "sungrow-st6900ux-4h", "--station-transformer", "SUNGROW_MVS7400_LS",
    "--stations", "16", "--containers", "64", "--poc-capacity-kw", "100000",
    "--load-loss-pct", "1.0", "--no-load-loss-pct", "0.1", "--cycles-per-day", "1",
]


def test_cli_reads_ambients_and_writes_the_four_column_csv(tmp_path, capsys):
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\n2026-07-01 00:00,25\n2026-07-01 01:00,25.0\n")
    target = tmp_path / "rte.csv"

    exit_code = efficiency_cli.main([str(source), str(target), *WORKED_ARGS])

    assert exit_code == 0
    with target.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["timestamp", "operating RTE %", "idle loss %", "PCS power % of rated"]
    assert [r[0] for r in rows[1:]] == ["2026-07-01 00:00", "2026-07-01 01:00"]
    assert float(rows[1][1]) == pytest.approx(88.64, abs=0.01)
    assert rows[1][3] == "100"
    assert capsys.readouterr().err == ""


def test_cli_prints_warnings_outside_the_csv(tmp_path, capsys):
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\nt0,25\n")
    target = tmp_path / "rte.csv"
    args = [a if a != "SUNGROW_MVS7400_LS" else "GENERIC_BESS_TX_4000_LV069"
            for a in WORKED_ARGS]
    args[args.index("--stations") + 1] = "32"

    assert efficiency_cli.main([str(source), str(target), *args]) == 0

    assert "warning:" in capsys.readouterr().err
    assert "warning" not in target.read_text()


def test_cli_reports_an_invalid_configuration_and_fails(tmp_path, capsys):
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\nt0,25\n")
    args = [*WORKED_ARGS]
    args[args.index("--containers") + 1] = "65"

    exit_code = efficiency_cli.main([str(source), str(tmp_path / "rte.csv"), *args])

    assert exit_code != 0
    assert "exceed" in capsys.readouterr().err
    assert not (tmp_path / "rte.csv").exists()


# --- Hot-ambient PCS derating (ticket 14) -----------------------------------

def test_worked_example_at_48c_runs_at_the_derated_power(db):
    result = run_efficiency([("t", 48.0)], WORKED, db)

    (row,) = result.rows
    # Hand calculation (spec, Further Notes): d = 0.76, RTE 87.59 %, with the
    # charge leg importing 85,954 kW, below the 100 MW POC capacity.
    assert row.pcs_power_pct == pytest.approx(76.0)
    assert row.operating_rte_pct == pytest.approx(87.59, abs=0.01)
    assert result.warnings == []


@pytest.mark.parametrize("ambient, pcs_pct", [(45.0, 100.0), (48.0, 76.0), (50.0, 60.0)])
def test_derating_is_never_counted_as_a_loss(db, ambient, pcs_pct):
    config = replace(WORKED, load_loss_pct=0.0, no_load_loss_pct=0.0)

    (row,) = run_efficiency([("t", ambient)], config, _without_auxiliaries(db)).rows

    # With no loss chain and no auxiliaries the derated cycle moves the same
    # energy, so RTE stays rho x eta^2 = 92.08 % however far the PCS derates.
    assert row.pcs_power_pct == pytest.approx(pcs_pct)
    assert row.operating_rte_pct == pytest.approx(92.08, abs=0.01)


def test_solution_without_derating_curve_runs_at_rated_power_and_warns(db):
    result = run_efficiency([("a", 48.0), ("b", 50.0)], WORKED, _with_solution(db, derating=None))

    assert [r.pcs_power_pct for r in result.rows] == [100.0, 100.0]
    assert len(result.warnings) == 1
    assert "derating" in result.warnings[0]


def test_out_of_range_ambients_clamp_to_the_edge_with_one_warning(db):
    rows = [("a", -35.0), ("b", 25.0), ("c", 55.0), ("d", 60.0), ("e", -31.0), ("f", 50.0)]

    result = run_efficiency(rows, WORKED, db)
    edges = run_efficiency([("cold", -30.0), ("hot", 50.0)], WORKED, db).rows

    by_ts = {r.timestamp: r for r in result.rows}
    for ts in ("a", "e"):
        assert by_ts[ts].operating_rte_pct == edges[0].operating_rte_pct
    for ts in ("c", "d"):
        assert by_ts[ts].operating_rte_pct == edges[1].operating_rte_pct
        assert by_ts[ts].pcs_power_pct == pytest.approx(60.0)
    (warning,) = result.warnings
    # Four timestamps clamped (50 °C is on the edge, not outside it); the
    # extremes seen are -35 and 60 °C.
    assert "4 timestamps" in warning
    assert "-35" in warning and "60" in warning


def test_cli_writes_the_derated_pcs_power_and_the_clamp_warning(tmp_path, capsys):
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\nt0,48\nt1,55\n")
    target = tmp_path / "rte.csv"

    assert efficiency_cli.main([str(source), str(target), *WORKED_ARGS]) == 0

    with target.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert [r[3] for r in rows[1:]] == ["76", "60"]
    err = capsys.readouterr().err
    assert err.count("warning:") == 1
    assert "1 timestamp had" in err
