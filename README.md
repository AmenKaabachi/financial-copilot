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
        __init__.py
        conversations.py       # Conversation history CRUD endpoints
        copilot.py             # /copilot/chat, /copilot/chat/stream, /copilot/health/models,
                               # /copilot/benchmark, /copilot/continuation/clear
      services/
        __init__.py
        timing.py              # RequestMetrics: structured latency tracking and request IDs
        database.py            # Supabase query helpers with entity-level caching
        financial_rules.py     # invoice vs. payment reconciliation rule engine
        conversation.py        # chat history persistence
        conversation_state.py  # per-session conversation state management
        continuation_state.py  # interrupted generation tracking for "continue" requests
        context_budget.py      # token budget calculation, validation, overflow prevention
        context_formatter.py   # record trimming to essential fields before prompt construction
        token_counter.py       # tiktoken-based accurate token estimation + model context limits
        analytics.py           # statistics calculators for reconciliation, anomalies, payments
        benchmark/
          __init__.py
          benchmark_models.py  # Pydantic models for benchmark requests/responses/rankings
          benchmark_service.py # model test runner, TTFT measurement, ranking calculation
        llm/
          __init__.py
          client.py            # OpenAI-compatible client wrapper
          manager.py           # model pool, 3-tier fallback, health, generate/stream, response cache
          models.py            # model config, 3-tier pools, per-intent model routing
          prompts.py           # intent-specific prompt builders (full, lightweight, minimal)
          routing.py           # IntentClassifier + IntentType definitions + direct-answer patterns
    database/
      __init__.py
      supabase_client.py       # Supabase client initialization
    scripts/
      import_data.py           # CSV -> Supabase importer
    check_syntax.py            # Python syntax checker
    requirements.txt
  frontend/                    # Angular 18 standalone-components app
    src/
      app/
        app.config.ts          # providers (router, http, markdown)
        app.routes.ts          # routes (layout + copilot + benchmark)
        core/
          layout/              # sidebar/header shell layout component
          models/
            conversation.models.ts  # conversation request/response interfaces
            copilot.models.ts       # copilot request/response interfaces
          services/
            benchmark-state.service.ts  # benchmark state management
            conversation.service.ts     # conversation history service
            copilot.service.ts          # HTTP + SSE streaming client
        features/
          benchmark/           # LLM model benchmark comparison UI
            benchmark.component.ts/html/css
            benchmark.models.ts
            benchmark.service.ts
            benchmark-charts/  # Chart.js visualization components
          copilot/             # chat UI (messages, streaming, edit/regenerate)
            copilot.component.ts/html/css
            conversation-history.component.ts/html/css
            conversation-item.component.ts/css
            new-conversation-button.component.ts/css
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
    migrate_chat_history.sql   # Supabase migration for chat history
  tests/
    copilot_cases.json         # Test cases for copilot evaluation
    copilot_context_regression.py  # Context regression tests
    run_evaluation.py          # Evaluation runner
  _patch_conv.py               # Migration patches
  _patch_copilot.py
  _patch_copilot2.py
  _patch_copilot3.py
```

## Current State

### Backend Architecture

The backend follows a pipeline architecture:

```
User Request
    │
    ▼
Intent Classification (routing.py)
  - Regex + keyword scoring against 18 intent types
  - Direct-answer pattern detection (skips LLM entirely)
  - Entity extraction (invoice IDs, anomaly IDs, etc.)
  - Conversation memory for pronoun resolution
    │
    ▼
Context Retrieval (copilot.py)
  - Intent-aware database queries
  - Entity-level caching (database.py)
  - Financial rule engine (financial_rules.py)
  - Analytics calculations (analytics.py)
    │
    ▼
Prompt Construction (prompts.py)
  - Intent-specific system prompts
    - Full prompt (~1500 words): complex analysis, dataset review, recommendations
    - Lightweight prompt (~400 words): invoice/anomaly/reconciliation lookups
    - Minimal prompt (~50 words): general knowledge / financial general
  - Context fields included only when populated
    │
    ▼
