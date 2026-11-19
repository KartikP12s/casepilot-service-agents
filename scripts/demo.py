"""Exercise actual network endpoints; requires running Docker Compose services."""

import os
import uuid

import httpx

base = os.getenv("API_URL", "http://localhost:8000")
user = {
    "Authorization": "Bearer " + os.getenv("USER_TOKEN", "local-user-only"),
    "Idempotency-Key": str(uuid.uuid4()),
}
approver = {"Authorization": "Bearer " + os.getenv("APPROVER_TOKEN", "local-approver-only")}
with httpx.Client(base_url=base, timeout=20) as client:
    response = client.post(
        "/api/requests", json={"text": "Escalate ticket #1024 to infrastructure team"}, headers=user
    )
    response.raise_for_status()
    row = response.json()
    assert row["status"] == "awaiting_approval", row
    path = f"/api/requests/{row['id']}"
    forbidden = client.post(
        path + "/decision", json={"approve": True, "reason": "Not authorized"}, headers=user
    )
    assert forbidden.status_code == 403
    response = client.post(
        path + "/decision",
        json={"approve": True, "reason": "Reviewed synthetic demo"},
        headers=approver,
    )
    response.raise_for_status()
    assert response.json()["status"] == "completed", response.text
    audit = client.get(path, headers=user).json()
    assert any(event["event"] == "tool_completed" for event in audit["events"])
    print(f"PASS: {row['id']}: persistent approval, RBAC, REST execution and audit trail")
