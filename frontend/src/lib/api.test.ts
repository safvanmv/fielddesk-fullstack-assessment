import { describe, expect, it } from "vitest";

import { getErrorMessage } from "./api";

function envelope(details: unknown, message = "Request failed.") {
  return { error: { code: "x", message, details, request_id: "req-1" } };
}

describe("getErrorMessage", () => {
  it("uses the detail string inside the error envelope", () => {
    expect(
      getErrorMessage(envelope({ detail: "Technician already has a work order in this time window." }), 409),
    ).toBe("Technician already has a work order in this time window.");
  });

  it("lists per-field validation errors and drops the non_field_errors key", () => {
    expect(
      getErrorMessage(envelope({ password: ["This password is entirely numeric."] }), 400),
    ).toBe("password: This password is entirely numeric.");
    expect(
      getErrorMessage(envelope({ non_field_errors: ["You cannot change your own role or active state."] }), 400),
    ).toBe("You cannot change your own role or active state.");
  });

  it("never shows the envelope object itself when details are empty", () => {
    expect(getErrorMessage(envelope(null), 403)).toBe("Request failed (403).");
    expect(
      getErrorMessage(envelope(null, "The request could not be completed."), 500),
    ).toBe("The request could not be completed.");
  });
});
