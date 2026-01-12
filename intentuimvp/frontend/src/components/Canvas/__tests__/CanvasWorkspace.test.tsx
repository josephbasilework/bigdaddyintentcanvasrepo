/**
 * Tests for workspace normalization functions.
 *
 * These tests ensure that workspace state is correctly restored on session load,
 * including handling of various input formats, corruption recovery, and edge cases.
 *
 * Acceptance Criteria:
 * - Given valid workspace data, when normalized, then nodes and edges are correctly parsed
 * - Given invalid/corrupted data, when normalized, then valid data is recovered and corruption is flagged
 * - Given various legacy field names, when normalized, then data is correctly mapped
 */

import { describe, it, expect } from "vitest";
import { normalizeNode, normalizeEdge, normalizeWorkspaceState } from "../CanvasWorkspace";

describe("normalizeNode", () => {
  it("should return null for non-object values", () => {
    expect(normalizeNode(null)).toBe(null);
    expect(normalizeNode(undefined)).toBe(null);
    expect(normalizeNode("string")).toBe(null);
    expect(normalizeNode(123)).toBe(null);
    expect(normalizeNode([])).toBe(null);
  });

  it("should return null for objects without id", () => {
    expect(normalizeNode({})).toBe(null);
    expect(normalizeNode({ x: 100, y: 200 })).toBe(null);
  });

  it("should normalize valid node with minimal fields", () => {
    const result = normalizeNode({ id: "test-id" });
    expect(result).toEqual({
      id: "test-id",
      type: "text",
      x: 0,
      y: 0,
      z: 0,
      title: "Untitled",
    });
  });

  it("should normalize node with all fields", () => {
    const result = normalizeNode({
      id: "full-node",
      type: "document",
      x: 100,
      y: 200,
      z: 5,
      title: "Test Document",
      content: "Document content here",
      metadata: { author: "test", tags: ["important"] },
    });
    expect(result).toEqual({
      id: "full-node",
      type: "document",
      x: 100,
      y: 200,
      z: 5,
      title: "Test Document",
      content: "Document content here",
      metadata: { author: "test", tags: ["important"] },
    });
  });

  it("should handle legacy nodeId field", () => {
    const result = normalizeNode({
      nodeId: "legacy-id",
      x: 50,
      y: 50,
    });
    expect(result?.id).toBe("legacy-id");
  });

  it("should convert numeric id to string", () => {
    const result = normalizeNode({
      id: 12345,
      x: 0,
      y: 0,
    });
    expect(result?.id).toBe("12345");
  });

  it("should default to text type for unknown types", () => {
    const result = normalizeNode({
      id: "unknown-type",
      type: "invalid_type",
    });
    expect(result?.type).toBe("text");
  });

  it("should handle position object", () => {
    const result = normalizeNode({
      id: "pos-object",
      position: { x: 10, y: 20, z: 30 },
    });
    expect(result).toEqual({
      id: "pos-object",
      type: "text",
      x: 10,
      y: 20,
      z: 30,
      title: "Untitled",
    });
  });

  it("should prefer position.x over direct x", () => {
    const result = normalizeNode({
      id: "pos-priority",
      position: { x: 100, y: 200 },
      x: 999,
      y: 888,
    });
    expect(result?.x).toBe(100);
    expect(result?.y).toBe(200);
  });

  it("should use label as fallback for title", () => {
    const result = normalizeNode({
      id: "label-fallback",
      label: "From Label",
    });
    expect(result?.title).toBe("From Label");
  });

  it("should trim title whitespace", () => {
    const result = normalizeNode({
      id: "trim-test",
      title: "  Whitespace Title  ",
    });
    expect(result?.title).toBe("Whitespace Title");
  });

  it("should default to Untitled for empty title", () => {
    expect(normalizeNode({ id: "empty1", title: "" })?.title).toBe("Untitled");
    expect(normalizeNode({ id: "empty2", title: "   " })?.title).toBe("Untitled");
  });

  it("should handle legacy node_metadata field", () => {
    const result = normalizeNode({
      id: "legacy-meta",
      node_metadata: { version: 1 },
    });
    expect(result?.metadata).toEqual({ version: 1 });
  });

  it("should handle camelCase nodeMetadata field", () => {
    const result = normalizeNode({
      id: "camel-meta",
      nodeMetadata: { source: "api" },
    });
    expect(result?.metadata).toEqual({ source: "api" });
  });

  it("should ignore non-record metadata", () => {
    const result = normalizeNode({
      id: "bad-meta",
      metadata: "string metadata",
    });
    expect(result?.metadata).toBeUndefined();
  });

  it("should handle negative coordinates", () => {
    const result = normalizeNode({
      id: "negative",
      x: -100,
      y: -200,
      z: -50,
    });
    expect(result).toEqual({
      id: "negative",
      type: "text",
      x: -100,
      y: -200,
      z: -50,
      title: "Untitled",
    });
  });

  it("should handle NaN and Infinity coordinates", () => {
    const result = normalizeNode({
      id: "nan-coord",
      x: NaN,
      y: Infinity,
      z: -Infinity,
    });
    expect(result).toEqual({
      id: "nan-coord",
      type: "text",
      x: 0,
      y: 0,
      z: 0,
      title: "Untitled",
    });
  });
});

