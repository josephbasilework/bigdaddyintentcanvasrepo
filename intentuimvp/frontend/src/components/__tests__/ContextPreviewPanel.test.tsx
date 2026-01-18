import { render, screen } from "@testing-library/react";
import { ContextPreviewPanel } from "../ContextPreview/ContextPreviewPanel";
import type { ContextPreview } from "@/types/contextPreview";

describe("ContextPreviewPanel", () => {
  it("renders preview nodes and reasons", () => {
    const preview: ContextPreview = {
      input_text: "plan next steps",
      prompt: "Primary nodes:\n- [node 1] Alpha",
      nodes: [
        {
          id: "1",
          title: "Alpha",
          node_type: "text",
          score: 1.2,
          reasons: ["selected"],
          reason_scores: { selected: 0.6 },
          is_primary: true,
          similarity: 0.4,
          recency: null,
          content: "Alpha content",
          metadata: null,
        },
      ],
      turns: [],
      attachments: [],
      explicit_node_refs: [],
      explicit_turn_refs: [],
      selection: null,
    };

    render(<ContextPreviewPanel preview={preview} />);

    expect(screen.getByText("Context Preview")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Primary")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
  });
});
