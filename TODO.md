# AI Report Pipeline Fix - Task Progress

## Steps

- [x] Add `description` and `definition` fields to `AiReportPreview` interface in `reporting.models.ts`
- [x] Fix `ai-report-config.component.ts` `generateReport()` to send AI-generated title/description/definition
- [x] Fix `report_service.py` `create_ai_report()` to use definition name/description/definition
- [x] Add structured logs to `ai_report_service.py` `generate_report_definition_from_prompt`
- [x] Add test proving different prompts produce different report structures
- [x] Run tests to verify all changes pass
- [x] Fix `generate_answer()` to accept custom `system_prompt` (AI Report Architect LLM call was throwing TypeError)

## Root Cause (Primary)

AI Report Architect generation only ran during PDF export because `ai_report_service.py` called `generate_answer(system_prompt=...)` with a keyword argument that `generate_answer()` in `manager.py` did not accept. This raised `TypeError: generate_answer() got an unexpected keyword argument 'system_prompt'` immediately, triggering the heuristic fallback path (static structure, no LLM call, instant preview).

## Secondary Root Cause

Frontend dropped AI-generated `name`, `description`, and `definition` when calling `createAiReport()` — it used the hardcoded user `title` and a static description instead of `preview.title` / `preview.description` / `preview.definition`.

## Fix

Added optional `system_prompt: Optional[str] = None` parameter to `generate_answer()` in `backend/app/shared/llm/manager.py`. When not provided, it falls back to the built-in intent-based system prompt. This preserves backward compatibility with all existing callers while allowing `ai_report_service.py` to pass the custom Financial Architect system prompt.
