"""Tests for the M4 Projects/Designs persistence API (CRUD, optimistic
locking 409 conflict path, cascade delete). Uses the tmp-file SQLite DB
injected by ``tests/conftest.py`` — never touches a real ``powertool.db``.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

SAMPLE_PAYLOAD = {"schema_version": 1, "nodes": [], "edges": []}


def _create_project(name: str = "Test Project") -> dict:
    resp = client.post("/api/projects", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def _create_design(project_id: int, name: str = "Design A") -> dict:
    resp = client.post(
        f"/api/projects/{project_id}/designs",
        json={"name": name, "payload": SAMPLE_PAYLOAD, "last_edited_by": "Alice"},
    )
    assert resp.status_code == 201
    return resp.json()


def test_project_crud_happy_path():
    project = _create_project("Plant Alpha")
    assert project["name"] == "Plant Alpha"
    assert project["design_count"] == 0

    listed = client.get("/api/projects").json()
    assert any(p["id"] == project["id"] for p in listed)

    detail = client.get(f"/api/projects/{project['id']}").json()
    assert detail["id"] == project["id"]
    assert detail["designs"] == []

    resp = client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404


def test_design_crud_happy_path():
    project = _create_project("Plant Beta")
    design = _create_design(project["id"], "Alt 1")

    assert design["version"] == 1
    assert design["project_id"] == project["id"]
    assert design["payload"] == SAMPLE_PAYLOAD

    got = client.get(f"/api/designs/{design['id']}")
    assert got.status_code == 200
    assert got.json()["payload"] == SAMPLE_PAYLOAD

    # Project detail lists the design summary, without the payload.
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert len(detail["designs"]) == 1
    assert "payload" not in detail["designs"][0]
    assert detail["designs"][0]["id"] == design["id"]

    resp = client.delete(f"/api/designs/{design['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/designs/{design['id']}").status_code == 404


def test_project_delete_cascades_designs():
    project = _create_project("Plant Gamma")
    design = _create_design(project["id"])

    resp = client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/designs/{design['id']}").status_code == 404


def test_update_design_success_bumps_version():
    project = _create_project("Plant Delta")
    design = _create_design(project["id"])

    new_payload = {"schema_version": 1, "nodes": [{"id": "n1"}], "edges": []}
    resp = client.put(
        f"/api/designs/{design['id']}",
        json={
            "name": "Alt 1 renamed",
            "payload": new_payload,
            "version": 1,
            "last_edited_by": "Bob",
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["version"] == 2
    assert updated["name"] == "Alt 1 renamed"
    assert updated["payload"] == new_payload
    assert updated["last_edited_by"] == "Bob"


def test_update_design_stale_version_returns_409_with_server_copy_then_succeeds():
    project = _create_project("Plant Epsilon")
    design = _create_design(project["id"])

    # Someone else saves first, bumping the server version to 2.
    first_save = client.put(
        f"/api/designs/{design['id']}",
        json={"payload": {"schema_version": 1, "nodes": [], "edges": []}, "version": 1, "last_edited_by": "Bob"},
    )
    assert first_save.status_code == 200
    assert first_save.json()["version"] == 2

    # Stale client still thinks it's version 1 -> conflict.
    conflict = client.put(
        f"/api/designs/{design['id']}",
        json={"payload": {"schema_version": 1, "nodes": [], "edges": []}, "version": 1, "last_edited_by": "Alice"},
    )
    assert conflict.status_code == 409
    body = conflict.json()["detail"]
    assert body["design"]["id"] == design["id"]
    assert body["design"]["version"] == 2
    assert body["design"]["last_edited_by"] == "Bob"

    # Client reloads, retries with the fresh version -> success, version bumps again.
    retry = client.put(
        f"/api/designs/{design['id']}",
        json={"payload": {"schema_version": 1, "nodes": [], "edges": []}, "version": 2, "last_edited_by": "Alice"},
    )
    assert retry.status_code == 200
    assert retry.json()["version"] == 3
    assert retry.json()["last_edited_by"] == "Alice"


def test_404s_for_missing_ids():
    assert client.get("/api/projects/999999").status_code == 404
    assert client.delete("/api/projects/999999").status_code == 404
    assert client.get("/api/designs/999999").status_code == 404
    assert client.delete("/api/designs/999999").status_code == 404
    resp = client.post(
        "/api/projects/999999/designs",
        json={"name": "x", "payload": SAMPLE_PAYLOAD, "last_edited_by": "Alice"},
    )
    assert resp.status_code == 404
    resp = client.put(
        "/api/designs/999999",
        json={"payload": SAMPLE_PAYLOAD, "version": 1, "last_edited_by": "Alice"},
    )
    assert resp.status_code == 404
