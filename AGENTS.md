# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

## Notes learned while working beads
- 2026-01-09 22:31 EST: `git commit` runs pre-commit hooks (gitleaks, ruff, mypy, eslint, etc.), so expect checks to run on commit.
- 2026-01-09 22:44 EST: `npm run build` in `intentuimvp/frontend` currently fails with a TypeScript error in `intentuimvp/frontend/src/agui/protocol.ts` (record indexing type narrowing needed).
- 2026-01-10 00:07 EST: `pip install -r intentuimvp/backend/requirements.txt` hits a google-auth resolver conflict; `python3 -m pip install --no-deps -r intentuimvp/backend/requirements.txt` works since the file is a full freeze.
- 2026-01-10 00:25 EST: `npm run build` in `intentuimvp/frontend` completed successfully; the prior TypeScript error may be resolved.
- 2026-01-10 00:37 EST: `npm test -- --run` in `intentuimvp/frontend` runs the full vitest suite once and emits existing warnings about `jsx` attributes and act wrapping.
- 2026-01-10 00:54 EST: `python` isn't available; use `python3` for backend `pytest` and `ruff` commands.