LLM Generation (manager.py)
  - Per-intent model pool selection
  - Tiered fallback (3 tiers, 8s/15s/25s timeouts)
  - Caching (LLM response cache, 5-min TTL)
  - Streaming support (SSE with metadata events)
  - Token budgets per intent (12s fast / 25s complex)
    │
    ▼
Structured Logging (timing.py)
  - Request ID (UUID per request)
  - Per-stage latency breakdown
  - Token metrics (prompt/completion/total)
  - Tokens/sec calculation
```

### Request Lifecycle with Metrics

Every request is logged with a structured summary:

```
======== Request [9AF31] ========
Intent             : invoice_lookup
  Intent Classification :   11.2ms
  Context Retrieval     :  142.5ms | Invoice:18ms Anomaly:31ms
  Prompt Construction   :    8.7ms
  LLM Generation        : 3210.1ms
Model              : google/gemma-4-26b-a4b-it:free
Provider           : OpenRouter
Pool               : Financial Analysis Pool
Finish Reason      : stop
Prompt Tokens      : 1782
Completion Tokens  : 642
Total Tokens       : 2424
Max Tokens         : 800
Tokens/sec         : 202.3
Prompt Size (chars): 14280
Rows Retrieved     : 3
Database Used      : True
Cache Hit          : False
Fallback Used      : False
Total Time         : 3372.5ms
```

### Key Features

#### 1. Intent Classification (`services/llm/routing.py`)

18 intent types detected before any LLM call:

| Intent                                     | LLM Required | Database Required | Description                             |
| ------------------------------------------ | ------------ | ----------------- | --------------------------------------- |
| GREETING, GOODBYE, THANKS, SMALL_TALK      | No           | No                | Instant rule-based responses            |
| ASSISTANT_IDENTITY, ASSISTANT_CAPABILITIES | No           | No                | Pre-defined identity responses          |
| GENERAL_KNOWLEDGE                          | Yes          | No                | General accounting concept explanations |
| FINANCIAL_GENERAL                          | Yes          | No                | Financial term definitions              |
| INVOICE_LOOKUP                             | Yes          | Yes               | Single invoice details                  |
| ANOMALY_LOOKUP                             | Yes          | Yes               | Anomaly investigation                   |
| RECONCILIATION_ANALYSIS                    | Yes          | Yes               | ERP vs bank comparison                  |
| DATASET_REVIEW                             | Yes          | Yes               | Executive dashboard summary             |
| REPORT_SUMMARY                             | Yes          | Yes               | Aggregated metrics                      |
| TREND_ANALYSIS                             | Yes          | Yes               | Time-based pattern analysis             |
| COMPARISON                                 | Yes          | Yes               | Side-by-side comparisons                |
| RECOMMENDATIONS                            | Yes          | Yes               | Actionable suggestions                  |
| FINANCIAL_ANALYSIS                         | Yes          | Yes               | General financial investigation         |

#### 2. Direct SQL Responses (No LLM)

Simple factual queries skip the LLM entirely and return in milliseconds:

- "How many invoices are there?" → `SELECT COUNT(*)` → "There are **45** invoices in the system."
- "How many anomalies exist?" → Instant count response
- "How many high severity anomalies?" → Filtered count
- "How many duplicate/missing payments?" → Type-filtered count

Supported queries: invoice count, transaction count, anomaly count, high-severity count, duplicate payment count, missing payment count, reconciliation count.

#### 3. Structured Latency Tracking (`services/timing.py`)

Every request generates a `RequestMetrics` object with:

- **Request ID** (8-char hex UUID, e.g., `9AF31B2C`)
- **Per-stage timing**: Intent Classification → Context Retrieval → Prompt Construction → LLM Generation
- **Token metrics**: prompt_tokens, completion_tokens, total_tokens
- **Performance**: tokens/sec, time-to-first-token (streaming)

The metrics are logged as a structured block and included in API responses as `request_id`.

#### 4. Intent-Aware SSE Status Events

Streaming responses emit immediate status events before the LLM starts generating:

```
Invoice lookup:
  → {"type":"status","message":"Searching invoice records..."}
  → {"type":"status","message":"Checking reconciliation..."}
  → {"type":"status","message":"Preparing invoice analysis..."}
  → {"type":"token","content":"Based on..."}
  ...

