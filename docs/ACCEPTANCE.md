# CasePilot acceptance contract

- User requests and audit events persist in SQLAlchemy/PostgreSQL (SQLite test option).
- LangGraph performs classify → permission → approval interrupt → REST execute → result.
- SQLite checkpoints on a durable volume survive process restart. Initial deployment uses one application worker, serial graph mutations, and an independent REST service; distributed workers are not claimed.
- The server derives identity and role from configured bearer credentials; clients cannot select roles by request fields. Development identities are explicit.
- Protected access, escalation, update and deactivation actions cannot execute before an approver resumes the graph. Requesters cannot approve their own actions.
- The allowlisted service validates parameters and deduplicates writes transactionally by operation key; retry after an uncertain HTTP outcome reuses that key.
- Synthetic REST service has real persistent ticket/access records, is independently authenticated and never accepts arbitrary URLs.
- Browser can submit, filter, inspect, approve/reject and safely retry failed cases.
- 200 labeled synthetic scenarios plus integration/security tests exercise meaningful expected outcomes. Test reports record actual execution only.