describe("normalizeEdge", () => {
  it("should return null for non-object values", () => {
    expect(normalizeEdge(null, 0)).toBe(null);
    expect(normalizeEdge(undefined, 0)).toBe(null);
    expect(normalizeEdge("string", 0)).toBe(null);
  });

  it("should return null for edges without source or target", () => {
    expect(normalizeEdge({}, 0)).toBe(null);
    expect(normalizeEdge({ sourceNodeId: "a" }, 0)).toBe(null);
    expect(normalizeEdge({ targetNodeId: "b" }, 0)).toBe(null);
  });

  it("should normalize valid edge with minimal fields", () => {
    const result = normalizeEdge(
      { sourceNodeId: "node-a", targetNodeId: "node-b" },
      0
    );
    expect(result).toEqual({
      id: "node-a-node-b-0",
      sourceNodeId: "node-a",
      targetNodeId: "node-b",
    });
  });

  it("should normalize edge with all fields", () => {
    const result = normalizeEdge(
      {
        id: "edge-1",
        sourceNodeId: "node-a",
        targetNodeId: "node-b",
        label: "Related to",
        type: "dashed",
        relationType: "depends_on",
      },
      0
    );
    expect(result).toEqual({
      id: "edge-1",
      sourceNodeId: "node-a",
      targetNodeId: "node-b",
      label: "Related to",
      type: "dashed",
      relationType: "depends_on",
    });
  });

  it("should handle legacy fromNodeId and toNodeId fields", () => {
    const result = normalizeEdge(
      { fromNodeId: "from-node", toNodeId: "to-node" },
      1
    );
    expect(result?.sourceNodeId).toBe("from-node");
    expect(result?.targetNodeId).toBe("to-node");
  });

  it("should handle snake_case from_node_id and to_node_id fields", () => {
    const result = normalizeEdge(
      { from_node_id: "snake-from", to_node_id: "snake-to" },
      2
    );
    expect(result?.sourceNodeId).toBe("snake-from");
    expect(result?.targetNodeId).toBe("snake-to");
  });

  it("should prioritize sourceNodeId over fromNodeId", () => {
    const result = normalizeEdge(
      { sourceNodeId: "priority", fromNodeId: "ignored", targetNodeId: "target" },
      0
    );
    expect(result?.sourceNodeId).toBe("priority");
  });

  it("should generate id from source-target-index if not provided", () => {
    const result = normalizeEdge(
      { sourceNodeId: "a", targetNodeId: "b" },
      5
    );
    expect(result?.id).toBe("a-b-5");
  });

  it("should handle invalid edge type values", () => {
    const result = normalizeEdge(
      {
        sourceNodeId: "a",
        targetNodeId: "b",
        type: "invalid_type",
      },
      0
    );
    expect(result?.type).toBeUndefined();
  });

  it("should use type as fallback for relationType if valid", () => {
    const result = normalizeEdge(
      {
        sourceNodeId: "a",
        targetNodeId: "b",
        type: "depends_on",
      },
      0
    );
    expect(result?.relationType).toBe("depends_on");
  });

  it("should handle snake_case relation_type field", () => {
    const result = normalizeEdge(
      {
        sourceNodeId: "a",
        targetNodeId: "b",
        relation_type: "supports",
      },
      0
    );
    expect(result?.relationType).toBe("supports");
  });

  it("should not include optional fields if not provided", () => {
    const result = normalizeEdge({ sourceNodeId: "a", targetNodeId: "b" }, 0);
    expect(Object.keys(result ?? {})).toEqual(["id", "sourceNodeId", "targetNodeId"]);
  });
});

