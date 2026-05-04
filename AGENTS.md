# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Forex AI Signal Engine — a single-service FastAPI backend (`tradingagents/`) that generates deterministic Forex trading signals via a LangGraph multi-agent pipeline. No external services (databases, LLMs, brokers) are required; it uses bundled dummy market data.

### Running the application

```bash
. .venv/bin/activate
uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8000 --reload
```

API docs are at `http://localhost:8000/docs`. Key endpoints: `GET /health`, `POST /analyze`, `POST /signals`.

### Running tests

```bash
. .venv/bin/activate
python -m pytest tests/ -v
```

### Linting

No linter is configured in this project. There is no `ruff`, `flake8`, `mypy`, or similar tool in the dev dependencies or `pyproject.toml`.

### Notes

- Python >= 3.10 is required (`pyproject.toml`). The VM has Python 3.12.
- The virtual environment lives at `.venv/`. Always activate it before running commands.
- `python3.12-venv` system package must be installed for `python3 -m venv` to work (not present by default on the VM).
- `requirements.txt` contains just `.` — it delegates to `pyproject.toml` for all dependency resolution.
- The project installs a console script `forex-signal-engine` that launches uvicorn, but for development use `uvicorn ... --reload` directly.
- All agents are deterministic (no LLM API keys needed). The `ForexDataService` generates dummy OHLCV candles when no real data is provided.
