import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // Gateway-only enforcement: Ban direct LLM provider SDK imports
    // All LLM calls must go through the backend Gateway API
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["openai", "anthropic", "@anthropic-ai/sdk", "google/generative-ai", "cohere-*", "langchain*"],
              message: "Direct LLM provider SDK imports are not allowed. All LLM calls must go through the backend Gateway API. See app/gateway/client.py for the Gateway client implementation.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
