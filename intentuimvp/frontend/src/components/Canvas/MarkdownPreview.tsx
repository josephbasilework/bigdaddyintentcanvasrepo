"use client";

/* eslint-disable @next/next/no-img-element */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownPreviewVariant = "compact" | "full";

type MarkdownPreviewProps = {
  content: string;
  variant?: MarkdownPreviewVariant;
};

export function MarkdownPreview({ content, variant = "full" }: MarkdownPreviewProps) {
  const isCompact = variant === "compact";
  const textColor = isCompact ? "#cbd5f5" : "#e2e8f0";
  const headingColor = isCompact ? "#f8fafc" : "#ffffff";
  const baseFontSize = isCompact ? "12px" : "14px";
  const headingScale = isCompact ? 1 : 1.1;
  const lineHeight = isCompact ? 1.4 : 1.6;

  return (
    <div
      style={{
        fontSize: baseFontSize,
        lineHeight,
        color: textColor,
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 style={{ margin: "0 0 8px", fontSize: `calc(1.3em * ${headingScale})`, color: headingColor }}>
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 style={{ margin: "12px 0 6px", fontSize: `calc(1.15em * ${headingScale})`, color: headingColor }}>
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 style={{ margin: "12px 0 6px", fontSize: `calc(1.05em * ${headingScale})`, color: headingColor }}>
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p style={{ margin: "0 0 8px", color: textColor }}>{children}</p>
          ),
          li: ({ children }) => (
            <li style={{ marginBottom: "4px", color: textColor }}>{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote
              style={{
                margin: "8px 0",
                paddingLeft: "12px",
                borderLeft: "3px solid rgba(148, 163, 184, 0.6)",
                color: "#94a3b8",
              }}
            >
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => {
            if (!href) {
              return <span style={{ color: textColor }}>{children}</span>;
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                style={{ color: "#7dd3fc", textDecoration: "underline" }}
              >
                {children}
              </a>
            );
          },
          img: ({ src, alt }) => {
            if (!src) {
              return null;
            }
            return (
              <img
                src={src}
                alt={alt ?? ""}
                style={{
                  maxWidth: "100%",
                  borderRadius: "8px",
                  border: "1px solid rgba(148, 163, 184, 0.3)",
                  margin: "6px 0",
                }}
              />
            );
          },
          pre: ({ children }) => (
            <pre
              style={{
                backgroundColor: "rgba(15, 23, 42, 0.75)",
                padding: "10px",
                borderRadius: "8px",
                overflowX: "auto",
                margin: "8px 0",
                color: textColor,
              }}
            >
              {children}
            </pre>
          ),
          code: ({ children, className, node, ...rest }) => {
            const text = String(children ?? "");
            const isSingleLine = node?.position?.start.line === node?.position?.end.line;
            const isInline = !className && isSingleLine && !text.includes("\n");

            return (
              <code
                {...rest}
                className={className}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.75)",
                  padding: isInline ? "2px 4px" : "0",
                  borderRadius: "4px",
                  fontSize: isCompact ? "11px" : "13px",
                  color: textColor,
                }}
              >
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
