import { afterEach, describe, expect, it } from "vitest";
import {
  buildNodeContextFromNode,
  getNodeTypeDefinition,
  hasNodeType,
  registerNodeType,
  registerNodeTypeExtension,
  serializeCanvasNode,
  unregisterNodeType,
  unregisterNodeTypeExtension,
} from "../index";

const CUSTOM_TYPE = "custom-experiment";
const EXTENSION_ID = "custom-extension";
const EXTENSION_TYPE = "custom-extension-type";

describe("node type registry", () => {
  afterEach(() => {
    unregisterNodeType(CUSTOM_TYPE);
    unregisterNodeTypeExtension(EXTENSION_ID);
  });

  it("exposes built-in node types", () => {
    expect(hasNodeType("text")).toBe(true);
    expect(hasNodeType("document")).toBe(true);
    expect(getNodeTypeDefinition("text").icon).toBe("📝");
  });

  it("allows registering custom node types with context and serialization", () => {
    registerNodeType({
      type: CUSTOM_TYPE,
      label: "Custom",
      icon: "🧪",
      schema: { fields: [] },
      buildContext: (node) => ({
        id: node.id,
        title: node.title,
        node_type: node.type,
        content: "custom context",
      }),
      serialize: (_node, base) => ({
        ...base,
        metadata: { ...(base.metadata as Record<string, unknown> | undefined), custom: true },
      }),
    });

    const node = {
      id: "node-1",
      type: CUSTOM_TYPE,
      title: "Custom node",
      content: "Hello",
      x: 10,
      y: 20,
      z: 0,
    };

    const context = buildNodeContextFromNode(node);
    expect(context.content).toBe("custom context");

    const payload = serializeCanvasNode(node);
    expect(payload.type).toBe(CUSTOM_TYPE);
    expect(payload.metadata).toMatchObject({ custom: true });
  });

  it("registers node type extensions", () => {
    registerNodeTypeExtension({
      id: EXTENSION_ID,
      definitions: [
        {
          type: EXTENSION_TYPE,
          label: "Extension Node",
          icon: "🧩",
          schema: { fields: [] },
        },
      ],
    });

    expect(hasNodeType(EXTENSION_TYPE)).toBe(true);
  });
});
