"""Request-size caps (security review ticket 04): a 413 for bodies over the
limit, a 422 for over-long names. Uses the disposable ``*_test`` Postgres
database injected by ``tests/conftest.py`` for the project-create cases.
"""

import asyncio
import json

from fastapi.testclient import TestClient

import backend.main
from backend.main import app, db
from backend.seed import seed_diagram

client = TestClient(app)

# The ticket's limits, spelled out so each test fails on its own (rather than
# the module failing to import) when the caps are missing.
MAX_BODY_BYTES = 10 * 1024 * 1024
MAX_NAME_LENGTH = 200

BESS_240_MW = {
    "technology": "bess", "pf_target": 1.0, "interconnection": "HV",
    "v_hv_kv": 400.0, "v_mv_kv": 33.0, "export_m": 0.0,
    "bess_station_model": "GENERIC_BESS_TX_4000_LV069",
    "bess_solution": "sungrow-st6900ux-4h", "discharge_hours": 4.0,
    "max_loading_bess": 1.0, "trunk_bess_m": 500.0, "spacing_bess_m": 200.0,
    "p_poc_bess_mw": 240,
}


def test_limits_are_named_module_constants():
    assert getattr(backend.main, "MAX_BODY_BYTES", None) == MAX_BODY_BYTES
    assert getattr(backend.main, "MAX_NAME_LENGTH", None) == MAX_NAME_LENGTH


def test_solve_rejects_a_body_just_over_the_limit_with_413():
    wrapper = len(b'{"pad":""}')
    body = b'{"pad":"' + b"x" * (MAX_BODY_BYTES - wrapper + 1) + b'"}'
    assert len(body) == MAX_BODY_BYTES + 1
    resp = client.post("/api/solve", content=body,
                       headers={"Content-Type": "application/json"})
    assert resp.status_code == 413


def test_the_largest_seeded_plant_still_solves():
    diagram = seed_diagram(BESS_240_MW, db)
    assert len(json.dumps(diagram).encode()) < MAX_BODY_BYTES
    resp = client.post("/api/solve", json=diagram)
    assert resp.status_code == 200


def test_body_without_content_length_is_counted_as_it_streams():
    """A chunked body carries no Content-Length; the middleware must count
    the bytes ``receive()`` delivers and answer 413 once they pass the cap."""
    chunk = b"x" * (1024 * 1024)
    chunks = [chunk] * 11  # 11 MiB, over the 10 MiB cap
    sent: list[dict] = []

    async def receive():
        if chunks:
            return {"type": "http.request", "body": chunks.pop(), "more_body": bool(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/api/solve", "raw_path": b"/api/solve",
        "query_string": b"", "root_path": "",
        "headers": [(b"content-type", b"application/json"),
                    (b"transfer-encoding", b"chunked")],
        "client": ("testclient", 50000), "server": ("testserver", 80),
    }

    asyncio.run(app(scope, receive, send))
    starts = [m for m in sent if m["type"] == "http.response.start"]
    assert starts and starts[0]["status"] == 413


def test_project_name_of_201_characters_is_rejected_with_422():
    resp = client.post("/api/projects", json={"name": "a" * (MAX_NAME_LENGTH + 1)})
    assert resp.status_code == 422


def test_project_name_of_exactly_200_characters_is_accepted():
    resp = client.post("/api/projects", json={"name": "a" * MAX_NAME_LENGTH})
    assert resp.status_code == 201
    assert resp.json()["name"] == "a" * MAX_NAME_LENGTH


def test_design_name_and_editor_are_capped():
    project = client.post("/api/projects", json={"name": "Caps"}).json()
    base = {"name": "D", "technology": "pv",
            "payload": {"schema_version": 1, "nodes": [], "edges": []},
            "last_edited_by": "Alice"}
    url = f"/api/projects/{project['id']}/designs"
    assert client.post(url, json={**base, "name": "a" * (MAX_NAME_LENGTH + 1)}).status_code == 422
    assert client.post(url, json={**base, "last_edited_by": "a" * (MAX_NAME_LENGTH + 1)}).status_code == 422
    design = client.post(url, json=base)
    assert design.status_code == 201
    d = design.json()
    put = {"payload": base["payload"], "version": d["version"], "last_edited_by": "Alice"}
    assert client.put(f"/api/designs/{d['id']}", json={**put, "name": "a" * (MAX_NAME_LENGTH + 1)}).status_code == 422
    assert client.put(f"/api/designs/{d['id']}",
                      json={**put, "last_edited_by": "a" * (MAX_NAME_LENGTH + 1)}).status_code == 422


def test_report_name_of_201_characters_is_rejected_with_422():
    diagram = seed_diagram(BESS_240_MW, db)
    resp = client.post("/api/report", json=diagram, params={"name": "a" * (MAX_NAME_LENGTH + 1)})
    assert resp.status_code == 422


def test_sld_name_of_201_characters_is_rejected_with_422():
    diagram = seed_diagram(BESS_240_MW, db)
    resp = client.post("/api/sld", json=diagram, params={"name": "a" * (MAX_NAME_LENGTH + 1)})
    assert resp.status_code == 422
