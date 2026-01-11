"use client";

import { ReactZoomPanPinchRef, TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { useRef } from "react";

interface CanvasProps {
  children?: React.ReactNode;
}

/**
 * Canvas component for the IntentUI workspace.
 *
 * Provides a full-viewport pannable and zoomable canvas area
 * where nodes and other elements can be rendered.
 */
export function Canvas({ children }: CanvasProps) {
  const transformRef = useRef<ReactZoomPanPinchRef>(null);

  return (
    <div className="canvas-container" data-testid="canvas-container">
      <TransformWrapper
        ref={transformRef}
        initialScale={1}
        minScale={0.1}
        maxScale={10}
        limitToBounds={false}
      >
        <TransformComponent
          wrapperStyle={{
            width: "100vw",
            height: "100vh",
            overflow: "hidden",
          }}
          contentStyle={{
            width: "100%",
            height: "100%",
          }}
        >
          <div className="canvas-content">{children}</div>
        </TransformComponent>
      </TransformWrapper>
      <style jsx>{`
        .canvas-container {
          width: 100vw;
          height: 100vh;
          position: relative;
          overflow: hidden;
          background-color: #0a0a0a;
          background-image: radial-gradient(circle, #222 1px, transparent 1px);
          background-size: 20px 20px;
        }
        .canvas-content {
          position: absolute;
          top: 0;
          left: 0;
          min-width: 100%;
          min-height: 100%;
        }

        .canvas-content:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: -2px;
          box-shadow: inset 0 0 0 2px var(--focus-ring);
        }

        @supports not selector(:focus-visible) {
          .canvas-content:focus {
            outline: 2px solid var(--focus-ring);
            outline-offset: -2px;
            box-shadow: inset 0 0 0 2px var(--focus-ring);
          }
        }
      `}</style>
    </div>
  );
}
