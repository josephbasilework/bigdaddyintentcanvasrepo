import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MCPInstallPanel } from "../MCPInstallPanel";

const catalogEntry = {
  catalog_id: "google-calendar",
  server_id: "google-calendar",
  name: "Google Calendar",
  description: "Google Calendar integration",
  credential_fields: [
    {
      key: "google_calendar_credentials",
      label: "Google Calendar OAuth Credentials",
      type: "json",
      description: "Paste OAuth JSON",
      env_key: "GOOGLE_CALENDAR_CREDENTIALS",
      required: true,
    },
  ],
  oauth: {
    provider: "google",
    scopes: ["scope-one"],
  },
};

const previewPayload = {
  server_id: "google-calendar",
  name: "Google Calendar",
  description: "Google Calendar integration",
  transport_type: "stdio",
  transport_config: {},
  tools: [
    {
      name: "calendar_list",
      description: "List events",
      security_level: "allowed",
    },
  ],
  security_rules: {
    calendar_list: "allowed",
  },
  credential_fields: catalogEntry.credential_fields,
  missing_credentials: [],
  sandbox_issues: [],
  blocked_tools: [],
};

describe("MCPInstallPanel", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders catalog and credential fields", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/mcp/catalog")) {
        return {
          ok: true,
          json: async () => ({ entries: [catalogEntry] }),
        } as Response;
      }
      if (url.includes("/api/mcp/servers")) {
        return {
          ok: true,
          json: async () => ({ servers: [] }),
        } as Response;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(<MCPInstallPanel />);

    expect(await screen.findByText("Available MCPs")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Google Calendar" })).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Google Calendar OAuth Credentials/i)
    ).toBeInTheDocument();
  });

  it("previews and confirms install", async () => {
    const fetchMock = vi.mocked(fetch);
    let installCallCount = 0;
    fetchMock.mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/mcp/catalog")) {
        return {
          ok: true,
          json: async () => ({ entries: [catalogEntry] }),
        } as Response;
      }
      if (url.includes("/api/mcp/servers")) {
        return {
          ok: true,
          json: async () => ({ servers: [] }),
        } as Response;
      }
      if (url.includes("/api/mcp/install")) {
        installCallCount += 1;
        if (installCallCount === 1) {
          return {
            ok: true,
            json: async () => ({
              requires_confirmation: true,
              preview: previewPayload,
            }),
          } as Response;
        }
        return {
          ok: true,
          json: async () => ({ success: true, review_required: false }),
        } as Response;
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(<MCPInstallPanel />);

    const reviewButton = await screen.findByRole("button", { name: /review install/i });
    fireEvent.click(reviewButton);

    expect(await screen.findByText("Capability review")).toBeInTheDocument();
    expect(screen.getByText("calendar_list")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /confirm install/i }));

    await waitFor(() =>
      expect(screen.getByText(/installed and enabled/i)).toBeInTheDocument()
    );
  });
});
