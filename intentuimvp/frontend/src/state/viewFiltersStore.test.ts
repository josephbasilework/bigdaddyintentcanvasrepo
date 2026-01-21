// @vitest-environment node
import { describe, expect, it } from "vitest";

import { getSessionStorage } from "./viewFiltersStore";

describe("getSessionStorage", () => {
  it("returns a memory-backed storage in node", () => {
    const storage = getSessionStorage();

    storage.clear();
    expect(storage.length).toBe(0);

    storage.setItem("alpha", "1");
    storage.setItem("beta", "2");

    expect(storage.length).toBe(2);
    expect(storage.getItem("alpha")).toBe("1");
    expect(storage.getItem("missing")).toBeNull();
    expect(storage.key(0)).toBe("alpha");

    storage.removeItem("alpha");
    expect(storage.length).toBe(1);

    storage.clear();
    expect(storage.length).toBe(0);
  });
});
