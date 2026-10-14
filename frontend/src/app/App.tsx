import { useEffect, useState } from "react";

import { LoginScreen } from "../features/auth/LoginScreen";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { WorkOrderDetails } from "../features/work-orders/WorkOrderDetails";
import { WorkOrderForm } from "../features/work-orders/WorkOrderForm";
import { SettingsPage } from "../features/settings/SettingsPage";
import {
  ApiError,
  getCurrentUser,
  getTechnicians,
  getWorkOrder,
  login,
  logout,
  saveWorkOrder,
  submitProgress,
  uploadAttachment,
} from "../lib/api";
import type {
  CurrentUser,
  Technician,
  WorkOrder,
  WorkOrderInput,
  WorkOrderStatus,
} from "../lib/types";

type PageState =
  | { kind: "dashboard" }
  | { kind: "settings" }
  | { kind: "create" }
  | { kind: "edit"; id: string }
  | { kind: "details"; id: string };

function displayName(user: CurrentUser): string {
  const name = `${user.first_name} ${user.last_name}`.trim();
  return name || user.username;
}

export function App() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [page, setPage] = useState<PageState>({ kind: "dashboard" });
  const [activeOrder, setActiveOrder] = useState<WorkOrder | null>(null);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          setUser(null);
        } else {
          setAuthError(
            error instanceof Error
              ? error.message
              : "Could not connect to the FieldDesk API.",
          );
        }
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (page.kind !== "create" && page.kind !== "edit") return;
    if (user?.role !== "owner" && user?.role !== "dispatcher") return;
    let active = true;
    getTechnicians()
      .then((results) => {
        if (active) setTechnicians(results);
      })
      .catch((error: unknown) => {
        if (active) {
          setPageError(
            error instanceof Error ? error.message : "Could not load technicians.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [page, user]);

  async function handleLogin(username: string, password: string) {
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      const signedInUser = await login(username, password);
      setUser(signedInUser);
    } catch (error) {
      setLoginError(
        error instanceof Error
          ? error.message
          : "Sign-in failed. Check your credentials and try again.",
      );
    } finally {
      setIsLoggingIn(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
      setUser(null);
      setPage({ kind: "dashboard" });
      setActiveOrder(null);
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Could not sign out.",
      );
    }
  }

  async function selectOrder(order: WorkOrder) {
    setPageError(null);
    setActiveOrder(order);
    setPage({ kind: "details", id: order.id });
    try {
      const detail = await getWorkOrder(order.id);
      setActiveOrder(detail);
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Could not load work order.",
      );
    }
  }

  async function handleSave(input: WorkOrderInput) {
    if (page.kind !== "create" && page.kind !== "edit") return;
    setIsWorking(true);
    setPageError(null);
    try {
      const saved = await saveWorkOrder(
        input,
        page.kind === "edit" ? page.id : undefined,
      );
      // The save response has no activity history; reload the full order so the
      // details page shows the audit entry this save just created.
      setActiveOrder(await getWorkOrder(saved.id));
      setPage({ kind: "details", id: saved.id });
    } catch (error) {
      setPageError(
        error instanceof Error
          ? error.message
          : "Could not save this work order.",
      );
    } finally {
      setIsWorking(false);
    }
  }

  async function handleUpload(file: File) {
    if (!activeOrder) return;
    setIsWorking(true);
    setPageError(null);
    try {
      await uploadAttachment(activeOrder.id, file);
      setActiveOrder(await getWorkOrder(activeOrder.id));
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "Could not upload attachment.",
      );
    } finally {
      setIsWorking(false);
    }
  }

  async function handleProgress(status: WorkOrderStatus, note: string) {
    if (!activeOrder) return;
    setIsWorking(true);
    setPageError(null);
    try {
      await submitProgress(activeOrder.id, status, note);
      setActiveOrder(await getWorkOrder(activeOrder.id));
    } catch (error) {
      setPageError(
        error instanceof Error
          ? error.message
          : "Could not submit the progress update.",
      );
    } finally {
      setIsWorking(false);
    }
  }

  if (authLoading) {
    return <p className="loading-state">Connecting to FieldDesk…</p>;
  }

  if (authError) {
    return (
      <main className="auth-layout auth-layout--error">
        <section className="auth-panel">
          <p className="eyebrow">Connection problem</p>
          <h1>Could not reach the API</h1>
          <p className="muted-copy">{authError}</p>
          <button className="button button-primary" onClick={() => location.reload()}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (!user) {
    return (
      <LoginScreen
        error={loginError}
        isSubmitting={isLoggingIn}
        onSubmit={handleLogin}
      />
    );
  }

  const canManage = user.role === "owner" || user.role === "dispatcher";

  return (
    <div className="app-shell">
      <header className="app-header">
        <a
          aria-label="FieldDesk home"
          className="app-brand"
          href="#dashboard"
          onClick={(event) => {
            event.preventDefault();
            setPage({ kind: "dashboard" });
            setPageError(null);
          }}
        >
          <span className="brand-mark" aria-hidden="true">
            FD
          </span>
          FieldDesk
        </a>
        <div className="header-actions">
          {user.role === "owner" && (
            <button
              className="button button-secondary"
              onClick={() => {
                setPageError(null);
                setPage({ kind: "settings" });
              }}
            >
              Settings
            </button>
          )}
          <span className="user-chip">
            {displayName(user)} · {user.organization_name} · {user.role}
          </span>
          <button className="button button-secondary" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      {pageError && page.kind !== "details" && (
        <div className="content-shell">
          <div className="error-banner" role="alert">
            {pageError}
          </div>
        </div>
      )}

      {page.kind === "dashboard" && (
        <DashboardPage
          onCreate={() => {
            setPageError(null);
            setPage({ kind: "create" });
          }}
          onExport={() => {
            window.location.assign("/api/reports/work-orders.csv");
          }}
          onSelect={(order) => void selectOrder(order)}
          role={user.role}
        />
      )}

      {page.kind === "settings" && user.role === "owner" && <SettingsPage />}

      {(page.kind === "create" || page.kind === "edit") && canManage && (
        <WorkOrderForm
          key={page.kind === "edit" ? page.id : "new"}
          initialOrder={
            page.kind === "edit" && activeOrder?.id === page.id
              ? activeOrder
              : undefined
          }
          isSaving={isWorking}
          onCancel={() => setPage({ kind: "dashboard" })}
          onSave={handleSave}
          technicians={technicians}
        />
      )}

      {page.kind === "details" && activeOrder && (
        <WorkOrderDetails
          error={pageError}
          isWorking={isWorking}
          onBack={() => {
            setPage({ kind: "dashboard" });
            setPageError(null);
          }}
          onEdit={() => {
            setPageError(null);
            setPage({ kind: "edit", id: activeOrder.id });
          }}
          onProgress={handleProgress}
          onUpload={handleUpload}
          order={activeOrder}
          role={user.role}
        />
      )}
    </div>
  );
}
