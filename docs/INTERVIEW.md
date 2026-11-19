# Interview walkthrough

## 30 seconds

CasePilot is a service-agent dashboard that turns a request into a validated IT tool operation. LangGraph pauses high-impact operations for an independent approver, persists the pause across restarts, then calls a separate REST service. I tested the policy boundary, restart behavior and idempotency with 200 synthetic cases and additional API/browser tests. Its local planner and shared development identities are deliberately scoped demo adapters.

## Two minutes

Start in the React request dashboard and submit an escalation for ticket 1024. FastAPI authenticates the requester, validates input and creates a server-owned thread ID. The graph classifies the request, validates a typed proposal and checks permissions. A protected action reaches a persistent interrupt, so no REST call occurs yet. An independent approver inspects the proposal and resumes the graph. The executor calls a fixed service endpoint with a stable idempotency key. The service commits its mutation and receipt together; repeated calls return the original response. The dashboard reads the resulting state and ordered audit events. Show a rejected request, then the evaluation category report. Explain that PostgreSQL stores application and service records while a persistent SQLite volume holds graph checkpoints. A single API worker is an explicit constraint, not a hidden claim of distributed reliability.

## Hardest engineering decision

Separating replay-safe side effects from restartable graph nodes. Graph execution can replay after a crash, and a timeout cannot establish whether a remote mutation happened. A durable service receipt keyed to the request makes those retries safe, while a changed payload with the same key is rejected.

## Reliability and security

Bounded HTTP retries, persistent interrupts, schema validation, server-derived roles, self-approval rejection, fixed endpoints, database-backed idempotency receipts and transparent audit history. Production OIDC and an atomic audit outbox remain future work.

## Likely questions

1. **Why not execute the action before approval and undo it?** Some actions are irreversible, and rollback is not authorization. The graph stops before the executor, and tests assert zero outgoing calls while approval is pending.
2. **What if the HTTP request times out after commit?** The retry uses the original key. The service either returns its committed receipt or executes once if the first transaction never committed. A payload hash prevents key reuse for different operations.
3. **How would you scale this?** Replace the SQLite checkpointer with PostgreSQL storage, use database leases or a durable queue, and atomically record approval/audit changes through an outbox. The current deployment deliberately supports one API worker.
