/**
 * Integration test for useWebSocket hook with real backend.
 * NOTE: This test is skipped in jsdom/test environments because WebSocket
 * connections don't work properly in Node.js test environments.
 *
 * To manually test the WebSocket hook:
 * 1. Start the backend server (e.g., `cd backend && uvicorn app.main:app --reload`)
 * 2. Start the frontend dev server (e.g., `cd frontend && npm run dev`)
 * 3. Open browser DevTools console and use the hook directly, or create a demo page
 */

import { describe, it } from "vitest";

describe("useWebSocket Integration (with backend)", () => {
  it.skip("should connect to real backend WebSocket endpoint - manual test only", async () => {
    // Skipped: WebSocket connections don't work in jsdom environment
    // Manual testing required:
    // 1. Ensure backend is running on localhost:8000
    // 2. Use the hook in a real browser to verify connection
    // 3. Verify send/receive functionality
  });
});