describe("normalizeWorkspaceState", () => {
  it("should return empty state with corruption flag for non-record values", () => {
    const result = normalizeWorkspaceState(null);
    expect(result).toEqual({
      nodes: [],
      edges: [],
      hadCorruption: true,
    });
  });

  it("should return empty state with corruption flag when nodes is not an array", () => {
    const result = normalizeWorkspaceState({ nodes: "not-an-array" });
    expect(result).toEqual({
      nodes: [],
      edges: [],
      hadCorruption: true,
    });
  });

  it("should normalize valid workspace with nodes and edges", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        { id: "node-1", type: "text", x: 10, y: 20, title: "Node 1" },
        { id: "node-2", type: "document", x: 30, y: 40, title: "Node 2" },
      ],
      edges: [
        { sourceNodeId: "node-1", targetNodeId: "node-2", label: "connects" },
      ],
    });
    expect(result.hadCorruption).toBe(false);
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
    expect(result.nodes[0].id).toBe("node-1");
    expect(result.edges[0].label).toBe("connects");
  });

  it("should handle workspace with empty nodes array", () => {
    const result = normalizeWorkspaceState({
      nodes: [],
    });
    expect(result).toEqual({
      nodes: [],
      edges: [],
      hadCorruption: false,
    });
  });

  it("should handle workspace without edges field", () => {
    const result = normalizeWorkspaceState({
      nodes: [{ id: "node-1", x: 0, y: 0 }],
    });
    expect(result.edges).toEqual([]);
    expect(result.hadCorruption).toBe(false);
  });

  it("should flag corruption when edges is not an array but is defined", () => {
    const result = normalizeWorkspaceState({
      nodes: [{ id: "node-1", x: 0, y: 0 }],
      edges: "invalid",
    });
    expect(result.hadCorruption).toBe(true);
    expect(result.edges).toEqual([]);
  });

  it("should flag corruption when some nodes are invalid", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        { id: "valid-node", x: 0, y: 0 },
        { x: 100, y: 200 }, // Missing id
        { id: "another-valid", x: 50, y: 50 },
      ],
    });
    expect(result.hadCorruption).toBe(true);
    expect(result.nodes).toHaveLength(2);
  });

  it("should flag corruption when some edges are invalid", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        { id: "node-1", x: 0, y: 0 },
        { id: "node-2", x: 100, y: 100 },
      ],
      edges: [
        { sourceNodeId: "node-1", targetNodeId: "node-2" },
        { invalid: "edge" }, // Missing source/target
      ],
    });
    expect(result.hadCorruption).toBe(true);
    expect(result.edges).toHaveLength(1);
  });

  it("should return empty arrays when all nodes are invalid", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        { x: 0, y: 0 },
        { label: "no id" },
        null,
      ],
    });
    expect(result).toEqual({
      nodes: [],
      edges: [],
      hadCorruption: true,
    });
  });

  it("should handle missing extra fields gracefully", () => {
    const result = normalizeWorkspaceState({
      nodes: [{ id: "minimal" }],
      documents: [],
      name: "test-workspace",
    });
    expect(result.hadCorruption).toBe(false);
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].id).toBe("minimal");
  });

  it("should handle legacy edge field names in workspace", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        { id: "a", x: 0, y: 0 },
        { id: "b", x: 100, y: 100 },
      ],
      edges: [
        { fromNodeId: "a", toNodeId: "b", relationType: "supports" },
      ],
    });
    expect(result.edges[0].sourceNodeId).toBe("a");
    expect(result.edges[0].targetNodeId).toBe("b");
    expect(result.edges[0].relationType).toBe("supports");
  });

  it("should handle complex real-world workspace data", () => {
    const result = normalizeWorkspaceState({
      nodes: [
        {
          id: "doc-1",
          type: "document",
          x: 150,
          y: 200,
          z: 0,
          title: "Project Requirements",
          content: "Initial requirements document...",
          metadata: { version: 1.0, author: "user" },
        },
        {
          id: "audio-1",
          type: "audio",
          x: 400,
          y: 300,
          z: 0,
          title: "Meeting Recording",
          metadata: { duration: 1800, date: "2026-01-12" },
        },
        {
          nodeId: "legacy-node",
          type: "text",
          label: "Legacy Format Node",
          position: { x: 600, y: 150, z: 0 },
        },
      ],
      edges: [
        {
          id: "edge-1",
          sourceNodeId: "doc-1",
          targetNodeId: "audio-1",
          relationType: "references",
          label: "Discussed in",
        },
        {
          from_node_id: "legacy-node",
          to_node_id: "doc-1",
          relation_type: "supports",
        },
      ],
    });
    expect(result.hadCorruption).toBe(false);
    expect(result.nodes).toHaveLength(3);
    expect(result.edges).toHaveLength(2);

    // Verify first node
    expect(result.nodes[0]).toEqual({
      id: "doc-1",
      type: "document",
      x: 150,
      y: 200,
      z: 0,
      title: "Project Requirements",
      content: "Initial requirements document...",
      metadata: { version: 1.0, author: "user" },
    });

    // Verify second node
    expect(result.nodes[1]).toEqual({
      id: "audio-1",
      type: "audio",
      x: 400,
      y: 300,
      z: 0,
      title: "Meeting Recording",
      metadata: { duration: 1800, date: "2026-01-12" },
    });

    // Verify legacy node normalization
    expect(result.nodes[2]).toEqual({
      id: "legacy-node",
      type: "text",
      x: 600,
      y: 150,
      z: 0,
      title: "Legacy Format Node",
    });

    // Verify first edge
    expect(result.edges[0]).toEqual({
      id: "edge-1",
      sourceNodeId: "doc-1",
      targetNodeId: "audio-1",
      relationType: "references",
      label: "Discussed in",
    });

    // Verify legacy edge normalization
    expect(result.edges[1].sourceNodeId).toBe("legacy-node");
    expect(result.edges[1].targetNodeId).toBe("doc-1");
    expect(result.edges[1].relationType).toBe("supports");
  });
});

