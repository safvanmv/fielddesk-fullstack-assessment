import { useState } from "react";
import type { FormEvent } from "react";

import type { UserRole, WorkOrder, WorkOrderStatus } from "../../lib/types";

interface WorkOrderDetailsProps {
  order: WorkOrder;
  role: UserRole;
  error: string | null;
  isWorking: boolean;
  onBack: () => void;
  onEdit: () => void;
  onUpload: (file: File) => Promise<void>;
  onProgress: (status: WorkOrderStatus, note: string) => Promise<void>;
}

function displayDate(date: string | null): string {
  return date
    ? new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(date))
    : "Not scheduled";
}

function readableAction(action: string): string {
  return action.replaceAll("_", " ");
}

// Internal identifiers that mean nothing to a reader of the history.
const HIDDEN_CHANGE_FIELDS = new Set(["event_id"]);

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "" || value === "None") {
    return "—";
  }
  return String(value);
}

/** One readable line per audited field: "status: scheduled → in_progress", "note: …". */
function describeChanges(changes: Record<string, unknown>): string[] {
  return Object.entries(changes)
    .filter(([field]) => !HIDDEN_CHANGE_FIELDS.has(field))
    .flatMap(([field, value]) => {
      const label = field.replaceAll("_", " ");
      if (typeof value === "object" && value !== null) {
        if ("before" in value && "after" in value) {
          return [`${label}: ${displayValue(value.before)} → ${displayValue(value.after)}`];
        }
        return [];
      }
      return value === null || value === "" ? [] : [`${label}: ${String(value)}`];
    });
}

function isWorkOrderStatus(value: string): value is WorkOrderStatus {
  return value === "in_progress" || value === "completed";
}

export function WorkOrderDetails({
  order,
  role,
  error,
  isWorking,
  onBack,
  onEdit,
  onUpload,
  onProgress,
}: WorkOrderDetailsProps) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<WorkOrderStatus>("in_progress");
  const [note, setNote] = useState("");
  const canManage = role === "owner" || role === "dispatcher";
  const canReportProgress =
    role === "technician" && order.status !== "completed";

  async function upload() {
    if (!file) return;
    await onUpload(file);
    setFile(null);
  }

  async function submitProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onProgress(status, note.trim());
    setNote("");
  }

  return (
    <main className="content-shell">
      <div className="page-heading">
        <div>
          <button className="text-button" onClick={onBack}>
            ← Work orders
          </button>
          <p className="eyebrow">{order.reference}</p>
          <h1>{order.title}</h1>
          <p>{order.site_name}</p>
        </div>
        {canManage && (
          <button className="button button-secondary" onClick={onEdit}>
            Edit work order
          </button>
        )}
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <div className="detail-layout">
        <div className="detail-card">
          <div className="panel-heading">
            <h2>Job details</h2>
            <span className={`status-pill status-pill--${order.status}`}>
              {readableAction(order.status)}
            </span>
          </div>
          <p>{order.description}</p>
          <div className="detail-meta">
            <div>
              <span>Priority</span>
              <strong>{order.priority}</strong>
            </div>
            <div>
              <span>Assigned technician</span>
              <strong>{order.assigned_technician?.name ?? "Unassigned"}</strong>
            </div>
            <div>
              <span>Scheduled start</span>
              <strong>{displayDate(order.scheduled_start)}</strong>
            </div>
            <div>
              <span>Scheduled end</span>
              <strong>{displayDate(order.scheduled_end)}</strong>
            </div>
          </div>

          <hr className="section-divider" />
          <h2>Attachments</h2>
          {order.attachments.length ? (
            <ul className="file-list">
              {order.attachments.map((attachment) => (
                <li key={attachment.id}>
                  <a href={attachment.download_url}>
                    {attachment.original_name}
                  </a>{" "}
                  <span className="file-size">
                    ({Math.ceil(attachment.size_bytes / 1024)} KB)
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p>No attachments have been added.</p>
          )}
          {canManage && (
            <div className="attachment-upload">
              <label className="field">
                <span>Add an image or PDF (maximum 10 MB)</span>
                <input
                  accept="image/*,application/pdf"
                  className="file-input"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
              <button
                className="button button-secondary"
                disabled={!file || isWorking}
                onClick={() => void upload()}
              >
                Upload attachment
              </button>
            </div>
          )}

          {canReportProgress && (
            <>
              <hr className="section-divider" />
              <h2>Submit a progress update</h2>
              <form className="form-stack" onSubmit={submitProgress}>
                <label className="field">
                  <span>New status</span>
                  <select
                    onChange={(event) =>
                      isWorkOrderStatus(event.target.value) &&
                      setStatus(event.target.value)
                    }
                    value={status}
                  >
                    <option value="in_progress">In progress</option>
                    <option value="completed">Completed</option>
                  </select>
                </label>
                <label className="field">
                  <span>Note</span>
                  <textarea
                    maxLength={1000}
                    onChange={(event) => setNote(event.target.value)}
                    required
                    value={note}
                  />
                </label>
                <button className="button button-primary" disabled={isWorking}>
                  {isWorking ? "Submitting…" : "Submit update"}
                </button>
              </form>
            </>
          )}
        </div>

        <aside className="detail-card">
          <h2>Activity history</h2>
          {order.activity.length ? (
            <ol className="activity-list">
              {order.activity.map((entry) => (
                <li key={entry.id}>
                  <strong>
                    {entry.actor_name} {readableAction(entry.action)}
                  </strong>
                  {describeChanges(entry.changes).map((line) => (
                    <span className="activity-change" key={line}>
                      {line}
                    </span>
                  ))}
                  <time dateTime={entry.created_at}>
                    {displayDate(entry.created_at)}
                  </time>
                </li>
              ))}
            </ol>
          ) : (
            <p>No activity recorded yet.</p>
          )}
        </aside>
      </div>
    </main>
  );
}