Anomaly lookup:
  → {"type":"status","message":"Finding anomaly records..."}
  → {"type":"status","message":"Analyzing financial impact..."}
  → {"type":"status","message":"Generating recommendations..."}
  → {"type":"token","content":"The..."}
  ...
```

Each intent has a custom sequence (11 intent-specific message sets).

#### 5. Intelligent Prompt Selection (`services/llm/prompts.py`)

Three system prompt templates selected by intent:

| Intent(s)                                               | Prompt Size | Contents                                                                                              |
| ------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------- |
| invoice_lookup, anomaly_lookup, reconciliation_analysis | ~400 words  | Brief identity + data rules + formatting. Omits general knowledge guidelines and verbose style rules. |
| general_knowledge, financial_general                    | ~50 words   | Minimal "explain concepts" instruction.                                                               |
| All others (dataset_review, recommendations, etc.)      | ~1500 words | Full copilot identity, all sections.                                                                  |

#### 6. Model Routing by Intent & Complexity (`services/llm/models.py`)

Three model pools with 9 models across 3 tiers, selected per intent:

| Pool                   | Models                                                                                                                                                              | Timeout          | Used For                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ---------------------------------------- |
| **Fast** (tier 1)      | `openai/gpt-oss-20b:free`, `google/gemma-4-26b-a4b-it:free`, `poolside/laguna-xs-2.1:free`                                                                          | 8s               | Simple lookups, definitions              |
| **Medium** (tiers 1-2) | Fast models + `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `nvidia/nemotron-3-nano-30b-a3b:free`                                                           | 8s               | Reconciliation, comparisons, trends      |
| **Full** (tiers 1-3)   | Medium models + `nvidia/nemotron-nano-9b-v2:free`, `google/gemma-4-31b-it:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`, `nvidia/nemotron-3-super-120b-a12b:free` | 8s/15s/25s tiers | Dataset review, reports, recommendations |

Intent-to-pool mapping:

| Intent                                                              | Pool      | Rationale                          |
| ------------------------------------------------------------------- | --------- | ---------------------------------- |
| INVOICE_LOOKUP, ANOMALY_LOOKUP                                      | Fast only | Data retrieval + short explanation |
| RECONCILIATION_ANALYSIS, COMPARISON, TREND_ANALYSIS                 | Medium    | Cross-referencing needed           |
| FINANCIAL_ANALYSIS, DATASET_REVIEW, REPORT_SUMMARY, RECOMMENDATIONS | Full      | Complex synthesis required         |

#### 7. Entity-Level Database Caching (`services/database.py`)

Separate from the LLM response cache:

- **Cache scope**: Database objects (invoices, anomalies, transactions, reconciliations)
- **Cache key**: `(entity_type, entity_id)` — e.g., `("invoice", "INV00020")`
- **TTL**: 30 seconds (fresh enough for follow-up questions)
- **Thread-safe**: Uses `Lock` for concurrent access
- **Cached functions**: `get_invoice()`, `get_anomaly()`, `get_invoice_transactions()`, `get_invoice_reconciliation()`

Repeated lookups of the same entity (e.g., user asking follow-ups) skip the database entirely.

#### 8. Model Fallback & Health

The LLM manager (`manager.py`) supports:

- **3-tier fallback**: Each tier tries models in order. If all models in a tier fail, the next tier is attempted.
- **Cooldown logic**: Models with 3+ consecutive failures are put in cooldown (60s for rate limits, 120s for other errors).
- **Health endpoint**: `GET /copilot/health/models` returns per-model latency, success rate, and cooldown status.

#### 9. Response Caching

