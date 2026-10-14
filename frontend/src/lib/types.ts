export type UserRole = "owner" | "dispatcher" | "technician";

export type WorkOrderStatus =
  | "open"
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled";

export type WorkOrderPriority = "low" | "normal" | "high" | "urgent";

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  organization_name: string;
}

export interface OrganizationSettings {
  id: number;
  name: string;
  storage_limit_bytes: number;
  storage_used_bytes: number;
}

export interface OrganizationMember {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  active: boolean;
}

export interface Technician {
  id: string;
  name: string;
  username: string;
  email: string;
}

export interface Attachment {
  id: string;
  original_name: string;
  download_url: string;
  size_bytes: number;
}

export interface ActivityEntry {
  id: string;
  action: string;
  actor_name: string;
  created_at: string;
  /** Audit details: plain values, or {before, after} pairs for changed fields. */
  changes: Record<string, unknown>;
}

export interface WorkOrder {
  id: string;
  reference: string;
  title: string;
  description: string;
  priority: WorkOrderPriority;
  status: WorkOrderStatus;
  assigned_technician: Technician | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  site_name: string;
  created_at: string;
  updated_at: string;
  attachments: Attachment[];
  activity: ActivityEntry[];
}

export interface DashboardSummary {
  open: number;
  scheduled: number;
  in_progress: number;
  completed: number;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface WorkOrderInput {
  title: string;
  description: string;
  priority: WorkOrderPriority;
  status: WorkOrderStatus;
  assigned_technician: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  site_name: string;
}
