import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  createOrganizationMember,
  getOrganizationMembers,
  getOrganizationSettings,
  updateOrganizationMember,
  updateOrganizationSettings,
} from "../../lib/api";
import type {
  OrganizationMember,
  OrganizationSettings,
  UserRole,
} from "../../lib/types";

const bytesPerGiB = 1024 ** 3;

function formatBytes(bytes: number): string {
  if (bytes >= bytesPerGiB) return `${(bytes / bytesPerGiB).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

function isRole(value: string): value is UserRole {
  return value === "owner" || value === "dispatcher" || value === "technician";
}

export function SettingsPage() {
  const [organization, setOrganization] =
    useState<OrganizationSettings | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [name, setName] = useState("");
  const [limitGiB, setLimitGiB] = useState("1");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("dispatcher");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([getOrganizationSettings(), getOrganizationMembers()])
      .then(([settings, currentMembers]) => {
        if (!active) return;
        setOrganization(settings);
        setName(settings.name);
        setLimitGiB(String(settings.storage_limit_bytes / bytesPerGiB));
        setMembers(currentMembers);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : "Could not load settings.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      const updated = await updateOrganizationSettings({
        name: name.trim(),
        storage_limit_bytes: Math.round(Number(limitGiB) * bytesPerGiB),
      });
      setOrganization(updated);
      setName(updated.name);
      setNotice("Organization settings saved.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not save organization settings.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function inviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setIsSaving(true);
    try {
      const created = await createOrganizationMember({
        username: username.trim(),
        email: email.trim(),
        password,
        role,
      });
      setMembers((current) => [...current, created]);
      setUsername("");
      setEmail("");
      setPassword("");
      setNotice("User created.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not create user.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function changeMember(
    member: OrganizationMember,
    changes: Partial<Pick<OrganizationMember, "role" | "active">>,
  ) {
    setError(null);
    setNotice(null);
    try {
      const updated = await updateOrganizationMember(member.id, changes);
      setMembers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(`Updated ${updated.username}.`);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not update this user.",
      );
    }
  }

  return (
    <main className="content-shell">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Owner controls</p>
          <h1>Organization settings</h1>
          <p>Manage team access and organization storage limits.</p>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="success-banner" role="status">
          {notice}
        </p>
      )}
      {isLoading ? (
        <p className="loading-state" role="status">
          Loading organization settings…
        </p>
      ) : (
        <div className="settings-grid">
          <section className="panel" aria-labelledby="org-settings-heading">
            <div className="panel-heading">
              <h2 id="org-settings-heading">Organization</h2>
            </div>
            <form className="form-stack" onSubmit={saveSettings}>
              <label className="field">
                <span>Organization name</span>
                <input
                  maxLength={120}
                  onChange={(event) => setName(event.target.value)}
                  required
                  value={name}
                />
              </label>
              <label className="field">
                <span>Storage limit (GB)</span>
                <input
                  min={0}
                  onChange={(event) => setLimitGiB(event.target.value)}
                  required
                  step="0.01"
                  type="number"
                  value={limitGiB}
                />
              </label>
              <p className="storage-copy">
                Used {formatBytes(organization?.storage_used_bytes ?? 0)} of{" "}
                {formatBytes(organization?.storage_limit_bytes ?? 0)}.
              </p>
              <button className="button button-primary" disabled={isSaving}>
                {isSaving ? "Saving…" : "Save settings"}
              </button>
            </form>
          </section>

          <section className="panel" aria-labelledby="invite-member-heading">
            <div className="panel-heading">
              <h2 id="invite-member-heading">Add a team member</h2>
            </div>
            <form className="form-stack" onSubmit={inviteMember}>
              <label className="field">
                <span>Username</span>
                <input
                  autoComplete="off"
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  value={username}
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  autoComplete="email"
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </label>
              <label className="field">
                <span>Password (at least 12 characters)</span>
                <input
                  autoComplete="new-password"
                  minLength={12}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </label>
              <label className="field">
                <span>Role</span>
                <select
                  onChange={(event) =>
                    isRole(event.target.value) && setRole(event.target.value)
                  }
                  value={role}
                >
                  <option value="dispatcher">Dispatcher</option>
                  <option value="technician">Technician</option>
                  <option value="owner">Owner</option>
                </select>
              </label>
              <button className="button button-primary" disabled={isSaving}>
                {isSaving ? "Creating…" : "Create user"}
              </button>
            </form>
          </section>

          <section className="panel panel-wide" aria-labelledby="members-heading">
            <div className="panel-heading">
              <h2 id="members-heading">Team members</h2>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Access</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member) => (
                    <tr key={member.id}>
                      <td>{member.username}</td>
                      <td>{member.email}</td>
                      <td>
                        <label>
                          <span className="sr-only">
                            Role for {member.username}
                          </span>
                          <select
                            disabled={isSaving}
                            onChange={(event) =>
                              isRole(event.target.value) &&
                              void changeMember(member, {
                                role: event.target.value,
                              })
                            }
                            value={member.role}
                          >
                            <option value="owner">Owner</option>
                            <option value="dispatcher">Dispatcher</option>
                            <option value="technician">Technician</option>
                          </select>
                        </label>
                      </td>
                      <td>
                        <button
                          className="button button-secondary"
                          disabled={isSaving}
                          onClick={() =>
                            void changeMember(member, {
                              active: !member.active,
                            })
                          }
                        >
                          {member.active ? "Deactivate" : "Reactivate"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