LLM responses are cached by prompt hash + intent + max_tokens with a 5-minute TTL. Cache hits skip both database queries and LLM calls.

#### 10. Context Budget Management (`services/context_budget.py`)

Prevents context overflow by calculating token budgets before every LLM call:

- **Model-aware**: Uses per-model context limits (e.g., 8K for Gemma, 32K for Nemotron, 128K for GPT-4o)
- **Intent-aware minimum output**: Ensures enough room for complete responses:

| Intent(s)                        | Min Output Tokens |
| -------------------------------- | ----------------- |
| invoice_lookup, anomaly_lookup   | 300               |
| reconciliation_analysis          | 500               |
| report_summary                   | 600               |
| dataset_review                   | 800               |
| financial_analysis               | 600               |
| general_knowledge, financial_gen | 400               |

- **Safety margin**: Uses 80% of model context limit by default
- **Output reservation**: Reserves 25% of context for model output
- **Validation**: Raises `ContextOverflowError` if estimated input tokens exceed budget
- **Diagnostics**: Logs detailed prompt breakdown (system tokens, context tokens, user tokens, utilization %)

#### 11. Context Formatting & Token Optimization (`services/context_formatter.py`)

Sits between database retrieval and prompt construction to trim verbose records:

- **Key-field extraction**: Only essential fields are retained per record type:

| Record Type    | Retained Fields                                                                            |
| -------------- | ------------------------------------------------------------------------------------------ |
| Invoice        | invoice_id, amount, due_date, payment_status, vendor_name, description, issue, severity    |
| Transaction    | transaction_id, amount, transaction_date, type, status, description                        |
| Anomaly        | anomaly_id, invoice_id, anomaly_type, severity, status, amount, description, detected_date |
| Reconciliation | reconciliation_id, invoice_id, erp_amount, bank_amount, difference, status, match_status   |

- **Query-type budgets**: Broad/general questions get ~1500 tokens, specific investigations get ~3000 tokens, dataset reviews get ~4000 tokens
- **Token estimation**: Uses `estimate_context_tokens()` for rough character-to-token ratio

#### 12. Token Counter (`services/token_counter.py`)

Accurate token estimation using tiktoken with fallback:

- **Primary**: Uses `tiktoken` with `cl100k_base` encoding for accurate counts
- **Fallback**: Character-based estimation (`len(text) // 4`) when tiktoken is unavailable
- **Model context limits**: Built-in database of context limits for 20+ models (Gemma, Nemotron, GPT, Claude, Qwen, Mistral, etc.)
- **Functions**: `count_tokens()`, `count_messages_tokens()`, `estimate_prompt_tokens()`, `get_model_context_limit()`

#### 13. Continuation & Interruption Handling (`services/continuation_state.py`)

Tracks interrupted generations and supports "continue" requests:

- **Interruption detection**: When `finish_reason == "length"`, the generation state is preserved
- **Continue flow**: User says "continue" → system restores original context + accumulated text → model continues from where it left off
- **Overlap detection**: `_merge_with_overlap_detection()` prevents duplicate text when merging continuation chunks
- **State lifecycle**: `start_generation()` → `update_accumulated_text()` → `mark_completed()` / `mark_interrupted()` → `clear_state()`
- **API endpoints**: `POST /copilot/continuation/clear` and `POST /copilot/chat/continuation/clear` to reset state
- **Finish reasons**: COMPLETED, MAX_TOKENS, MODEL_TIMEOUT, PROVIDER_ERROR, RATE_LIMIT, NETWORK_ERROR, STOPPED_BY_USER

#### 14. Conversation State Management (`services/conversation_state.py`)

Per-session state tracking for pronoun resolution and follow-up context:

- **Tracked fields**: active_intent, active_entity (type + id), last_analysis_type, last_tool_used, last_response_status, previous_intent
- **Thread-safe**: Uses `RLock` for concurrent access
- **Usage**: When user asks "tell me more about it", the system resolves "it" to the last active entity

#### 15. Benchmark System (`services/benchmark/`)

