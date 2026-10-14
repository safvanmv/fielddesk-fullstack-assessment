import { useEffect, useState } from "react";

import { getDashboardSummary, getWorkOrders } from "../../lib/api";
import type {
  DashboardSummary,
  UserRole,
  WorkOrder,
} from "../../lib/types";

interface DashboardPageProps {
  role: UserRole;
  onCreate: () => void;
  onSelect: (workOrder: WorkOrder) => void;
  onExport: () => void;
}

// Real-time event types that change what the dashboard shows (see record_change in the backend).
const WORK_ORDER_EVENT_TYPES = [
  "work_order.created",
  "work_order.updated",
  "work_order.status_changed",
  "work_order.note_added",
  "attachment.added",
];

const emptySummary: DashboardSummary = {
  open: 0,
  scheduled: 0,
  in_progress: 0,
  completed: 0,
};

function formatDate(date: string | null): string {
  if (!date) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(date));
}

export function DashboardPage({
  role,
  onCreate,
  onSelect,
  onExport,
}: DashboardPageProps) {
  const [summary, setSummary] = useState(emptySummary);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [liveState, setLiveState] = useState<"connected" | "reconnecting">(
    "connected",
  );

  const canManage = role === "owner" || role === "dispatcher";
  const pageSize = 20;

  useEffect(() => {
    // Only a changed search triggers a reload. Setting `isLoading` without a new
    // search would leave the list on "Loading…" with no request to clear it.
    if (searchInput === search) return;
    const timeout = window.setTimeout(() => {
      setIsLoading(true);
      setError(null);
      setSearch(searchInput);
      setPage(1);
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [searchInput, search]);

  useEffect(() => {
    let active = true;
    Promise.all([
      getDashboardSummary(),
      getWorkOrders(search, status, page, priority, ordering),
    ])
      .then(([nextSummary, nextPage]) => {
        if (!active) return;
        setSummary(nextSummary);
        setOrders(nextPage.results);
        setCount(nextPage.count);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load work orders. Try again.",
        );
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [ordering, page, priority, reloadVersion, search, status]);

  useEffect(() => {
    const events = new EventSource("/api/events/stream/");
    const refresh = () => setReloadVersion((version) => version + 1);
    const fallbackRefresh = window.setInterval(refresh, 30_000);
    events.onopen = () => setLiveState("connected");
    events.onerror = () => setLiveState("reconnecting");
    // The server sends named events (`event: work_order.updated`), which never reach `onmessage`.
    for (const type of WORK_ORDER_EVENT_TYPES) {
      events.addEventListener(type, refresh);
    }
    return () => {
      for (const type of WORK_ORDER_EVENT_TYPES) {
        events.removeEventListener(type, refresh);
      }
      events.close();
      window.clearInterval(fallbackRefresh);
    };
  }, []);

  const statItems = [
    { label: "Open", value: summary.open },
    { label: "Scheduled", value: summary.scheduled },
    { label: "In progress", value: summary.in_progress },
    { label: "Completed", value: summary.completed },
  ];

  return (
    <main className="content-shell">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Work orders</h1>
          <p>Monitor the schedule and keep your field team on track.</p>
        </div>
        {canManage && (
          <div className="button-row">
            <button className="button button-secondary" onClick={onExport}>
              Export CSV
            </button>
            <button className="button button-primary" onClick={onCreate}>
              Create work order
            </button>
          </div>
        )}
      </div>

      <section className="stat-grid" aria-label="Work order summary">
        {statItems.map((item) => (
          <article className="stat-card" key={item.label}>
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="table-card" aria-labelledby="work-orders-heading">
        <div className="table-toolbar">
          <h2 id="work-orders-heading">All work orders</h2>
          <div className="toolbar">
            <label>
              <span className="sr-only">Search work orders</span>
              <input
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search work orders"
                type="search"
                value={searchInput}
              />
            </label>
            <label>
              <span className="sr-only">Filter by status</span>
              <select
                onChange={(event) => {
                  setIsLoading(true);
                  setError(null);
                  setStatus(event.target.value);
                  setPage(1);
                }}
                value={status}
              >
                <option value="">All statuses</option>
                <option value="open">Open</option>
                <option value="scheduled">Scheduled</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by priority</span>
              <select
                onChange={(event) => {
                  setIsLoading(true);
                  setError(null);
                  setPriority(event.target.value);
                  setPage(1);
                }}
                value={priority}
              >
                <option value="">All priorities</option>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Sort work orders</span>
              <select
                onChange={(event) => {
                  setIsLoading(true);
                  setError(null);
                  setOrdering(event.target.value);
                  setPage(1);
                }}
                value={ordering}
              >
                <option value="-created_at">Newest first</option>
                <option value="created_at">Oldest first</option>
                <option value="scheduled_start">Schedule: earliest first</option>
                <option value="-scheduled_start">Schedule: latest first</option>
                <option value="priority">Priority</option>
              </select>
            </label>
            <span className="live-indicator" role="status">
              <span className={`live-dot live-dot--${liveState}`} />
              {liveState === "connected" ? "Live updates" : "Reconnecting"}
            </span>
          </div>
        </div>

        {error && (
          <div className="error-banner" role="alert">
            {error}{" "}
            <button
              onClick={() => {
                setIsLoading(true);
                setError(null);
                setReloadVersion((version) => version + 1);
              }}
            >
              Retry
            </button>
          </div>
        )}

        {isLoading ? (
          <p className="loading-state" role="status">
            Loading work orders…
          </p>
        ) : orders.length === 0 ? (
          <div className="empty-state">
            <strong>No work orders found</strong>
            <p>Try changing your search, or create a work order to get started.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Work order</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Technician</th>
                  <th>Scheduled</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td>{order.reference}</td>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => onSelect(order)}
                      >
                        {order.title}
                      </button>
                    </td>
                    <td>
                      <span
                        className={`status-pill status-pill--${order.status}`}
                      >
                        {order.status.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>{order.priority}</td>
                    <td>{order.assigned_technician?.name ?? "Unassigned"}</td>
                    <td>{formatDate(order.scheduled_start)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!isLoading && count > pageSize && (
          <div className="pagination">
            <span>
              Showing {(page - 1) * pageSize + 1}–
              {Math.min(page * pageSize, count)} of {count}
            </span>
            <div className="button-row">
              <button
                className="button button-secondary"
                disabled={page === 1}
                onClick={() => {
                  setIsLoading(true);
                  setError(null);
                  setPage((current) => current - 1);
                }}
              >
                Previous
              </button>
              <button
                className="button button-secondary"
                disabled={page * pageSize >= count}
                onClick={() => {
                  setIsLoading(true);
                  setError(null);
                  setPage((current) => current + 1);
                }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
