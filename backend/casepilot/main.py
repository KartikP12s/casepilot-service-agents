import hmac
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import RLock

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from sqlalchemy import select

from .config import Settings, settings
from .contracts import Decision, Submission
from .db import Audit, Request, database
from .tools import RestTools
from .workflow import build_graph


def create_app(cfg: Settings | None = None, tools=None) -> FastAPI:
    cfg = cfg or settings()
    engine, sessions = database(cfg.database_url)
    lock = RLock()
    windows = defaultdict(deque)
    tools = tools or RestTools(cfg.service_url, cfg.service_token, cfg.tool_timeout)

    def audit(rid, actor, event, detail):
        with sessions.begin() as db:
            db.add(Audit(request_id=rid, actor=actor, event=event, detail=detail))

    graph, connection = build_graph(cfg.checkpoint_path, tools, audit)

    @asynccontextmanager
    async def lifespan(app):
        yield
        connection.close()
        engine.dispose()
        if hasattr(tools, "client"):
            tools.client.close()

    app = FastAPI(title="CasePilot", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[cfg.cors_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.state.graph = graph

    def identity(authorization: str = Header(default="")):
        for token, user, role in [
            (cfg.user_token, "demo.requester", "requester"),
            (cfg.approver_token, "demo.approver", "approver"),
            (cfg.viewer_token, "demo.viewer", "viewer"),
        ]:
            if hmac.compare_digest(authorization, f"Bearer {token}"):
                with lock:
                    queue = windows[user]
                    while queue and queue[0] < time.monotonic() - 60:
                        queue.popleft()
                    if len(queue) >= 120:
                        raise HTTPException(429, "Rate limit exceeded")
                    queue.append(time.monotonic())
                return {"user": user, "role": role}
        raise HTTPException(401, "Valid development bearer credential required")

    def serialize(row):
        return {
            "id": row.id,
            "owner": row.owner,
            "text": row.text,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "state": row.state,
        }

    def get_owned(db, rid, user):
        row = db.get(Request, rid)
        if row is None or (row.owner != user["user"] and user["role"] != "approver"):
            raise HTTPException(404, "Request not found")
        return row

    def sync(rid):
        snapshot = graph.get_state({"configurable": {"thread_id": rid}})
        state = dict(snapshot.values)
        pending = any(task.interrupts for task in snapshot.tasks)
        status = "awaiting_approval" if pending else state.get("status", "received")
        with sessions.begin() as db:
            row = db.get(Request, rid)
            row.state = state
            row.status = status
            return serialize(row)

    def run(rid, value):
        try:
            graph.invoke(value, {"configurable": {"thread_id": rid}})
        except Exception:
            logging.exception("workflow_error", extra={"request_id": rid})
            audit(rid, "system", "workflow_error", {})
            raise HTTPException(503, "Workflow interrupted; retry with the same idempotency key")
        return sync(rid)

    @app.get("/health")
    def health():
        with sessions() as db:
            db.execute(select(1))
        return {"status": "ok", "planner": "deterministic-local"}

    @app.get("/api/me")
    def me(user=Depends(identity)):
        return user

    @app.get("/api/requests")
    def listing(status: str | None = None, user=Depends(identity)):
        with sessions() as db:
            query = select(Request).order_by(Request.created_at.desc()).limit(500)
            if user["role"] != "approver":
                query = query.where(Request.owner == user["user"])
            if status:
                query = query.where(Request.status == status)
            ids = [r.id for r in db.scalars(query)]
        with lock:
            return [sync(rid) for rid in ids]

    @app.post("/api/requests", status_code=201)
    def submit(
        payload: Submission,
        idempotency_key: str = Header(min_length=1, max_length=100),
        user=Depends(identity),
    ):
        key = user["user"] + ":" + idempotency_key
        with lock:
            with sessions.begin() as db:
                existing = db.scalar(select(Request).where(Request.idempotency_key == key))
                if existing:
                    if existing.text != payload.text:
                        raise HTTPException(
                            409, "Idempotency key already used for a different request"
                        )
                    rid = existing.id
                else:
                    rid = str(uuid.uuid4())
                    db.add(
                        Request(id=rid, owner=user["user"], text=payload.text, idempotency_key=key)
                    )
            config = {"configurable": {"thread_id": rid}}
            snapshot = graph.get_state(config)
            if snapshot.values:
                if snapshot.next and not any(t.interrupts for t in snapshot.tasks):
                    return run(rid, None)
                return sync(rid)
            audit(rid, user["user"], "received", {})
            return run(
                rid, {"id": rid, "text": payload.text, "owner": user["user"], "role": user["role"]}
            )

    @app.get("/api/requests/{rid}")
    def detail(rid: str, user=Depends(identity)):
        with sessions() as db:
            get_owned(db, rid, user)
            events = [
                {
                    "id": e.id,
                    "actor": e.actor,
                    "event": e.event,
                    "detail": e.detail,
                    "created_at": e.created_at.isoformat(),
                }
                for e in db.scalars(select(Audit).where(Audit.request_id == rid).order_by(Audit.id))
            ]
        with lock:
            return {**sync(rid), "events": events}

    @app.post("/api/requests/{rid}/decision")
    def decision(rid: str, payload: Decision, user=Depends(identity)):
        if user["role"] != "approver":
            raise HTTPException(403, "Approver role required")
        with lock, sessions() as db:
            row = get_owned(db, rid, user)
            if row.owner == user["user"]:
                raise HTTPException(403, "Self-approval is prohibited")
            if sync(rid)["status"] != "awaiting_approval":
                raise HTTPException(409, "Request is not awaiting approval")
            audit(
                rid,
                user["user"],
                "approved" if payload.approve else "rejected",
                {"reason": payload.reason},
            )
            return run(rid, Command(resume=payload.model_dump()))

    @app.post("/api/requests/{rid}/retry")
    def retry(rid: str, user=Depends(identity)):
        with lock, sessions() as db:
            get_owned(db, rid, user)
            current = sync(rid)
            if current["status"] != "failed":
                raise HTTPException(409, "Only failed tool executions can be retried")
            # Reuse persisted approved parameters and original operation key.
            graph.update_state(
                {"configurable": {"thread_id": rid}}, {"status": "ready"}, as_node="approval"
            )
            audit(rid, user["user"], "retry_requested", {})
            return run(rid, None)

    return app
