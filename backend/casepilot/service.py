"""Synthetic enterprise REST service: independent database and authentication."""

import hashlib
import hmac
import json
from threading import RLock

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy.exc import IntegrityError

from .config import settings
from .contracts import Proposal, ToolResult
from .db import ServiceRecord, ToolReceipt, database


def create_service(db_url: str | None = None, token: str | None = None) -> FastAPI:
    cfg = settings()
    _, sessions = database(db_url or cfg.service_database_url)
    secret = token or cfg.service_token
    lock = RLock()
    api = FastAPI(title="CasePilot synthetic enterprise service")
    with sessions.begin() as db:
        if not db.get(ServiceRecord, 1024):
            db.add(
                ServiceRecord(
                    id=1024,
                    kind="ticket",
                    data={"title": "Synthetic equipment request", "status": "open"},
                )
            )

    @api.get("/health")
    def health():
        return {"status": "ok", "synthetic": True}

    @api.post("/tools/execute", response_model=ToolResult)
    def execute(
        proposal: Proposal,
        authorization: str = Header(),
        idempotency_key: str = Header(min_length=1, max_length=160),
    ):
        if not hmac.compare_digest(authorization, f"Bearer {secret}"):
            raise HTTPException(401, "Invalid service credential")
        fingerprint = hashlib.sha256(
            json.dumps(proposal.model_dump(), sort_keys=True).encode()
        ).hexdigest()

        def cached(receipt):
            if receipt.fingerprint != fingerprint:
                raise HTTPException(409, "Idempotency key reused with different parameters")
            return receipt.result

        try:
            with lock, sessions.begin() as db:
                receipt = db.get(ToolReceipt, idempotency_key)
                if receipt:
                    return cached(receipt)
                op = proposal.operation
                if op in {"get_ticket", "check_status", "update_ticket", "escalate_ticket"}:
                    record = db.get(ServiceRecord, proposal.ticket_id)
                    if not record or record.kind != "ticket":
                        raise HTTPException(404, "Ticket not found")
                    data = dict(record.data)
                    if op == "update_ticket":
                        data["status"] = proposal.status
                    if op == "escalate_ticket":
                        data.update(team=proposal.team, status="escalated")
                    record.data = data
                else:
                    kind = (
                        "ticket"
                        if op == "create_ticket"
                        else "access"
                        if op == "request_access"
                        else "deactivation"
                    )
                    record = ServiceRecord(
                        kind=kind,
                        data={
                            **proposal.model_dump(exclude_none=True),
                            "status": "open" if kind == "ticket" else "requested",
                        },
                    )
                    db.add(record)
                    db.flush()
                result = ToolResult(
                    record_id=record.id,
                    operation=op,
                    status=record.data["status"],
                    summary=f"{op}: record #{record.id} is {record.data['status']}",
                ).model_dump()
                db.add(ToolReceipt(key=idempotency_key, fingerprint=fingerprint, result=result))
                return result
        except IntegrityError:
            with sessions() as db:
                receipt = db.get(ToolReceipt, idempotency_key)
                if receipt:
                    return cached(receipt)
            raise

    return api
