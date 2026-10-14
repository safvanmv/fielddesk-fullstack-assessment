import { useState } from "react";
import type { FormEvent } from "react";

import type {
  Technician,
  WorkOrder,
  WorkOrderInput,
  WorkOrderPriority,
} from "../../lib/types";

interface WorkOrderFormProps {
  initialOrder?: WorkOrder;
  technicians: Technician[];
  isSaving: boolean;
  onCancel: () => void;
  onSave: (input: WorkOrderInput) => Promise<void>;
}

interface FormState {
  title: string;
  description: string;
  priority: WorkOrderPriority;
  status: WorkOrder["status"];
  assignedTechnicianId: string;
  scheduledStart: string;
  scheduledEnd: string;
  siteName: string;
}

const blankForm: FormState = {
  title: "",
  description: "",
  priority: "normal",
  status: "open",
  assignedTechnicianId: "",
  scheduledStart: "",
  scheduledEnd: "",
  siteName: "",
};

function toLocalDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toIsoDateTime(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

function isPriority(value: string): value is WorkOrderPriority {
  return ["low", "normal", "high", "urgent"].includes(value);
}

function isWorkOrderStatusValue(
  value: string,
): value is WorkOrder["status"] {
  return [
    "open",
    "scheduled",
    "in_progress",
    "completed",
    "cancelled",
  ].includes(value);
}

function toFormState(initialOrder?: WorkOrder): FormState {
  if (!initialOrder) return blankForm;
  return {
    title: initialOrder.title,
    description: initialOrder.description,
    priority: initialOrder.priority,
    status: initialOrder.status,
    assignedTechnicianId: initialOrder.assigned_technician?.id ?? "",
    scheduledStart: toLocalDateTime(initialOrder.scheduled_start),
    scheduledEnd: toLocalDateTime(initialOrder.scheduled_end),
    siteName: initialOrder.site_name,
  };
}

export function WorkOrderForm({
  initialOrder,
  technicians,
  isSaving,
  onCancel,
  onSave,
}: WorkOrderFormProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(initialOrder));
  const [validationError, setValidationError] = useState<string | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);
    if (
      form.scheduledStart &&
      form.scheduledEnd &&
      new Date(form.scheduledEnd) <= new Date(form.scheduledStart)
    ) {
      setValidationError("The scheduled end must be after the scheduled start.");
      return;
    }

    await onSave({
      title: form.title.trim(),
      description: form.description.trim(),
      priority: form.priority,
      status: form.status,
      assigned_technician: form.assignedTechnicianId || null,
      scheduled_start: toIsoDateTime(form.scheduledStart),
      scheduled_end: toIsoDateTime(form.scheduledEnd),
      site_name: form.siteName.trim(),
    });
  }

  return (
    <main className="content-shell">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{initialOrder?.reference ?? "Work order"}</p>
          <h1>{initialOrder ? "Edit work order" : "Create work order"}</h1>
          <p>
            Add the job details, site, schedule, and technician assignment.
            {!initialOrder && " A reference number is assigned when you save."}
          </p>
        </div>
      </div>
      <section className="panel">
        <form className="form-grid" onSubmit={submit}>
          <label className="field">
            <span>Title</span>
            <input
              maxLength={200}
              onChange={(event) => update("title", event.target.value)}
              required
              value={form.title}
            />
          </label>
          <label className="field">
            <span>Site name</span>
            <input
              maxLength={200}
              onChange={(event) => update("siteName", event.target.value)}
              required
              value={form.siteName}
            />
          </label>
          <label className="field">
            <span>Priority</span>
            <select
              onChange={(event) => {
                if (isPriority(event.target.value)) {
                  update("priority", event.target.value);
                }
              }}
              value={form.priority}
            >
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          <label className="field">
            <span>Status</span>
            <select
              onChange={(event) =>
                isWorkOrderStatusValue(event.target.value) &&
                update("status", event.target.value)
              }
              value={form.status}
            >
              <option value="open">Open</option>
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <label className="field">
            <span>Assigned technician</span>
            <select
              onChange={(event) =>
                update("assignedTechnicianId", event.target.value)
              }
              value={form.assignedTechnicianId}
            >
              <option value="">Unassigned</option>
              {technicians.map((technician) => (
                <option key={technician.id} value={technician.id}>
                  {technician.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Scheduled start</span>
            <input
              onChange={(event) => update("scheduledStart", event.target.value)}
              type="datetime-local"
              value={form.scheduledStart}
            />
          </label>
          <label className="field">
            <span>Scheduled end</span>
            <input
              onChange={(event) => update("scheduledEnd", event.target.value)}
              type="datetime-local"
              value={form.scheduledEnd}
            />
          </label>
          <label className="field field-wide">
            <span>Description</span>
            <textarea
              maxLength={5000}
              onChange={(event) => update("description", event.target.value)}
              required
              value={form.description}
            />
          </label>
          {validationError && (
            <p className="form-error field-wide" role="alert">
              {validationError}
            </p>
          )}
          <div className="button-row field-wide">
            <button
              className="button button-secondary"
              onClick={onCancel}
              type="button"
            >
              Cancel
            </button>
            <button className="button button-primary" disabled={isSaving}>
              {isSaving ? "Saving…" : "Save work order"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
