"use client";

import { ReactZoomPanPinchRef, TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { useCallback, useRef } from "react";

interface CanvasProps {
  children?: React.ReactNode;
}

const PAN_STEP = 40;

/**
 * Canvas component for the IntentUI workspace.
 *
 * Provides a full-viewport pannable and zoomable canvas area
 * where nodes and other elements can be rendered.
 */
export function Canvas({ children }: CanvasProps) {
  const transformRef = useRef<ReactZoomPanPinchRef>(null);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.currentTarget !== event.target) return;

    const transform = transformRef.current;
    if (!transform) return;

    const { positionX, positionY, scale } = transform.state;
    const hasModifier = event.metaKey || event.ctrlKey;
    const key = event.key;

    if (hasModifier && (key === "=" || key === "+")) {
      event.preventDefault();
      transform.zoomIn();
      return;
    }

    if (hasModifier && key === "-") {
      event.preventDefault();
      transform.zoomOut();
      return;
    }

    if (hasModifier && key === "0") {
      event.preventDefault();
      transform.resetTransform();
      return;
    }

    let nextX = positionX;
    let nextY = positionY;
    let handled = true;

    switch (key) {
      case "ArrowRight":
        nextX = positionX - PAN_STEP;
        break;
      case "ArrowLeft":
        nextX = positionX + PAN_STEP;
        break;
      case "ArrowDown":
        nextY = positionY - PAN_STEP;
        break;
      case "ArrowUp":
        nextY = positionY + PAN_STEP;
        break;
      default:
        handled = false;
        break;
    }

    if (!handled) return;

    event.preventDefault();
    transform.setTransform(nextX, nextY, scale, 0);
  }, []);

  return (
    <div
      className="canvas-container"
      data-testid="canvas-container"
      role="region"
      aria-label="Canvas workspace"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
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

        .canvas-container:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: -2px;
          box-shadow: inset 0 0 0 2px var(--focus-ring);
        }

        @supports not selector(:focus-visible) {
          .canvas-container:focus {
            outline: 2px solid var(--focus-ring);
            outline-offset: -2px;
            box-shadow: inset 0 0 0 2px var(--focus-ring);
          }
        }
      `}</style>
    </div>
  );
}
