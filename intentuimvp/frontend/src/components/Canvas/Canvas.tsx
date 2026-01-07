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
    <div className="canvas-container">
      <TransformWrapper
        ref={transformRef}
        initialScale={1}
        minScale={0.1}
        maxScale={10}
        initialPositionX={0}
        initialPositionY={0}
        limitToBounds={false}
        panning={{
          disabled: false,
          activationKeys: [],
          ignoreKeyEvents: false,
        }}
        doubleClick={{
          disabled: false,
          step: 0.7,
          mode: "zoomIn",
        }}
        zooming={{
          disabled: false,
          step: 0.1,
          limitsOnWheel: true,
        }}
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
      `}</style>
    </div>
  );
}
