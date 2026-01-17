"use client";

import type { ConversationScope } from "@/state/conversationStore";

interface NodeContextBannerProps {
  /** Current conversation scope */
  scope: ConversationScope;
  /** Callback when user clears the node context */
  onClearContext?: () => void;
  /** Whether to show the banner (can be dismissed) */
  visible?: boolean;
}

/**
 * Banner showing the active node context for agent interaction.
 * Displays prominently when a node is selected to indicate that
 * conversations will use that node's content as context.
 */
export function NodeContextBanner({
  scope,
  onClearContext,
  visible = true,
}: NodeContextBannerProps) {
  if (!visible || scope.type !== 'node') {
    return null;
  }

  const { nodeTitle, hasContent } = scope;
  const truncatedTitle = nodeTitle.length > 40
    ? `${nodeTitle.slice(0, 37).trimEnd()}...`
    : nodeTitle;

  return (
    <div
      className="node-context-banner"
      role="status"
      aria-live="polite"
      aria-label={`Conversation context: ${nodeTitle}`}
    >
      <div className="banner-content">
        <div className="banner-icon" aria-hidden="true">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M8 1L14.5 4.5V11.5L8 15L1.5 11.5V4.5L8 1Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle cx="8" cy="8" r="2" fill="currentColor" />
          </svg>
        </div>
        <div className="banner-text">
          <span className="banner-label">Context:</span>
          <span className="banner-title" title={nodeTitle}>
            {truncatedTitle}
          </span>
          {hasContent && (
            <span className="content-badge" title="Node content will be used as context">
              Content active
            </span>
          )}
        </div>
      </div>
      {onClearContext && (
        <button
          type="button"
          className="clear-context-button"
          onClick={onClearContext}
          aria-label="Clear node context"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M10.5 3.5L3.5 10.5M3.5 3.5L10.5 10.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          Clear
        </button>
      )}
      <style jsx>{`
        .node-context-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
          padding: 0.6rem 0.85rem;
          margin-bottom: 0.5rem;
          border-radius: 0.75rem;
          background: linear-gradient(
            135deg,
            rgba(56, 189, 248, 0.15) 0%,
            rgba(59, 130, 246, 0.1) 100%
          );
          border: 1px solid rgba(56, 189, 248, 0.4);
          color: #e0f2fe;
          animation: banner-appear 0.2s ease-out;
        }

        @keyframes banner-appear {
          from {
            opacity: 0;
            transform: translateY(-4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .banner-content {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          min-width: 0;
          flex: 1;
        }

        .banner-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          color: #38bdf8;
        }

        .banner-text {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          min-width: 0;
          flex-wrap: wrap;
        }

        .banner-label {
          font-size: 0.7rem;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: #7dd3fc;
          flex-shrink: 0;
        }

        .banner-title {
          font-size: 0.85rem;
          font-weight: 600;
          color: #f0f9ff;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 200px;
        }

        .content-badge {
          display: inline-flex;
          align-items: center;
          padding: 0.15rem 0.45rem;
          border-radius: 999px;
          background-color: rgba(56, 189, 248, 0.25);
          border: 1px solid rgba(56, 189, 248, 0.35);
          font-size: 0.65rem;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          color: #7dd3fc;
          flex-shrink: 0;
        }

        .clear-context-button {
          display: inline-flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.35rem 0.6rem;
          border: 1px solid rgba(148, 163, 184, 0.4);
          border-radius: 0.4rem;
          background: rgba(15, 23, 42, 0.6);
          color: #94a3b8;
          font-size: 0.75rem;
          cursor: pointer;
          transition: all 0.15s ease-in-out;
          flex-shrink: 0;
        }

        .clear-context-button:hover {
          border-color: rgba(148, 163, 184, 0.6);
          color: #e2e8f0;
          background: rgba(15, 23, 42, 0.8);
        }

        .clear-context-button:focus-visible {
          outline: 2px solid #38bdf8;
          outline-offset: 2px;
        }

        @media (max-width: 640px) {
          .node-context-banner {
            flex-wrap: wrap;
            padding: 0.5rem 0.7rem;
          }

          .banner-title {
            max-width: 150px;
          }

          .content-badge {
            display: none;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .node-context-banner {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
