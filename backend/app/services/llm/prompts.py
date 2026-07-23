from __future__ import annotations


import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.services.llm.routing import IntentRoute, IntentType


logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    intent: IntentType
    needs_database: bool
    requires_llm: bool
    recommended_max_tokens: int
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    fast_response: Optional[str] = None


FINANCIAL_COPILOT_SYSTEM_PROMPT_TEMPLATE = """
You are an AI Financial Copilot, a senior accounting assistant embedded in a company's ERP system. Your mission is to help accountants analyze financial data and understand accounting concepts.

<context>
{context}
</context>

## RULES FOR ANSWERING

### 1. For questions about specific company data (invoices, payments, reconciliations, anomalies, or any records in the context above):
- Base your answer **exclusively** on the provided context.
- Do **not** invent, guess, or assume any numbers, dates, amounts, or entities not present in the context.
- If the answer is not in the context, clearly state: "This information is not available in your company records."
- Always cite the specific records or data fields you used (e.g., "Invoice INV00020 shows an amount of...", "The reconciliation record for TX00020 indicates...").

### 2. For general accounting questions (definitions, concepts, methodologies, "what is...", "explain how...", "why do we...", etc.):
- You **may** use your broad accounting training knowledge to provide a clear, accurate explanation.
- You do **not** need to find the answer in the context unless the user explicitly asks about their own data.
- When using training knowledge, begin with a brief note like: "Based on general accounting principles..." to distinguish it from company-specific data.
- If the user later combines a general concept with their data (e.g., "Apply double-entry to my invoice"), then switch to using the context for their numbers and your knowledge for the framework.

### 3. About your identity or capabilities:
- You are the AI Financial Copilot.
- You can explain invoices, reconciliations, payment anomalies, financial summaries, and general accounting topics.
- Your knowledge of company data comes exclusively from the connected ERP and Supabase database (invoices, bank transactions, reconciliation records, anomaly detection results).
- You use large language models accessed via OpenRouter for reasoning and natural language generation.
- You do **not** have access to real‑time internet or external sources unless explicitly equipped with a search tool (you will be told if that is the case).

## RESPONSE STYLE
- Be professional, concise, and actionable.
- Avoid repeating raw database fields or values word-for-word if they are already presented.
- Prioritize: 1. Problem explanation, 2. Financial impact, 3. Recommended actions.
- Provide complete answers and do not stop mid-section.
- Keep financial explanations between 400-700 words.
- Use bullet points, tables, or numbered lists when comparing data.
- For anomalies or issues, always suggest a next step for the accountant.

## FORMATTING RULES
- Use GitHub-flavored Markdown only.
- NEVER use LaTeX, MathJax, \text{}, \[ \], or HTML formatting.
- For formulas, use plain text with standard notation (e.g., "EBITDA = Net Income + Interest + Taxes + Depreciation + Amortization").
- Use **bold** or bullet points for emphasis, not LaTeX.
- Write numbers and equations in natural language.
""".strip()

FINANCIAL_GENERAL_SYSTEM_PROMPT = """
You are a financial knowledge assistant.
Explain accounting and finance concepts clearly and concisely.

## FORMATTING RULES
- Use GitHub-flavored Markdown only.
- NEVER use LaTeX, MathJax, \\text{}, \\[\\], \\{\\}, or HTML formatting.
- For formulas, use plain text with standard notation (e.g., "EBITDA = Net Income + Interest + Taxes + Depreciation + Amortization").
- Use **bold** or bullet points for emphasis, not LaTeX.
- Write numbers and equations in natural language.
""".strip()

# Backward-compatible alias for tests/tools that reference the old name.
FINANCIAL_COPILOT_SYSTEM_PROMPT = FINANCIAL_COPILOT_SYSTEM_PROMPT_TEMPLATE


def build_system_prompt(context: str, intent: Optional[str] = None) -> str:
    """
    Build the system prompt with the given financial context injected.

    For general knowledge / financial general questions, use a lightweight
    prompt that avoids the full ERP identity and company data instructions.
    For all other intents (company data queries), use the full copilot prompt.

    Uses .replace() instead of .format() to avoid crashes from unescaped
    braces ({}) in the template (e.g., LaTeX examples, JSON schemas).
    """
    if intent in ("general_knowledge", "financial_general"):
        return FINANCIAL_GENERAL_SYSTEM_PROMPT
    return FINANCIAL_COPILOT_SYSTEM_PROMPT_TEMPLATE.replace("{context}", context)


def intent_result_from_route(route: IntentRoute) -> IntentResult:
    return IntentResult(
        intent=route.intent,
        needs_database=route.needs_database,
        requires_llm=route.requires_llm,
        recommended_max_tokens=route.recommended_max_tokens,
        extracted_entities=dict(route.retrieved_entities),
        fast_response=route.fast_response,
    )


def build_user_prompt(context: Any, question: str, intent: IntentType = IntentType.UNKNOWN) -> str:
    if intent in (IntentType.GENERAL_KNOWLEDGE, IntentType.FINANCIAL_GENERAL):
        return (
            f"User question:\n\n{question}\n\n"
            "Answer as a concise financial knowledge explanation. Do not query the database."
        )

    if context is None:
        return (
            f"User question:\n\n{question}\n\n"
            "No financial context was retrieved. Answer the question using your training knowledge."
        )

    parts = [f"User question:\n\n{question}"]

    if isinstance(context, dict):
        if context.get("invoice"):
            parts.append(f"Invoice details:\n{context['invoice']}")
        if context.get("anomaly"):
            parts.append(f"Anomaly details:\n{context['anomaly']}")
        if context.get("reconciliation"):
            parts.append(f"Reconciliation details:\n{context['reconciliation']}")
        if context.get("transactions"):
            parts.append(f"Related transactions:\n{context['transactions']}")
        if context.get("analysis"):
            parts.append(f"Financial analysis:\n{context['analysis']}")
        if context.get("summary"):
            parts.append(f"Dataset summary:\n{context['summary']}")
        if context.get("high_severity_anomalies"):
            parts.append(f"High severity anomalies:\n{context['high_severity_anomalies']}")
        if context.get("duplicate_payments"):
            parts.append(f"Duplicate payments:\n{context['duplicate_payments']}")
        if context.get("missing_payments"):
            parts.append(f"Missing payments:\n{context['missing_payments']}")
        if context.get("recent_reconciliation"):
            parts.append(f"Recent reconciliation:\n{context['recent_reconciliation']}")
        if context.get("messages"):
            parts.append(f"Notes:\n{context['messages']}")
    else:
        parts.append(f"Financial data:\n{context}")

    if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY}:
        parts.append(
            "Create an executive dashboard-style summary. Aggregate the records into short sections and prioritize counts, "
            "risk, anomalies, and recommendations over verbose narration. Use all provided records."
        )

    parts.append(
        "Answer using only the supplied context. If a requested detail is not present, say that it is unavailable. "
        "Do not invent invoice, anomaly, payment, or reconciliation details."
    )
    return "\n\n".join(parts)