A dedicated model benchmarking subsystem for comparing LLM performance:

- **Isolation**: Tests each model individually without fallback logic
- **Metrics measured**: Response time (ms), Time to First Token (TTFT), prompt/completion/total tokens, tokens/second
- **Automated rankings**:

| Ranking                | Description                                                                       |
| ---------------------- | --------------------------------------------------------------------------------- |
| Fastest Model          | Lowest total response time                                                        |
| Best Latency Model     | Lowest Time to First Token (TTFT)                                                 |
| Most Efficient Model   | Lowest total token usage among successful responses                               |
| Most Reliable Model    | Highest success rate (all attempts successful)                                    |
| Recommended Production | Weighted score: 25% latency + 15% tokens + 10% speed + 20% TTFT + 30% reliability |

- **API endpoint**: `POST /copilot/benchmark` accepts question + model list + optional intent override
- **Frontend UI**: Angular benchmark component with model selection, sortable results table, Chart.js visualizations, CSV/JSON export, and plain-text report generation

### API Endpoints

| Method | Path                               | Description                                 |
| ------ | ---------------------------------- | ------------------------------------------- |
| POST   | `/copilot/chat`                    | Non-streaming answer with metadata          |
| POST   | `/copilot/chat/stream`             | Server-Sent Events stream                   |
| POST   | `/copilot/benchmark`               | Multi-model benchmark comparison            |
| POST   | `/copilot/continuation/clear`      | Clear continuation state for a session      |
| POST   | `/copilot/chat/continuation/clear` | Clear continuation state (alternative path) |
| GET    | `/copilot/health/models`           | Model pool health and labels                |
| GET    | `/copilot/models/health`           | Per-model health summary                    |

### API Examples

#### Non-streaming request

```http
POST /copilot/chat
Content-Type: application/json

{
  "question": "Why did reconciliation fail for invoice INV00042?"
}
```

Response:

```json
{
  "question": "Why did reconciliation fail for invoice INV00042?",
  "answer": "...",
  "model": "openai/gpt-oss-20b:free",
  "tier": 1,
  "fallback_used": false,
  "response_time": 1.42,
  "intent": "RECONCILIATION_ANALYSIS",
  "database_used": true,
  "cache_used": false,
  "pool": "Financial Analysis Pool",
  "provider": "database",
  "time_to_first_token_ms": 0,
  "request_id": "9AF31B2C"
}
```

#### Streaming request

```http
POST /copilot/chat/stream
Content-Type: application/json

{ "question": "Summarize this month's anomalies" }
```

Streamed SSE frames:

```text
data: {"type":"status","message":"Loading dataset summary..."}
data: {"type":"status","message":"Computing statistics..."}
data: {"type":"status","message":"Preparing overview..."}
data: {"type":"token","content":"Based"}
data: {"type":"token","content":" on the"}
...
data: {"type":"done","model":"...","tier":1,"fallback_used":false,"response_time":1.2,"intent":"DATASET_REVIEW","database_used":true,"cache_used":false,"pool":"...","request_id":"9AF31B2C"}
```

#### Direct-answer query (no LLM)

```http
POST /copilot/chat
Content-Type: application/json

{ "question": "How many anomalies exist?" }
```

Response (milliseconds, no LLM call):

```json
{
  "question": "How many anomalies exist?",
  "answer": "There are **954** anomalies detected.",
  "model": "direct-query",
  "response_time": 0.015,
  "intent": "FINANCIAL_ANALYSIS",
  "pool": "Direct Query Pool",
  "provider": "database",
  "request_id": "3C7D91F4"
}
```

### SSE Event Types

| Event                                                            | Description                         |
| ---------------------------------------------------------------- | ----------------------------------- |
| `{"type":"status","message":"..."}`                              | Progress status before LLM starts   |
| `{"type":"token","content":"..."}`                               | Streamed text chunk                 |
| `{"type":"metadata","model":"...","time_to_first_token_ms":...}` | Time-to-first-token info            |
| `{"type":"warning","message":"..."}`                             | Truncation or other warning         |
| `{"type":"done",...}`                                            | Final metadata with full metrics    |
| `{"type":"error","message":"...","request_id":"..."}`            | Error with request ID for debugging |

