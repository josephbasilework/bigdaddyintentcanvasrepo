#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

iterations="$1"

PROMPT="$(cat <<'PROMPT'
1. Run `bd ready` to grab the next highest priority task that's ready to be worked on. Note the task ID from the output.
2. Mark the task as in progress by running `bd update <TASK_ID> --status in_progress` (replace <TASK_ID> with the actual ID from step 1, e.g. bd update abc123 --status in_progress).
3. Work on the task until it's complete. Make sure to write tests, lint your code, commit your code and make sure it's secure. Be thoughtful about your changes, keeping the code clean & maintainable.
4. Mark the task complete by running `bd close <TASK_ID> --reason '<reason>'` (use the same task ID from step 1).
5. Run `bd sync` to sync the changes with the git remote.

ONLY WORK ON A SINGLE TASK.

Use subagents as needed to explore the repo, investigate errors, or research implementation details in parallel.
Maintain a clear todo list in your working memory and update it as you go (subtasks, acceptance criteria, blockers).

If, while implementing the task, you notice all the tasks are complete and there are no ready tasks, return the string:
<promise>ALL BEADS TASKS COMPLETED</promise>
PROMPT
)"

for ((i=0; i<iterations; i++)); do
  echo "Iteration $i"
  echo "--------------------------------"

  # Amp execute mode: send PROMPT, wait for agent to finish its turn, print final message, exit.
  result="$(amp --dangerously-allow-all -x "$PROMPT")"
  echo "$result"

  if [[ "$result" == *"<promise>ALL BEADS TASKS COMPLETED</promise>"* ]]; then
    if [[ "$(bd count --status open)" -eq 0 ]]; then
      echo "All beads tasks completed"
      exit 0
    else
      echo "Amp said all beads tasks are complete, but there are still open tasks. Retrying."
    fi
  fi
done
