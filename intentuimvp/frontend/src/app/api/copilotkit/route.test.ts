/**
 * Tests for CopilotKit runtime API route.
 */
import { describe, it, expect, vi } from "vitest";

vi.mock("@copilotkit/runtime", () => ({
  CopilotRuntime: class {},
  copilotRuntimeNextJSAppRouterEndpoint: () => ({
    handleRequest: vi.fn(),
  }),
  OpenAIAdapter: class {},
}));

describe("CopilotKit Runtime API Route", () => {
  it("exports POST handler", async () => {
    const routeModule = await import("./route");
    expect(routeModule.POST).toBeDefined();
    expect(typeof routeModule.POST).toBe("function");
  });
});
