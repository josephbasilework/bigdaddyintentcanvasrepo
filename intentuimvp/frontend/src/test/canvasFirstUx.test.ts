import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = path.resolve(__dirname, "..");
const SOURCE_DIRS = ["app", "components", "hooks", "agui", "state"];
const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
const SKIP_DIRS = new Set(["__tests__", "__mocks__", "test", "tests"]);
const DISALLOWED_IMPORT = "@copilotkit/react-ui";

const collectSourceFiles = (dir: string, files: string[] = []): string[] => {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) {
        continue;
      }
      collectSourceFiles(path.join(dir, entry.name), files);
      continue;
    }

    if (entry.isFile() && SOURCE_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(path.join(dir, entry.name));
    }
  }
  return files;
};

describe("canvas-first UX", () => {
  it("keeps CopilotKit in headless mode (no chat UI imports)", () => {
    const matches: string[] = [];

    for (const subdir of SOURCE_DIRS) {
      const root = path.join(SRC_ROOT, subdir);
      if (!fs.existsSync(root)) {
        continue;
      }

      const files = collectSourceFiles(root);
      for (const file of files) {
        const contents = fs.readFileSync(file, "utf8");
        if (contents.includes(DISALLOWED_IMPORT)) {
          matches.push(path.relative(SRC_ROOT, file));
        }
      }
    }

    expect(matches).toEqual([]);
  });
});
