import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { UserRole, WorkOrder } from "../../lib/types";
import { WorkOrderDetails } from "./WorkOrderDetails";

const order: WorkOrder = {
  id: "wo-1",
  reference: "FD-7K3M9QX2",
  title: "Repair pump",
  description: "",
  priority: "high",
  status: "in_progress",
  assigned_technician: { id: "3", name: "tech", username: "tech", email: "" },
  scheduled_start: null,
  scheduled_end: null,
  site_name: "Plant 1",
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-01T10:00:00Z",
  attachments: [],
  activity: [
    {
      id: "1",
      action: "work_order.status_changed",
      actor_name: "tech",
      created_at: "2026-10-01T10:05:00Z",
      changes: { status: { before: "scheduled", after: "in_progress" }, event_id: "evt-1" },
    },
    {
      id: "2",
      action: "work_order.note_added",
      actor_name: "tech",
      created_at: "2026-10-01T10:06:00Z",
      changes: { note: "Replaced the seal", event_id: "evt-2" },
    },
  ],
};

function renderAs(role: UserRole) {
  const noop = async () => {};
  return render(
    <WorkOrderDetails
      error={null}
      isWorking={false}
      onBack={() => {}}
      onEdit={() => {}}
      onProgress={noop}
      onUpload={noop}
      order={order}
      role={role}
    />,
  );
}

describe("WorkOrderDetails", () => {
  it("offers attachment upload to dispatchers but not to technicians", () => {
    renderAs("dispatcher");
    expect(screen.getByRole("button", { name: "Upload attachment" })).toBeInTheDocument();
  });

  it("hides attachment upload from technicians, whom the API refuses", () => {
    renderAs("technician");
    expect(screen.queryByRole("button", { name: "Upload attachment" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit update" })).toBeInTheDocument();
  });

  it("shows what changed in each activity entry, without internal ids", () => {
    renderAs("dispatcher");
    expect(screen.getByText("status: scheduled → in_progress")).toBeInTheDocument();
    expect(screen.getByText("note: Replaced the seal")).toBeInTheDocument();
    expect(screen.queryByText(/evt-1/)).not.toBeInTheDocument();
  });
});
