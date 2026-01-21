# IntentUI Backend

## Dev setup (pytest/ruff)

### Option A: bootstrap script (recommended)

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
python3 scripts/bootstrap_test_tools.py
```

**Why this matters:** system `python3` in some environments does **not** include `pytest`/`ruff`, and `pip`/`apt` may be unavailable.
The bootstrap script creates a local `.venv`, runs `ensurepip`, and installs the pinned requirements so tooling is available without
system package managers.

### Option B: manual setup

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --no-deps -r requirements.txt
```

`requirements.txt` is fully pinned; `--no-deps` avoids resolver conflicts.

### Tooling availability notes

- Always run backend tooling from `.venv/bin/...` (not system Python).
- If `pytest`/`ruff` are missing, re-run the bootstrap script or reinstall the venv requirements.
- If `python3 -m venv` fails (missing `venv` module), install `python3-venv` or use a Python build that includes it.
- You can sanity-check tooling with:
  - `.venv/bin/python -m pytest --version`
  - `.venv/bin/python -m ruff --version`

## Run quality gates

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

Use `.venv/bin/python` (or `.venv/bin/ruff`) so the venv-installed tools are picked up.
If you see `ModuleNotFoundError` for `pytest` or `ruff`, rerun the bootstrap script above.
