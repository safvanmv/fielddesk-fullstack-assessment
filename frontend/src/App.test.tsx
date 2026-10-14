import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { App } from "./app/App";

const authenticatedUser = {
  id: "user-1",
  username: "dispatcher",
  email: "dispatcher@example.test",
  first_name: "Sam",
  last_name: "Dispatcher",
  role: "dispatcher",
  organization_name: "Northwind Maintenance",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("signs in and opens the organisation dashboard", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/auth/me/")) {
        return new Response(
          JSON.stringify({
            error: {
              code: "not_authenticated",
              message: "Request failed.",
              details: { detail: "Authentication credentials were not provided." },
              request_id: "test-request",
            },
          }),
          {
          status: 403,
          headers: { "Content-Type": "application/json" },
          },
        );
      }
      if (url.endsWith("/api/auth/csrf/")) {
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/api/auth/login/")) {
        return new Response(JSON.stringify({ user: authenticatedUser }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/dashboard/")) {
        return new Response(
          JSON.stringify({
            total: 1,
            by_status: { open: 1 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/technicians/")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/api/work-orders/")) {
        return new Response(
          JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    class MockEventSource {
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      addEventListener() {}
      removeEventListener() {}
      close() {}
    }
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", MockEventSource);

    render(<App />);
    await screen.findByRole("heading", { name: "Welcome back" });

    fireEvent.change(screen.getByLabelText("Email or username"), {
      target: { value: "dispatcher" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "assessment-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Work orders" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Northwind Maintenance/)).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/login/",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});
