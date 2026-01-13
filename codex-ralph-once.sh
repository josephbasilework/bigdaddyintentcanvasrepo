#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

iterations="$1"

if ! command -v codex >/dev/null 2>&1; then
  echo "Error: 'codex' CLI not found in PATH."
  exit 1
fi

if ! command -v bd >/dev/null 2>&1; then
  echo "Error: 'bd' CLI not found in PATH."
  exit 1
fi

PROMPT="$(cat <<'PROMPT'
1. Run `bd ready` to grab the next highest priority task that's ready to be worked on. Note the task ID from the output.
2. Mark the task as in progress by running `bd update <TASK_ID> --status in_progress` (replace <TASK_ID> with the actual ID from step 1, e.g. bd update abc123 --status in_progress)
3. Before coding, write a short plan (bullets) describing what you'll change and how you'll validate it.
4. Work on the task until it's complete. Make sure to write tests, lint your code, commit your code and make sure it's secure.
Be thoughtful about your changes, keeping the code clean & maintainable.
5. Mark the task complete by running `bd close <TASK_ID> --reason '<reason>'` (use the same task ID from step 1)
6. Run `bd sync` to sync the changes with the git remote.
ONLY WORK ON A SINGLE TASK.
ultrathink
If, while implementing the task, you notice all the tasks are complete and there are no ready tasks, return the string <promise>ALL BEADS TASKS COMPLETED</promise>
PROMPT
)"

for ((i=0; i<iterations; i++)); do
  echo "Iteration $i"
  echo "--------------------------------"

  # Use codex exec (scripting mode). Reasoning effort is configured via -c model_reasoning_effort=...
  result="$(
    codex exec --yolo \
      --model "gpt-5.2-codex" \
      -c model_reasoning_effort=xhigh \
      "$PROMPT"
  )"

  echo "$result"

  if [[ "$result" == *"<promise>ALL BEADS TASKS COMPLETED</promise>"* ]]; then
    open_count="$(bd count --status open | tr -d '[:space:]' || true)"

    if [[ "${open_count:-}" =~ ^[0-9]+$ ]] && [[ "$open_count" -eq 0 ]]; then
      echo "All beads tasks completed"
      exit 0
    else
      echo "Codex said all beads tasks are complete, but there are still open tasks. Retrying."
    fi
  fi
done