### Backend Setup

#### 1. Create and activate a virtual environment

Windows PowerShell example:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

#### 3. Configure environment variables

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

#### 4. Run the API

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

### Frontend Setup

#### 1. Install dependencies

From `frontend/`:

```powershell
npm install
```

#### 2. Configure the API URL

The API base URL is set in `frontend/src/environments/environment.ts`:

```ts
export const environment = {
  production: false,
  apiUrl: "http://127.0.0.1:8000",
};
```

Update this if your backend runs on a different host/port. CORS on the backend only allows `localhost` / `127.0.0.1:4200`, so keep the dev server on the default port.

#### 3. Run the dev server

From `frontend/`:

```powershell
npm start
```

The app is served at `http://localhost:4200/` and proxies chat requests to the backend on port `8000`.

#### 4. Build

```powershell
npm run build
```

Output is written to `frontend/dist/`.

### Data Pipeline

#### Generate synthetic datasets

From project root:

```powershell
python scripts/generate_data.py
```

This generates/overwrites CSV files under:

- `datasets/erp/erp_transactions.csv`
- `datasets/bank/bank_transactions.csv`
- `datasets/reconciliations/reconciliation_results.csv`
- `datasets/reconciliations/anomalies.csv`

#### Import datasets to Supabase

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

## Recent Performance Optimizations

| Optimization                     | Impact            | Details                                                           |
| -------------------------------- | ----------------- | ----------------------------------------------------------------- |
| Structured latency logging       | Debugging         | Per-stage timing with request IDs                                 |
| Context budget management        | Reliability       | Prevents context overflow with model-aware token budgets          |
| Context formatting & trimming    | Token efficiency  | Key-field extraction reduces context size by 40-60%               |
| Intent-aware SSE status events   | Perceived latency | Users see progress before LLM starts                              |
| Intent-specific system prompts   | TTFT reduction    | ~400 words for lookups vs ~1500 for full                          |
| Model routing by intent          | Latency + cost    | Simple lookups use fast models only; 3-tier fallback              |
| Entity-level caching             | DB latency        | 30s TTL eliminates repeated DB hits                               |
| Direct SQL responses             | Latency           | Simple count queries skip LLM entirely (<15ms)                    |
| Per-intent token limits          | Token efficiency  | 384 tokens for definitions, 3000 for reviews                      |
| Continuation & overlap detection | Response quality  | "Continue" requests resume from interruptions without duplication |
| tiktoken-based token estimation  | Accuracy          | Precise token counting vs character-based fallback (~4x better)   |
| Response caching (5-min TTL)     | Latency           | Identical queries skip both DB and LLM calls                      |

## Not Yet Implemented

- Other frontend routes (Dashboard, Transactions, Reconciliation, Reports, Settings) are sidebar placeholders only.
- Production-grade semantic retrieval (embeddings/search/ranking) — current retrieval is rule + intent based.
- Async database client (current Supabase client is synchronous).
- Project documentation in `docs/` (folder exists but empty).
- Full CI/CD pipeline with automated tests.
- A committed `.env.example` template (backend `.env` exists locally for secrets).
- Model quality scoring tied to benchmark evaluations (quality scores are user-rated, not automated).
- Documentation for the Supabase schema and migration workflow.

## Suggested Next Milestones

1. Implement the remaining frontend routes (Dashboard, Transactions, Reconciliation, Reports, Settings).
2. Add `.env.example` and onboarding notes for secrets.
3. Add unit/integration tests for routes, services, and the financial rule engine.
4. Upgrade retrieval to semantic search (embeddings) with ranking across all financial tables.
5. Migrate database layer to async Supabase client for true parallel query execution.
6. Add docs for the Supabase schema and a deployment workflow.
