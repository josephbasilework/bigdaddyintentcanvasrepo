import { describe, it, expect } from "vitest";
import { toMarkers } from "../AudioBlockNode";

describe("toMarkers", () => {
  it("returns empty array for non-array input", () => {
    expect(toMarkers(undefined)).toEqual([]);
    expect(toMarkers({})).toEqual([]);
  });

  it("filters invalid marker entries and normalizes values", () => {
    const result = toMarkers([
      { id: "a", time: 1, label: "Intro" },
      { id: "", time: 2 },
      { id: "b", time: "3.5" },
      { id: "z", time: 0 },
      { id: "c" },
      { time: 4 },
      "bad",
      null,
    ]);

    expect(result).toHaveLength(3);
    expect(result[0]).toEqual({ id: "a", time: 1, label: "Intro" });
    expect(result[1]).toEqual({ id: "b", time: 3.5, label: undefined });
    expect(result[2]).toEqual({ id: "z", time: 0, label: undefined });
  });
});
