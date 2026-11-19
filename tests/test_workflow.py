import httpx
import pytest
from casepilot.config import Settings
from casepilot.main import create_app
from casepilot.service import create_service
from casepilot.tools import RestTools
from fastapi.testclient import TestClient


@pytest.fixture
def setup(tmp_path):
    service = TestClient(create_service(f"sqlite:///{tmp_path}/service.db", "service"))
    calls = []

    def transport(req):
        calls.append(req)
        result = service.post(req.url.path, content=req.content, headers=dict(req.headers))
        return httpx.Response(result.status_code, json=result.json())

    tools = RestTools("http://service", "service", transport=httpx.MockTransport(transport))
    cfg = Settings(
        database_url=f"sqlite:///{tmp_path}/app.db",
        checkpoint_path=str(tmp_path / "checkpoints.db"),
    )
    return cfg, tools, calls


def headers(role="user", key="one"):
    return {"Authorization": f"Bearer local-{role}-only", "Idempotency-Key": key}


def test_approval_survives_restart(setup):
    cfg, tools, calls = setup
    with TestClient(create_app(cfg, tools)) as client:
        row = client.post(
            "/api/requests",
            json={"text": "Escalate ticket #1024 to infrastructure team"},
            headers=headers(),
        ).json()
        assert row["status"] == "awaiting_approval"
        assert calls == []
        assert (
            client.post(
                f"/api/requests/{row['id']}/decision",
                json={"approve": True, "reason": "Reviewed"},
                headers=headers(),
            ).status_code
            == 403
        )
    # New HTTP client because lifespan closes the first; checkpoints and SQL survive.
    tools.client = httpx.Client(base_url="http://service", transport=tools.client._transport)
    with TestClient(create_app(cfg, tools)) as client:
        response = client.post(
            f"/api/requests/{row['id']}/decision",
            json={"approve": True, "reason": "Reviewed"},
            headers=headers("approver"),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        assert len(calls) == 1
        events = client.get(f"/api/requests/{row['id']}", headers=headers()).json()["events"]
        assert {e["event"] for e in events} >= {
            "received",
            "classified",
            "permission_checked",
            "approved",
            "tool_completed",
        }
        assert (
            client.post(
                f"/api/requests/{row['id']}/decision",
                json={"approve": True, "reason": "Again"},
                headers=headers("approver"),
            ).status_code
            == 409
        )


def test_reject_and_role_isolation(setup):
    cfg, tools, calls = setup
    with TestClient(create_app(cfg, tools)) as c:
        row = c.post(
            "/api/requests", json={"text": "Request access to analytics"}, headers=headers()
        ).json()
        assert c.get(f"/api/requests/{row['id']}", headers=headers("viewer")).status_code == 404
        result = c.post(
            f"/api/requests/{row['id']}/decision",
            json={"approve": False, "reason": "No business need"},
            headers=headers("approver"),
        )
        assert result.json()["status"] == "rejected"
        assert not calls
        denied = c.post(
            "/api/requests",
            json={"text": "Create support ticket for broken laptop"},
            headers=headers("viewer"),
        ).json()
        assert denied["status"] == "denied"
        assert not calls


def test_idempotency_and_validation(setup):
    cfg, tools, calls = setup
    with TestClient(create_app(cfg, tools)) as c:
        payload = {"text": "Create support ticket for broken laptop"}
        first = c.post("/api/requests", json=payload, headers=headers()).json()
        assert first["status"] == "completed"
        assert c.post("/api/requests", json=payload, headers=headers()).json()["id"] == first["id"]
        assert len(calls) == 1
        assert (
            c.post("/api/requests", json={"text": "Different text"}, headers=headers()).status_code
            == 409
        )
        assert (
            c.post(
                "/api/requests", json={**payload, "role": "approver"}, headers=headers(key="two")
            ).status_code
            == 422
        )
        assert c.get("/api/requests").status_code == 401
        assert c.post(f"/api/requests/{first['id']}/retry", headers=headers()).status_code == 409


def test_service_receipts(tmp_path):
    with TestClient(create_service(f"sqlite:///{tmp_path}/service.db", "service")) as c:
        h = {"Authorization": "Bearer service", "Idempotency-Key": "same"}
        p = {"operation": "create_ticket", "title": "Laptop repair"}
        first = c.post("/tools/execute", json=p, headers=h)
        assert first.status_code == 200
        assert c.post("/tools/execute", json=p, headers=h).json() == first.json()
        assert (
            c.post("/tools/execute", json={**p, "title": "Changed"}, headers=h).status_code == 409
        )
        assert (
            c.post(
                "/tools/execute", json=p, headers={**h, "Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )


def test_safe_retry_after_timeout(setup):
    cfg, tools, calls = setup
    original = tools.execute

    def broken(*args):
        raise httpx.ReadTimeout("timeout")

    tools.execute = broken
    with TestClient(create_app(cfg, tools)) as c:
        row = c.post(
            "/api/requests", json={"text": "Request access to analytics"}, headers=headers()
        ).json()
        failed = c.post(
            f"/api/requests/{row['id']}/decision",
            json={"approve": True, "reason": "Approved request"},
            headers=headers("approver"),
        ).json()
        assert failed["status"] == "failed"
        tools.execute = original
        result = c.post(f"/api/requests/{row['id']}/retry", headers=headers()).json()
        assert result["status"] == "completed"
        assert len(calls) == 1
