import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LoginScreen } from "./LoginScreen";

describe("LoginScreen", () => {
  it("submits trimmed username and password", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <LoginScreen error={null} isSubmitting={false} onSubmit={onSubmit} />,
    );

    fireEvent.change(screen.getByLabelText("Email or username"), {
      target: { value: " dispatcher@example.test " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "assessment-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        "dispatcher@example.test",
        "assessment-password",
      ),
    );
  });

  it("displays login errors to assistive technology", () => {
    render(
      <LoginScreen
        error="The username or password is incorrect."
        isSubmitting={false}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "The username or password is incorrect.",
    );
  });
});
