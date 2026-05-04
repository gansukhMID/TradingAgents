# Forex AI Signal Engine

Production-oriented FastAPI backend for ICT/SMC Forex signal generation. The
legacy stock research workflow has been replaced with a modular multi-agent
pipeline that returns structured Pydantic JSON.

> Signals are analytical outputs, not financial advice. Connect a real broker or
> market-data provider before using this with live trading infrastructure.

## Architecture

The repository keeps the original multi-agent graph pattern and refactors it for
Forex:

1. **Data adapter** (`tradingagents.services.data`) loads OHLCV candles. The
   included deterministic fallback makes the backend runnable without stock
   vendors.
2. **Market Structure Agent** detects ICT/SMC swing highs/lows, BOS/CHOCH,
   order blocks, and fair value gaps.
3. **Liquidity Agent** identifies equal highs/lows, buy-side liquidity,
   sell-side liquidity, and sweep behavior.
4. **Technical Analysis Agent** calculates Forex-focused EMA, RSI, ATR, MACD,
   average range, support, and resistance.
5. **Risk Management Agent** builds entry, stop loss, take profit, risk/reward,
   risk amount, and position units from account/risk settings.
6. **Signal Synthesis Agent** combines agent outputs into a final structured
   `ForexSignal`.
7. **LangGraph Workflow** (`tradingagents.graph.forex_graph`) orchestrates the
   stages as typed nodes. No monolithic LLM call is required.

## API

### `GET /health`

Returns service health metadata.

### `POST /signals`

Request:

```json
{
  "pair": "EURUSD",
  "timeframe": "1h",
  "lookback": 160,
  "account_equity": 10000,
  "risk_per_trade": 0.01,
  "min_rr": 2.0
}
```

You may also pass a `candles` array with at least 50 OHLCV candles. If candles
are omitted, the service uses the bundled deterministic Forex data adapter.

Response includes:

- `direction`: `buy`, `sell`, or `hold`
- `confidence`
- `risk_plan`
- `market_structure`
- `liquidity`
- `technicals`
- `rationale`

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install .
uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8000
```

Or use the package script:

```bash
forex-signal-engine
```

Open API docs at `http://localhost:8000/docs`.

## Docker

```bash
docker compose up --build
```

## Development layout

```text
tradingagents/
  api/             FastAPI app and server CLI
  agents/forex.py  Modular Forex agents
  domain/          Pydantic request/response/domain schemas
  graph/           LangGraph workflow
  indicators/      Forex technical indicators
  services/        Data adapters
```

## Production extension points

- Replace `ForexDataService` with a broker/data-provider adapter.
- Add authentication and request throttling at the FastAPI boundary.
- Persist `ForexSignal` outputs to a database or queue for downstream execution.
- Add optional LLM commentary as a separate agent that consumes the typed reports;
  keep the deterministic agents as the authoritative signal source.
