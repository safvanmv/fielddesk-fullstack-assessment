import type {
  ActivityEntry,
  CurrentUser,
  DashboardSummary,
  OrganizationMember,
  OrganizationSettings,
  Page,
  Technician,
  WorkOrder,
  WorkOrderInput,
  WorkOrderStatus,
  UserRole,
} from "./types";

interface LoginResponse {
  user: CurrentUser;
}

export function getErrorMessage(body: unknown, status: number): string {
  const fallback = `Request failed (${status}).`;
  if (typeof body !== "object" || body === null) return fallback;

  const record = body as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (typeof record.message === "string") return record.message;
  if (typeof record.error === "object" && record.error !== null) {
    // The API's error envelope: {"error": {"code", "message", "details", "request_id"}}.
    // Handle it fully here; falling through would print the envelope itself.
    const envelope = record.error as Record<string, unknown>;
    const detailsMessage = getErrorMessage(envelope.details, status);
    if (detailsMessage !== fallback) return detailsMessage;
    if (
      typeof envelope.message === "string" &&
      envelope.message !== "Request failed."
    ) {
      return envelope.message;
    }
    return fallback;
  }
  if (record.errors && typeof record.errors === "object") {
    return Object.entries(record.errors)
      .map(([field, errors]) => {
        const messages = Array.isArray(errors) ? errors.join(", ") : String(errors);
        return `${field}: ${messages}`;
      })
      .join(" ");
  }
  const fieldMessages = Object.entries(record)
    .filter(([field]) => !["code", "message", "request_id"].includes(field))
    .map(([field, errors]) => {
      const messages = Array.isArray(errors) ? errors.join(", ") : String(errors);
      // DRF reports errors that are not tied to one field under "non_field_errors".
      return field === "non_field_errors" ? messages : `${field}: ${messages}`;
    });
  if (fieldMessages.length) return fieldMessages.join(" ");
  return fallback;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  const cookie = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const method = (options.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrfToken = readCookie("csrftoken");
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body: unknown = await response.json();
      message = getErrorMessage(body, response.status);
    } catch {
      // Keep the HTTP status message when the response isn't JSON.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function getCsrfToken(): Promise<void> {
  await request<void>("/api/auth/csrf/");
}

export async function login(
  username: string,
  password: string,
): Promise<CurrentUser> {
  await getCsrfToken();
  const response = await request<LoginResponse>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  clearTechnicianLookup();
  return response.user;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/api/auth/me/");
}

export async function logout(): Promise<void> {
  await request<void>("/api/auth/logout/", { method: "POST" });
  clearTechnicianLookup();
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const response = await request<{
    total: number;
    by_status: Record<string, number>;
  }>("/api/dashboard/");
  return {
    open: response.by_status.open ?? 0,
    scheduled: response.by_status.scheduled ?? 0,
    in_progress: response.by_status.in_progress ?? 0,
    completed: response.by_status.completed ?? 0,
  };
}

interface ApiAttachment {
  id: string;
  name: string;
  size: number;
  content_type: string;
}

interface ApiWorkOrder extends Omit<WorkOrder, "assigned_technician" | "attachments" | "activity"> {
  assigned_technician: number | string | null;
  attachments: ApiAttachment[];
}

interface ApiActivityEntry {
  id: string;
  action: string;
  actor: string | null;
  created_at: string;
  changes?: Record<string, unknown>;
}

function technicianName(value: unknown): unknown {
  if (value === null || value === undefined || value === "None") return value;
  return technicianLookup.get(String(value))?.name ?? value;
}

/** Audit entries store technician IDs; show usernames instead where we know them. */
function withTechnicianNames(changes: Record<string, unknown> = {}): Record<string, unknown> {
  const assigned = changes.assigned_technician;
  if (assigned === undefined) return changes;
  if (typeof assigned === "object" && assigned !== null && "before" in assigned && "after" in assigned) {
    return {
      ...changes,
      assigned_technician: { before: technicianName(assigned.before), after: technicianName(assigned.after) },
    };
  }
  return { ...changes, assigned_technician: technicianName(assigned) };
}

function normalizeWorkOrder(order: ApiWorkOrder, activity: ActivityEntry[] = []): WorkOrder {
  const technicianId = order.assigned_technician;
  const technician = technicianId === null
    ? null
    : technicianLookup.get(String(technicianId)) ?? {
        id: String(technicianId),
        name: "Assigned technician",
        username: "",
        email: "",
      };
  return {
    ...order,
    assigned_technician: technician,
    attachments: order.attachments.map((attachment) => ({
      id: attachment.id,
      original_name: attachment.name,
      size_bytes: attachment.size,
      download_url: `/api/attachments/${attachment.id}/download/`,
    })),
    activity,
  };
}

const technicianLookup = new Map<string, Technician>();
let technicianRequest: Promise<Technician[]> | null = null;

function clearTechnicianLookup() {
  technicianLookup.clear();
  technicianRequest = null;
}

export async function getWorkOrders(
  search: string,
  status: string,
  page: number,
  priority: string,
  ordering: string,
): Promise<Page<WorkOrder>> {
  const query = new URLSearchParams({
    page: String(page),
    page_size: "20",
    ordering,
  });
  if (search.trim()) query.set("search", search.trim());
  if (status) query.set("status", status);
  if (priority) query.set("priority", priority);
  const response = await request<{
    count: number;
    page: number;
    page_size: number;
    results: ApiWorkOrder[];
  }>(`/api/work-orders/?${query.toString()}`);
  await getTechnicians();
  return {
    count: response.count,
    next: response.page * response.page_size < response.count
      ? String(response.page + 1)
      : null,
    previous: response.page > 1 ? String(response.page - 1) : null,
    results: response.results.map((order) => normalizeWorkOrder(order)),
  };
}

export async function getWorkOrder(id: string): Promise<WorkOrder> {
  const [order, rawActivity] = await Promise.all([
    request<ApiWorkOrder>(`/api/work-orders/${id}/`),
    request<ApiActivityEntry[]>(`/api/work-orders/${id}/activity/`),
    getTechnicians(),
  ]);
  const activity = rawActivity.map((entry) => ({
    id: String(entry.id),
    action: entry.action,
    actor_name: entry.actor ?? "System",
    created_at: entry.created_at,
    changes: withTechnicianNames(entry.changes),
  }));
  return normalizeWorkOrder(order, activity);
}

export async function getTechnicians(): Promise<Technician[]> {
  if (!technicianRequest) {
    technicianRequest = request<
      { id: number | string; username: string; email: string }[]
    >("/api/technicians/").then((response) => {
      const technicians = response.map((technician) => ({
        id: String(technician.id),
        name: technician.username,
        username: technician.username,
        email: technician.email,
      }));
      for (const technician of technicians) {
        technicianLookup.set(technician.id, technician);
      }
      return technicians;
    }).catch((error: unknown) => {
      technicianRequest = null;
      throw error;
    });
  }
  return technicianRequest;
}

export async function getOrganizationSettings(): Promise<OrganizationSettings> {
  return request<OrganizationSettings>("/api/organization/settings/");
}

export async function updateOrganizationSettings(
  input: Pick<OrganizationSettings, "name" | "storage_limit_bytes">,
): Promise<OrganizationSettings> {
  return request<OrganizationSettings>("/api/organization/settings/", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function getOrganizationMembers(): Promise<OrganizationMember[]> {
  return request<OrganizationMember[]>("/api/users/");
}

export async function createOrganizationMember(input: {
  username: string;
  email: string;
  password: string;
  role: UserRole;
}): Promise<OrganizationMember> {
  return request<OrganizationMember>("/api/users/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateOrganizationMember(
  id: number,
  input: Partial<Pick<OrganizationMember, "role" | "active">>,
): Promise<OrganizationMember> {
  return request<OrganizationMember>(`/api/users/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function saveWorkOrder(
  input: WorkOrderInput,
  id?: string,
): Promise<WorkOrder> {
  const order = await request<ApiWorkOrder>(
    id ? `/api/work-orders/${id}/` : "/api/work-orders/",
    {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify({
        ...input,
        assigned_technician: input.assigned_technician
          ? Number(input.assigned_technician)
          : null,
      }),
    },
  );
  return normalizeWorkOrder(order);
}

export async function submitProgress(
  workOrderId: string,
  status: WorkOrderStatus,
  note: string,
): Promise<void> {
  await request<void>("/api/progress-events/", {
    method: "POST",
    body: JSON.stringify({
      eventId: crypto.randomUUID(),
      workOrderId,
      type: "status_changed",
      occurredAt: new Date().toISOString(),
      payload: { status, note },
    }),
  });
}

export async function uploadAttachment(
  workOrderId: string,
  file: File,
): Promise<void> {
  const formData = new FormData();
  formData.set("file", file);
  await request<void>(`/api/work-orders/${workOrderId}/attachments/`, {
    method: "POST",
    body: formData,
  });
}

export function getAttachmentUrl(id: string): string {
  return `/api/attachments/${id}/download/`;
}
