/**
 * Tests for CopilotKit runtime API route.
 */
import { describe, it, expect } from "vitest";

describe("CopilotKit Runtime API Route", () => {
  it("exports POST handler", async () => {
    const routeModule = await import("./route");
    expect(routeModule.POST).toBeDefined();
    expect(typeof routeModule.POST).toBe("function");
  });
});
