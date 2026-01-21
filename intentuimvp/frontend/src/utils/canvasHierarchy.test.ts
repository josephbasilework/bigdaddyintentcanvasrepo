import { describe, it, expect } from "vitest";
import { findContainerParentId } from "./canvasHierarchy";

describe("findContainerParentId", () => {
  it("prefers the deepest container that contains the node center", () => {
    const nodes = [
      {
        id: "container-a",
        type: "container",
        x: 0,
        y: 0,
        metadata: {
          container: { size: { width: 500, height: 400 } },
        },
      },
      {
        id: "container-b",
        type: "container",
        x: 50,
        y: 50,
        metadata: {
          container: {
            parentId: "container-a",
            size: { width: 300, height: 200 },
          },
        },
      },
      {
        id: "node-1",
        type: "text",
        x: 100,
        y: 80,
      },
    ];

    const target = nodes[2];

    expect(findContainerParentId(target, nodes)).toBe("container-b");
  });

  it("breaks ties by choosing the smallest area", () => {
    const nodes = [
      {
        id: "container-big",
        type: "container",
        x: 0,
        y: 0,
        metadata: {
          container: { size: { width: 400, height: 300 } },
        },
      },
      {
        id: "container-small",
        type: "container",
        x: 0,
        y: 0,
        metadata: {
          container: { size: { width: 200, height: 200 } },
        },
      },
      {
        id: "node-2",
        type: "text",
        x: 40,
        y: 40,
      },
    ];

    const target = nodes[2];

    expect(findContainerParentId(target, nodes)).toBe("container-small");
  });

  it("returns null when no container contains the node", () => {
    const nodes = [
      {
        id: "container-far",
        type: "container",
        x: 400,
        y: 400,
        metadata: {
          container: { size: { width: 100, height: 100 } },
        },
      },
      {
        id: "node-3",
        type: "text",
        x: 0,
        y: 0,
      },
    ];

    const target = nodes[1];

    expect(findContainerParentId(target, nodes)).toBeNull();
  });
});
