import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileText,
  LayoutDashboard,
  Plus,
  RefreshCw,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import "./style.css";

type Event = {
  id: number;
  event: string;
  actor: string;
  created_at: string;
  detail: unknown;
};
type Case = {
  id: string;
  owner: string;
  text: string;
  status: string;
  created_at: string;
  state: {
    proposal?: Record<string, unknown>;
    result?: { summary: string };
    error?: string;
  };
  events?: Event[];
};
const labels = (s: string) => s.replaceAll("_", " ");
export function Status({ value }: { value: string }) {
  return <span className={`status ${value}`}>{labels(value)}</span>;
}
export function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("casepilot-token") || "",
  );
  const [credential, setCredential] = useState("");
  const [me, setMe] = useState<{ user: string; role: string } | null>(null);
  const [rows, setRows] = useState<Case[]>([]),
    [selected, setSelected] = useState<Case | null>(null);
  const [view, setView] = useState("requests"),
    [filter, setFilter] = useState(""),
    [search, setSearch] = useState("");
  const [text, setText] = useState(""),
    [reason, setReason] = useState(""),
    [modal, setModal] = useState(false);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false);
  async function api(path: string, method = "GET", body?: unknown) {
    const response = await fetch("/api" + path, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok)
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : "Please check the submitted fields",
      );
    return result;
  }
  async function refresh() {
    setLoading(true);
    try {
      setMe(await api("/me"));
      setRows(await api("/requests"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (token) void refresh();
  }, [token]);
  async function detail(id: string) {
    try {
      setSelected(await api("/requests/" + id));
      setReason("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const visible = rows.filter(
    (r) =>
      (view !== "approvals" || r.status === "awaiting_approval") &&
      (!filter || r.status === filter) &&
      r.text.toLowerCase().includes(search.toLowerCase()),
  );
  if (!token || !me)
    return (
      <main className="login">
        <div className="brand">
          <Workflow /> CasePilot
        </div>
        <h1>
          Service operations,
          <br />
          with human oversight.
        </h1>
        <p>Sign in to the synthetic enterprise workspace.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sessionStorage.setItem("casepilot-token", credential);
            setToken(credential);
          }}
        >
          <label htmlFor="credential">Development bearer credential</label>
          <input
            id="credential"
            type="password"
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
            required
          />
          <button>Open workspace</button>
        </form>
        <p className="muted">
          Use the requester, approver, or viewer credential from your local
          environment. This demo authentication is not production SSO.
        </p>
        {error && <p role="alert">{error}</p>}
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Workflow /> CasePilot
        </div>
        <div className="workspace">
          <span className="workspace-icon">S</span>
          <div>
            Service workspace<small>Synthetic enterprise</small>
          </div>
        </div>
        <p className="nav-label">OPERATIONS</p>
        <nav>
          <button
            className={view === "requests" ? "active" : ""}
            onClick={() => {
              setView("requests");
              setFilter("");
            }}
          >
            <LayoutDashboard size={19} />
            All requests <span>{rows.length}</span>
          </button>
          <button
            className={view === "approvals" ? "active" : ""}
            onClick={() => {
              setView("approvals");
              setFilter("");
            }}
          >
            <ShieldCheck size={19} />
            Approval queue{" "}
            <span>
              {rows.filter((r) => r.status === "awaiting_approval").length}
            </span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={20} />
          <p>
            Human-guided execution
            <small>Protected actions require approval.</small>
          </p>
        </div>
        <div className="identity">
          <strong>{me.user}</strong>
          <small>{me.role}</small>
          <button
            onClick={() => {
              sessionStorage.removeItem("casepilot-token");
              setToken("");
              setMe(null);
              setRows([]);
              setSelected(null);
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header>
          <div>
            Workspace <span>/</span> Service operations
          </div>
          <span className="demo-badge">LOCAL DEMO</span>
        </header>
        <main>
          <div className="page-title">
            <div>
              <p className="eyebrow">SERVICE OPERATIONS</p>
              <h1>
                {view === "approvals" ? "Approval queue" : "Request overview"}
              </h1>
              <p>From request to resolution. Every decision, visible.</p>
            </div>
            <button onClick={() => setModal(true)}>
              <Plus size={18} /> New request
            </button>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <section className="metrics" aria-label="Request metrics">
            {[
              { label: "Total requests", value: rows.length, icon: FileText },
              {
                label: "Awaiting approval",
                value: rows.filter((r) => r.status === "awaiting_approval")
                  .length,
                icon: Clock3,
              },
              {
                label: "Completed",
                value: rows.filter((r) => r.status === "completed").length,
                icon: CheckCircle2,
              },
              {
                label: "Need attention",
                value: rows.filter((r) =>
                  ["failed", "needs_information"].includes(r.status),
                ).length,
                icon: ShieldCheck,
              },
            ].map((m) => (
              <article key={m.label}>
                <div>
                  {m.label}
                  <m.icon size={19} />
                </div>
                <strong>{m.value}</strong>
                <small>Recorded in this workspace</small>
              </article>
            ))}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>
                  {view === "approvals"
                    ? "Decisions waiting for you"
                    : "Service requests"}
                </h2>
                <p>
                  {view === "approvals"
                    ? "Review the proposed tool and parameters before approving."
                    : "Track agent activity and review outcomes."}
                </p>
              </div>
              <button
                className="secondary"
                onClick={() => void refresh()}
                disabled={loading}
              >
                <RefreshCw size={16} />
                Refresh
              </button>
            </div>
            <div className="filters">
              <input
                aria-label="Search requests"
                placeholder="Search requests…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <select
                aria-label="Filter status"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="">All statuses</option>
                {[
                  "completed",
                  "awaiting_approval",
                  "failed",
                  "rejected",
                  "denied",
                  "needs_information",
                ].map((s) => (
                  <option key={s} value={s}>
                    {labels(s)}
                  </option>
                ))}
              </select>
            </div>
            {loading && (
              <p role="status" className="notice">
                Updating requests…
              </p>
            )}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Request</th>
                    <th>Status</th>
                    <th>Submitted</th>
                    <th>Owner</th>
                    <th>
                      <span className="sr-only">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <button
                          className="text-button"
                          onClick={() => void detail(r.id)}
                        >
                          {r.text}
                        </button>
                        <small>{r.id.slice(0, 8)}</small>
                      </td>
                      <td>
                        <Status value={r.status} />
                      </td>
                      <td>{new Date(r.created_at).toLocaleDateString()}</td>
                      <td>{r.owner}</td>
                      <td>
                        <button
                          className="icon-button"
                          aria-label={`Inspect ${r.text}`}
                          onClick={() => void detail(r.id)}
                        >
                          <ArrowUpRight size={18} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!visible.length && (
              <div className="empty">
                <FileText />
                <h3>No requests here yet</h3>
                <p>
                  Submit a service request to see the agent’s execution trail.
                </p>
              </div>
            )}
            <footer>
              {visible.length} requests shown{" "}
              <span>Source: persisted application records</span>
            </footer>
          </section>
          <div className="info-card">
            <ShieldCheck />
            <div>
              <strong>You stay in control</strong>
              <p>
                Access requests, ticket changes, escalations, and deactivation
                requests pause for an authorized approver.
              </p>
            </div>
          </div>
        </main>
      </div>
      <Dialog.Root open={modal} onOpenChange={setModal}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>New service request</Dialog.Title>
            <Dialog.Description>
              Describe a task, or use a structured tool request. All demo data
              is synthetic.
            </Dialog.Description>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  const row = await api("/requests", "POST", { text });
                  setModal(false);
                  setText("");
                  await detail(row.id);
                });
              }}
            >
              <label htmlFor="request">What do you need?</label>
              <textarea
                id="request"
                required
                minLength={3}
                maxLength={2000}
                rows={5}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Escalate ticket #1024 to the infrastructure team"
              />
              <p className="muted">
                Local mode uses a deterministic planner. Missing details will be
                flagged for clarification.
              </p>
              <button disabled={busy}>
                {busy ? "Submitting…" : "Submit request"}
              </button>
            </form>
            <Dialog.Close className="close" aria-label="Close">
              <X />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog detail">
            <Dialog.Title>Request details</Dialog.Title>
            <Dialog.Description>{selected?.text}</Dialog.Description>
            {selected && (
              <>
                <Status value={selected.status} />
                <h3>Proposed operation</h3>
                <pre>
                  {JSON.stringify(selected.state.proposal || {}, null, 2)}
                </pre>
                {selected.state.result && (
                  <p className="success">{selected.state.result.summary}</p>
                )}
                {selected.state.error && (
                  <p className="error">{selected.state.error}</p>
                )}
                {selected.status === "awaiting_approval" && (
                  <div className="approval">
                    <strong>High-impact action · approval required</strong>
                    {me.role === "approver" && selected.owner !== me.user ? (
                      <>
                        <label htmlFor="reason">Decision reason</label>
                        <input
                          id="reason"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          minLength={3}
                        />
                        <div className="actions">
                          {[true, false].map((approve) => (
                            <button
                              key={String(approve)}
                              className={approve ? "" : "secondary"}
                              disabled={busy || reason.length < 3}
                              onClick={() =>
                                void action(async () => {
                                  await api(
                                    `/requests/${selected.id}/decision`,
                                    "POST",
                                    { approve, reason },
                                  );
                                  await detail(selected.id);
                                })
                              }
                            >
                              {approve ? "Approve action" : "Reject action"}
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p>An independent approver must review this action.</p>
                    )}
                  </div>
                )}
                {selected.status === "failed" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await api(`/requests/${selected.id}/retry`, "POST");
                        await detail(selected.id);
                      })
                    }
                  >
                    Retry safely
                  </button>
                )}
                <h3>Execution history</h3>
                <ol className="timeline">
                  {selected.events?.map((e) => (
                    <li key={e.id}>
                      <strong>{labels(e.event)}</strong>
                      <small>
                        {e.actor} ·{" "}
                        {new Date(e.created_at).toLocaleTimeString()}
                      </small>
                      <pre>{JSON.stringify(e.detail)}</pre>
                    </li>
                  ))}
                </ol>
              </>
            )}
            <Dialog.Close className="close" aria-label="Close">
              <X />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
if (document.getElementById("root"))
  createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
