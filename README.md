# AI Financial Copilot

AI Financial Copilot is a full-stack financial intelligence assistant that helps finance teams investigate reconciliation failures, anomalies, and invoice discrepancies using natural language. It combines:

- a **FastAPI backend** with intent-aware retrieval, a multi-model LLM pool (OpenRouter-compatible), and a streaming chat API
- a **Supabase**-backed data layer storing synthetic ERP, bank, reconciliation, and anomaly datasets
- an **Angular** frontend chat assistant that streams responses and supports editing/regenerating messages

## Project Structure

```text
financial-copilot/
  backend/
    app/
      main.py                  # FastAPI app, CORS for Angular, router registration
      routes/
        copilot.py             # /copilot/chat, /copilot/chat/stream, /copilot/health/models
      services/
        database.py            # Supabase query helpers (invoices, anomalies, reconciliation...)
        financial_rules.py     # invoice vs. payment reconciliation rule engine
        llm/
          client.py            # OpenAI-compatible client wrapper
          manager.py           # model pool, fallback, health, generate/stream
          models.py            # request/response models
          prompts.py           # prompt builder + intent -> route mapping
          routing.py           # IntentClassifier + IntentType definitions
    database/
      supabase_client.py       # Supabase client initialization
    scripts/
      import_data.py           # CSV -> Supabase importer
    requirements.txt
  frontend/                    # Angular 18 standalone-components app
    src/
      app/
        app.config.ts          # providers (router, http, markdown)
        app.routes.ts          # routes (layout + copilot)
        core/
          layout/              # sidebar/header shell layout component
          models/
            copilot.models.ts  # request/response interfaces
          services/
            copilot.service.ts # HTTP + SSE streaming client
        features/
          copilot/             # chat UI (messages, streaming, edit/regenerate)
      environments/
        environment.ts         # apiUrl -> http://127.0.0.1:8000
    package.json
    angular.json
  datasets/
    bank/bank_transactions.csv
    erp/erp_transactions.csv
    reconciliations/anomalies.csv
    reconciliations/reconciliation_results.csv
  docs/                        # currently empty
  scripts/
    generate_data.py           # synthetic dataset generator
```

## Current State

### Backend

- FastAPI app in `backend/app/main.py` with CORS allowing the Angular dev server (`localhost:4200`).
- `POST /copilot/chat` — non-streaming answer with metadata (model, tier, fallback, response_time, intent).
- `POST /copilot/chat/stream` — Server-Sent Events stream (`token` / `done` / `error` events).
- `GET /copilot/health/models` — LLM model-pool health and labels.
- **Intent classification** (`services/llm/routing.py`): greetings, thanks, small talk, identity/capability questions, general knowledge, and financial intents (invoice lookup, reconciliation analysis, anomaly lookup, dataset review, report summary, recommendations, comparison, trend analysis) are detected before any LLM call.
- **Intent-aware retrieval** (`routes/copilot.py`): the database context is built per intent — invoice + transactions + reconciliation lookups, anomaly lookups, executive dataset summaries, duplicate/missing payment lists, recent reconciliation, etc. This replaces the old "always fetch 5 anomalies" behavior.
- **Financial rule engine** (`services/financial_rules.py`): compares invoice amounts to bank payments and produces structured insights (payment shortfall, overpayment, reconciliation failure, paid-with-issue, unusual status) that enrich the LLM context.
- **LLM layer** (`services/llm/`): a manager with a model pool, automatic fallback across models, caching, token budgets per intent, and streaming support via an OpenAI-compatible client (OpenRouter). `AIServiceUnavailableError` surfaces as HTTP `503` when all models fail.
- Supabase data helpers in `services/database.py` cover invoices, bank transactions, anomalies (by severity/type), reconciliation, and a dataset summary used for dashboards/reports.

### Frontend

- Angular 18 app using standalone components, `provideHttpClient`, and `ngx-markdown` for rendered answers.
- `CopilotService` posts to `/copilot/chat` and streams from `/copilot/chat/stream` over `fetch` + `ReadableStream`, parsing SSE `data:` frames.
- `CopilotComponent` renders a chat thread with streaming tokens, copy/edit/regenerate message actions, and per-message model metadata.
- `LayoutComponent` provides the app shell (collapsible sidebar, user dropdown). The sidebar lists Dashboard, Transactions, Reconciliation, AI Assistant, Reports, and Settings — currently only the AI Assistant (`/copilot`) route is implemented; the others are placeholders.
- API base URL is configured in `src/environments/environment.ts` (`http://127.0.0.1:8000`).

