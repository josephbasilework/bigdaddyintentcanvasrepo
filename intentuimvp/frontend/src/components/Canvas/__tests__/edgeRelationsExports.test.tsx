import { describe, expect, it } from "vitest";

import {
  CUSTOM_EDGE_RELATION_VALUE,
  EDGE_RELATION_OPTIONS,
  buildEdgeRelationOptions,
  getEdgeRelationLabel,
  normalizeEdgeRelationType,
} from "../index";

describe("edge relation exports", () => {
  it("exposes relation helpers and defaults", () => {
    expect(CUSTOM_EDGE_RELATION_VALUE).toBe("__custom__");
    expect(EDGE_RELATION_OPTIONS.length).toBeGreaterThan(0);
    expect(normalizeEdgeRelationType("Depends On")).toBe("depends_on");
    expect(getEdgeRelationLabel("depends_on")).toBe("Depends on");

    const options = buildEdgeRelationOptions(["depends_on", "custom_link"]);
    expect(options.some((option) => option.value === "custom_link")).toBe(true);
  });
});
