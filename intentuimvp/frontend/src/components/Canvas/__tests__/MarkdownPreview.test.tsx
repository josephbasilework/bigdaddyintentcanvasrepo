import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownPreview } from "../MarkdownPreview";

describe("MarkdownPreview", () => {
  it("applies inline padding only to inline code", () => {
    const content = "Inline `code` and block:\n\n```js\nconst x = 1;\n```";

    render(<MarkdownPreview content={content} />);

    const inlineCode = screen.getByText("code");
    expect(inlineCode.tagName).toBe("CODE");
    expect(inlineCode).toHaveStyle("padding: 2px 4px");

    const blockCode = screen.getByText(/const x = 1/);
    expect(blockCode.tagName).toBe("CODE");
    expect(blockCode).toHaveStyle("padding: 0");
  });
});
