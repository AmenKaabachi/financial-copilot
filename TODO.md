# Response Metadata Feature - Completed

## Backend

### 1. `backend/app/services/llm/manager.py` — `stream_answer()`

- [x] Compute TTFT in milliseconds when first token is received
- [x] Emit early `type: "metadata"` event after first token (before subsequent tokens)
- [x] Include `model`, `provider: "OpenRouter"`, `time_to_first_token_ms`
- [x] Added `provider: "OpenRouter"` to `GenerateAnswerResult` and `StreamMetadata` TypedDicts

### 2. `backend/app/services/llm/manager.py` — `generate_answer()`

- [x] Added `provider: "OpenRouter"` to the non-streaming result dict

### 3. `backend/app/routes/copilot.py` — `chat_stream` endpoint

- [x] Handle `type: "metadata"` events from stream_answer (pass through as-is)
- [x] Update `_conversational()` to include metadata and provider fields
- [x] Update `_fast_conversational_response()` to include `provider` and `time_to_first_token_ms`
- [x] Update non-streaming `/chat` response to include `provider` and `time_to_first_token_ms`

## Frontend

### 4. `frontend/src/app/core/models/copilot.models.ts`

- [x] Added `provider?`, `time_to_first_token_ms?` to `CopilotResponse`
- [x] Created `ResponseMetadata` interface for extensibility

### 5. `frontend/src/app/core/services/copilot.service.ts`

- [x] Added `'metadata'` to `CopilotStreamEvent.type` union
- [x] Added `provider?`, `time_to_first_token_ms?`, `metadata?` fields
- [x] Added `[key: string]: unknown` index signature for future fields

### 6. `frontend/src/app/features/copilot/copilot.component.ts`

- [x] Added `responseMetadata?: ResponseMetadata`, `timeToFirstTokenMs?`, `provider?` to `ChatMessage`
- [x] Handle `metadata` event type in stream subscription
- [x] Store metadata on current AI message
- [x] Ensure `responseMetadata` is populated from both metadata and done events

### 7. `frontend/src/app/features/copilot/copilot.component.html`

- [x] Replaced `.metadata-card` with compact `.response-metadata` row
- [x] Shows: Model • Provider • First token: X ms • Total: Xs • [fallback]

### 8. `frontend/src/app/features/copilot/copilot.component.css`

- [x] Styled compact metadata row (small font, subtle gradient divider, muted text)
- [x] `fallback` badge style preserved