describe("Session Load Integration", () => {
  it("should handle round-trip save/load scenario", () => {
    // Simulate saving workspace state
    const savedState = {
      nodes: [
        { id: "node-1", type: "text", x: 100, y: 200, z: 0, title: "First Node", content: "Content 1" },
        { id: "node-2", type: "document", x: 300, y: 400, z: 0, title: "Second Node" },
      ],
      edges: [
        { sourceNodeId: "node-1", targetNodeId: "node-2", relationType: "depends_on", label: "Depends on" },
      ],
    };

    // Simulate loading and normalizing (as done on session load)
    const loadedState = normalizeWorkspaceState(savedState);

    // Verify round-trip integrity
    expect(loadedState.hadCorruption).toBe(false);
    expect(loadedState.nodes).toHaveLength(2);
    expect(loadedState.edges).toHaveLength(1);
    expect(loadedState.nodes[0].title).toBe("First Node");
    expect(loadedState.nodes[0].content).toBe("Content 1");
    expect(loadedState.edges[0].relationType).toBe("depends_on");
  });

  it("should recover gracefully from corrupted session data", () => {
    // Simulate corrupted workspace with some invalid data
    const corruptedState = {
      nodes: [
        { id: "valid-1", type: "text", x: 10, y: 20, title: "Valid Node" },
        { x: 999, y: 999 }, // Invalid: missing id
        null, // Invalid: not an object
        { id: "valid-2", type: "document", x: 50, y: 100, title: "Another Valid" },
      ],
      edges: [
        { sourceNodeId: "valid-1", targetNodeId: "valid-2" },
        { invalid: "edge" }, // Invalid: missing source/target
      ],
    };

    const recoveredState = normalizeWorkspaceState(corruptedState);

    // Should recover valid data
    expect(recoveredState.hadCorruption).toBe(true);
    expect(recoveredState.nodes).toHaveLength(2);
    expect(recoveredState.edges).toHaveLength(1);
    expect(recoveredState.nodes[0].id).toBe("valid-1");
    expect(recoveredState.nodes[1].id).toBe("valid-2");
  });
});
