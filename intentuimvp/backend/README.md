# IntentUI Backend

## Dev setup (pytest/ruff)

### Option A: bootstrap script (recommended)

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
python3 scripts/bootstrap_test_tools.py
```

### Option B: manual setup

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --no-deps -r requirements.txt
```

`requirements.txt` is fully pinned; `--no-deps` avoids resolver conflicts.

## Run quality gates

```bash
cd ~/bigdaddyintentcanvasrepo/intentuimvp/backend
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

Use `.venv/bin/python` (or `.venv/bin/ruff`) so the venv-installed tools are picked up.
If you see `ModuleNotFoundError` for `pytest` or `ruff`, rerun the bootstrap script above.
