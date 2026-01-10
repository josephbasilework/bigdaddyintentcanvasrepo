"use client";

import { CopilotKit } from "@copilotkit/react-core";
import type { ReactNode } from "react";

type CopilotKitProviderProps = {
  children: ReactNode;
};

const runtimeUrl = (() => {
  const explicitUrl = process.env.NEXT_PUBLIC_COPILOT_RUNTIME_URL;
  if (explicitUrl && explicitUrl.length > 0) {
    return explicitUrl;
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${apiBase.replace(/\/$/, "")}/copilotkit`;
})();

export function CopilotKitProvider({ children }: CopilotKitProviderProps) {
  return (
    <CopilotKit runtimeUrl={runtimeUrl} showDevConsole={false} enableInspector={false}>
      {children}
    </CopilotKit>
  );
}
