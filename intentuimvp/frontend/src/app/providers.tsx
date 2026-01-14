"use client";

import { CopilotKit } from "@copilotkit/react-core";
import type { ReactNode } from "react";

type CopilotKitProviderProps = {
  children: ReactNode;
};

/**
 * Runtime URL for CopilotKit.
 *
 * In CopilotKit v1.50+, the frontend must connect to a CopilotRuntime (not a
 * remote endpoint directly). We host the runtime at /api/copilotkit in this
 * Next.js app, which then connects to the Python backend's remote endpoint.
 *
 * Flow: React UI -> /api/copilotkit (runtime) -> Python /copilotkit (actions)
 */
const runtimeUrl = (() => {
  const explicitUrl = process.env.NEXT_PUBLIC_COPILOT_RUNTIME_URL;
  if (explicitUrl && explicitUrl.length > 0) {
    return explicitUrl;
  }
  return "/api/copilotkit";
})();

export function CopilotKitProvider({ children }: CopilotKitProviderProps) {
  return (
    <CopilotKit runtimeUrl={runtimeUrl} showDevConsole={false} enableInspector={false}>
      {children}
    </CopilotKit>
  );
}