### Not Yet Implemented

- Other frontend routes (Dashboard, Transactions, Reconciliation, Reports, Settings) are sidebar placeholders only.
- Production-grade semantic retrieval (embeddings/search/ranking) — current retrieval is rule + intent based.
- Project documentation in `docs/` (folder exists but empty).
- Tests and CI workflow.
- A committed `.env.example` template (backend `.env` exists locally for secrets).

## Backend Setup

### 1. Create and activate a virtual environment

Windows PowerShell example:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in `backend/` with:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
# OR use SUPABASE_KEY instead of SUPABASE_SERVICE_ROLE_KEY
SUPABASE_KEY=your_supabase_key

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your_openrouter_api_key
```

Notes:

- `SUPABASE_URL` is required.
- One of `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_KEY` is required.
- LLM calls require `OPENROUTER_API_KEY`.

### 4. Run the API

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

Default endpoints:

- API root: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Chat endpoint: `POST http://127.0.0.1:8000/copilot/chat`
- Streaming chat: `POST http://127.0.0.1:8000/copilot/chat/stream`
- Model health: `GET http://127.0.0.1:8000/copilot/health/models`

## Frontend Setup

### 1. Install dependencies

From `frontend/`:

```powershell
npm install
```

### 2. Configure the API URL

The API base URL is set in `frontend/src/environments/environment.ts`:

```ts
export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8000'
};
```

Update this if your backend runs on a different host/port. CORS on the backend only allows `localhost` / `127.0.0.1:4200`, so keep the dev server on the default port.

### 3. Run the dev server

From `frontend/`:

```powershell
npm start
```

The app is served at `http://localhost:4200/` and proxies chat requests to the backend on port `8000`.

### 4. Build

```powershell
npm run build
```

Output is written to `frontend/dist/`.

## Data Pipeline

### Generate synthetic datasets

From project root:

```powershell
python scripts/generate_data.py
```

This generates/overwrites CSV files under:

- `datasets/erp/erp_transactions.csv`
- `datasets/bank/bank_transactions.csv`
- `datasets/reconciliations/reconciliation_results.csv`
- `datasets/reconciliations/anomalies.csv`

### Import datasets to Supabase

From `backend/`:

```powershell
python scripts/import_data.py
```

Expected target tables:

- `erp_transactions`
- `bank_transactions`
- `reconciliations`
- `anomalies`

Optional tuning:

- `SUPABASE_IMPORT_BATCH_SIZE` (default: `500`)

## API Examples

### Non-streaming request

```http
POST /copilot/chat
Content-Type: application/json

{
  "question": "Why did reconciliation fail for invoice INV00042?"
}
```

Response shape:

```json
{
  "question": "Why did reconciliation fail for invoice INV00042?",
  "answer": "...",
  "model": "openai/gpt-...",
  "tier": 1,
  "fallback_used": false,
  "response_time": 1.42,
  "intent": "RECONCILIATION_ANALYSIS",
  "database_used": true,
  "cache_used": false,
  "pool": "Conversation Pool"
}
```

### Streaming request

```http
POST /copilot/chat/stream
Content-Type: application/json

{ "question": "Summarize this month's anomalies" }
```

Streamed SSE frames (`text/event-stream`):

```text
data: {"type":"token","content":"Based"}
data: {"type":"token","content":" on the"}
...
data: {"type":"done","model":"...","tier":1,"fallback_used":false,"response_time":1.2,"intent":"DATASET_REVIEW","database_used":true,"cache_used":false,"pool":"..."}
```

Conversational intents (greetings, thanks, small talk) return an immediate `fast_response` without an LLM call or database lookup.

## Suggested Next Milestones

1. Implement the remaining frontend routes (Dashboard, Transactions, Reconciliation, Reports, Settings).
2. Add `.env.example` and onboarding notes for secrets.
3. Add unit/integration tests for routes, services, and the financial rule engine.
4. Upgrade retrieval to semantic search (embeddings) with ranking across all financial tables.
5. Add docs for the Supabase schema and a deployment workflow.
