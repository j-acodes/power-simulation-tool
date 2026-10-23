"""API tests for the efficiency run endpoint (ticket 17).

POST /api/efficiency exposes powertool.efficiency.run_efficiency for the
design on the canvas: the diagram JSON, the ambient rows, cycles per day and
an optional cell RTE in; the rows and warnings out. A run error is a 400.
"""

import csv
import json

from fastapi.testclient import TestClient

from backend.main import app, db
from backend.seed import seed_diagram
from powertool import efficiency_cli

from test_efficiency_design import BESS_PARAMS, HYBRID_PARAMS

client = TestClient(app)


def _bess_design() -> dict:
    return seed_diagram(BESS_PARAMS, db)


def _run(diagram: dict, rows: list[dict], **extra) -> object:
    return client.post("/api/efficiency",
                       json={"diagram": diagram, "rows": rows, "cycles_per_day": 1, **extra})


def test_a_seeded_bess_design_returns_one_row_per_timestamp():
    resp = _run(_bess_design(), [{"timestamp": "t0", "ambient_c": 25.0},
                                 {"timestamp": "t1", "ambient_c": 48.0}])

    assert resp.status_code == 200
    body = resp.json()
    assert [r["timestamp"] for r in body["rows"]] == ["t0", "t1"]
    assert set(body["rows"][0]) == {"timestamp", "operating_rte_pct", "idle_loss_pct",
                                    "pcs_power_pct"}
    assert body["rows"][0]["pcs_power_pct"] == 100.0
    assert body["rows"][1]["pcs_power_pct"] == 76.0
    assert body["warnings"] == []


def test_the_endpoint_matches_the_cli_diagram_run(tmp_path):
    design = _bess_design()
    diagram = tmp_path / "design.json"
    diagram.write_text(json.dumps(design))
    source = tmp_path / "ambient.csv"
    source.write_text("timestamp,ambient_c\nt0,25\n")
    target = tmp_path / "rte.csv"
    assert efficiency_cli.main([str(source), str(target), "--diagram", str(diagram),
                                "--cycles-per-day", "1"]) == 0
    with target.open(newline="") as fh:
        cli_row = list(csv.reader(fh))[1]

    (row,) = _run(design, [{"timestamp": "t0", "ambient_c": 25.0}]).json()["rows"]

    assert cli_row[1] == f"{round(row['operating_rte_pct'], 4):g}"
    assert 80.0 < row["operating_rte_pct"] < 92.08


def test_a_cell_rte_override_changes_the_operating_rte():
    design = _bess_design()
    rows = [{"timestamp": "t0", "ambient_c": 25.0}]

    default = _run(design, rows).json()["rows"][0]["operating_rte_pct"]
    lower = _run(design, rows, cell_rte_pct=90.0).json()["rows"][0]["operating_rte_pct"]

    assert lower < default


def test_a_clamped_ambient_is_a_warning():
    body = _run(_bess_design(), [{"timestamp": "t0", "ambient_c": 80.0}]).json()

    assert any("°C" in w for w in body["warnings"])


def test_a_design_without_a_bess_fleet_is_a_400_with_the_run_error():
    pv_params = {k: v for k, v in HYBRID_PARAMS.items()
                 if "bess" not in k and k != "discharge_hours"}
    pv_only = seed_diagram({**pv_params, "technology": "pv"}, db)

    resp = _run(pv_only, [{"timestamp": "t0", "ambient_c": 25.0}])

    assert resp.status_code == 400
    assert "no BESS fleet" in resp.json()["detail"]


def test_a_design_that_does_not_validate_is_a_400():
    resp = _run({"nodes": [], "edges": []}, [{"timestamp": "t0", "ambient_c": 25.0}])

    assert resp.status_code == 400
    assert "does not validate" in resp.json()["detail"]
