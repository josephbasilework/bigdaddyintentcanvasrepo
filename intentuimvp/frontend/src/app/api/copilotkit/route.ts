/**
 * CopilotKit Runtime API endpoint.
 *
 * This endpoint hosts a CopilotRuntime with a default BasicAgent that connects
 * to the Python backend as a remote endpoint for actions.
 *
 * Architecture:
 *   React UI -> This Runtime (default agent) -> Python /copilotkit (actions)
 */

import type { NextRequest } from "next/server";
import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  OpenAIAdapter,
} from "@copilotkit/runtime";

const PYTHON_BACKEND_URL =
  process.env.COPILOT_PYTHON_ENDPOINT ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

let cachedServiceAdapter: OpenAIAdapter | null = null;

const getServiceAdapter = () => {
  if (!cachedServiceAdapter) {
    cachedServiceAdapter = new OpenAIAdapter({
      model: "gpt-4o-mini",
    });
  }

  return cachedServiceAdapter;
};

export async function POST(req: NextRequest) {
  const runtime = new CopilotRuntime({
    remoteEndpoints: [
      {
        url: `${PYTHON_BACKEND_URL}/copilotkit`,
      },
    ],
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: getServiceAdapter(),
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
}
