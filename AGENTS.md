# AGENTS.md

## Cursor Cloud specific instructions

This is a single-service Python FastAPI application (Forex AI Signal Engine). No external databases, message queues, or API keys are required — the `ForexDataService` generates deterministic synthetic OHLCV data when no real data is provided.

### Quick reference

| Action | Command |
|---|---|
| Install deps (with dev/test) | `pip install ".[dev]"` |
| Run tests | `python3 -m pytest tests/ -v` |
| Start dev server (hot-reload) | `python3 -m uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8000 --reload` |
| Start dev server (CLI) | `forex-signal-engine` |
| API docs | `http://localhost:8000/docs` |

### Non-obvious notes

- **No linter configured.** The project does not include ruff, flake8, mypy, or any other linter in its dependencies or config.
- **`requirements.txt` contains only `.`** — it delegates to `pyproject.toml` for all dependency resolution. Always use `pip install ".[dev]"` for development.
- **All agents are deterministic** — no LLM API keys are needed. The `ForexSignalGraph` runs a LangGraph `StateGraph` pipeline with purely algorithmic agents.
- **`python` vs `python3`** — this environment only has `python3` on PATH; use `python3` explicitly.
- **Test data** — tests generate synthetic candles inline; no fixtures or external data files are needed.
