import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { App, Status } from "./main";
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
test("status uses readable accessible text", () => {
  render(<Status value="awaiting_approval" />);
  expect(screen.getByText("awaiting approval")).toBeInTheDocument();
});
test("credentials are required before workspace access", () => {
  render(<App />);
  expect(
    screen.getByLabelText("Development bearer credential"),
  ).toHaveAttribute("type", "password");
  expect(screen.queryByText("New request")).not.toBeInTheDocument();
});
test("dashboard renders persisted requests and filters search", async () => {
  sessionStorage.setItem("casepilot-token", "test");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/me")
          ? { user: "demo.requester", role: "requester" }
          : [
              {
                id: "abc",
                text: "Repair laptop",
                owner: "demo.requester",
                status: "completed",
                created_at: "2026-11-19T12:00:00Z",
                state: {},
              },
            ],
    })),
  );
  render(<App />);
  await screen.findByText("Repair laptop");
  fireEvent.change(screen.getByLabelText("Search requests"), {
    target: { value: "not present" },
  });
  await waitFor(() =>
    expect(screen.queryByText("Repair laptop")).not.toBeInTheDocument(),
  );
  expect(screen.getByText("No requests here yet")).toBeInTheDocument();
});
