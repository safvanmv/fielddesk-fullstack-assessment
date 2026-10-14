import { useState } from "react";
import type { FormEvent } from "react";

interface LoginScreenProps {
  error: string | null;
  isSubmitting: boolean;
  onSubmit: (username: string, password: string) => Promise<void>;
}

export function LoginScreen({
  error,
  isSubmitting,
  onSubmit,
}: LoginScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(username.trim(), password);
  }

  return (
    <main className="auth-layout">
      <section className="auth-panel">
        <div className="brand-mark" aria-hidden="true">
          FD
        </div>
        <p className="eyebrow">Field service operations</p>
        <h1>Welcome back</h1>
        <p className="muted-copy">
          Sign in to view and coordinate your organisation&apos;s service work.
        </p>
        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Email or username</span>
            <input
              autoComplete="username"
              name="username"
              onChange={(event) => setUsername(event.target.value)}
              required
              value={username}
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              autoComplete="current-password"
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button button-primary button-block" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="auth-footnote">
          Use an assessment sample account supplied in the project documentation.
        </p>
      </section>
      <aside className="auth-aside">
        <div>
          <p className="eyebrow eyebrow-light">One clear view</p>
          <h2>Keep every field team moving.</h2>
          <p>
            Plan work, coordinate technicians, and follow progress from one
            organisation-scoped workspace.
          </p>
        </div>
        <div className="aside-decoration" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </aside>
    </main>
  );
}
