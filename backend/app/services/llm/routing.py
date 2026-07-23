from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict, Optional


logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    GREETING = "greeting"
    GOODBYE = "goodbye"
    THANKS = "thanks"
    SMALL_TALK = "small_talk"
    ASSISTANT_IDENTITY = "assistant_identity"
    ASSISTANT_CAPABILITIES = "assistant_capabilities"
    GENERAL_KNOWLEDGE = "general_knowledge"
    FINANCIAL_GENERAL = "financial_general"
    FINANCIAL_ANALYSIS = "financial_analysis"
    INVOICE_LOOKUP = "invoice_lookup"
    ANOMALY_LOOKUP = "anomaly_lookup"
    RECONCILIATION_ANALYSIS = "reconciliation_analysis"
    REPORT_SUMMARY = "report_summary"
    DATASET_REVIEW = "dataset_review"
    TREND_ANALYSIS = "trend_analysis"
    COMPARISON = "comparison"
    RECOMMENDATIONS = "recommendations"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentRoute:
    intent: IntentType
    requires_llm: bool
    needs_database: bool
    recommended_max_tokens: int
    fast_response: Optional[str] = None
    retrieved_entities: Dict[str, str] = field(default_factory=dict)
    direct_answer_key: Optional[str] = None  # Key into DIRECT_ANSWER_PATTERNS for SQL-only responses


GREETING_RESPONSE = (
    "Hello. I am your AI Financial Copilot. I can help you review invoices, reconciliation results, "
    "anomalies, payments, reports, comparisons, and follow-up analysis."
)

GOODBYE_RESPONSE = "Goodbye. If you need another financial review, come back anytime."
THANKS_RESPONSE = "You are welcome."
SMALL_TALK_RESPONSE = "I am here to help with financial questions, dataset review, and analysis."
ASSISTANT_IDENTITY_RESPONSE = (
    "I am the AI Financial Copilot designed to help accountants with invoice analysis, "
    "bank reconciliations, payment anomalies, and financial summaries.\n\n"
    "My knowledge comes from:\n"
    "- Your company's financial data from the connected ERP and Supabase database: invoices, bank transactions, reconciliation records, and anomaly detection results\n"
    "- Large language models accessed via OpenRouter for reasoning and natural language generation\n\n"
    "I do not have access to external real-time information. All financial answers are based solely on the data you have provided."
)
ASSISTANT_CAPABILITIES_RESPONSE = (
    "I can explain financial terms, review datasets, analyze invoices, inspect anomalies, compare ERP and "
    "bank data, summarize reconciliation results, and suggest next steps."
)

GENERAL_KNOWLEDGE_PATTERNS = (
    r"\bwhat\s+is\s+",
    r"\bdefine\b",
    r"\bexplain\b",
    r"\bmeaning\s+of\b",
)

FINANCIAL_TERM_PATTERNS = (
    r"\breconciliation\b",
    r"\berp\b",
    r"\binvoice\s+matching\b",
    r"\bocr\b",
    r"\baccounts?\s+payable\b",
    r"\bduplicate\s+payment\b",
    r"\bbank\s+reconciliation\b",
)

GREETING_PATTERNS = (
    r"^hi\b",
    r"^hello\b",
    r"^hey\b",
    r"^good\s*(morning|afternoon|evening|day)\b",
)

GOODBYE_PATTERNS = (
    r"\bbye\b",
    r"\bgoodbye\b",
    r"\bsee\s+you\b",
    r"\blater\b",
)

THANKS_PATTERNS = (
    r"^thanks?\b",
    r"^thank\s+you\b",
    r"\bappreciate\b",
)

SMALL_TALK_PATTERNS = (
    r"\bhow\s+are\s+you\b",
    r"\bhow\s+is\s+it\s+going\b",
    r"\bhow\s+are\s+things\b",
)

IDENTITY_PATTERNS = (
    r"\bwho\s+are\s+you\b",
    r"\bwhat\s+do\s+you\s+know\b",
    r"\bwhere\s+do\s+you\s+get\s+your\s+knowledge\b",
    r"\bwhat\s+do\s+you\s+get\s+your\s+knowledge\b",
    r"\bwhere\s+does\s+your\s+knowledge\s+come\s+from\b",
    r"\bwhat\s+is\s+your\s+knowledge\s+source\b",
    r"\bwhat\s+is\s+your\s+name\b",
    r"\byour\s+name\b",
    r"\btell\s+me\s+about\s+yourself\b",
    r"\bwho\s+created\s+you\b",
    r"\bwho\s+built\s+you\b",
)

CAPABILITY_PATTERNS = (
    r"\bwhat\s+can\s+you\s+do\b",
    r"\bhow\s+can\s+you\s+help\b",
    r"\bwhat\s+are\s+your\s+capabilities\b",
)

INVOICE_PATTERNS = (
    r"\binvoice\b",
    r"\binvoices\b",
    r"\bINV\d{4,8}\b",
)

ANOMALY_PATTERNS = (
    r"\banomaly\b",
    r"\banomalies\b",
    r"\bmissing\s+payment\b",
    r"\bduplicate\s+payment\b",
    r"\blate\s+payment\b",
    r"\bamount\s+mismatch\b",
)

RECONCILIATION_PATTERNS = (
    r"\breconcil",
    r"\bmismatch\b",
    r"\bmatching\b",
)

REVIEW_PATTERNS = (
    r"\breview\b",
    r"\boverview\b",
    r"\banalyze\b",
    r"\banalyse\b",
    r"\bsummarize\b",
    r"\bsummarise\b",
    r"\bdataset\b",
    r"\bdata\b",
    r"\brecords?\b",
)

DATASET_REVIEW_PATTERNS = (
    r"\breview\s+my\s+data\b",
    r"\breview\s+the\s+database\b",
    r"\bwhat\s+do\s+you\s+think\s+about\s+my\s+data\b",
    r"\bgive\s+me\s+an\s+overview\b",
    r"\bsummarize\s+my\s+financial\s+records\b",
    r"\bwhat\s+anomal(?:y|ies)\s+exist\b",
    r"\banalyze\s+the\s+dataset\b",
    r"\banalyze\s+my\s+data\b",
    r"\breview\s+the\s+dataset\b",
)

# Direct-answer patterns — simple factual questions that can be answered
# with a SQL query, skipping the LLM entirely.
# Each pattern maps to a (intent, response_template) where the template
# uses {count} or similar placeholders.
DIRECT_ANSWER_PATTERNS = {
    r"\bhow\s+many\s+invoices?\s+(?:are\s+there|exist|do\s+we\s+have)\b": ("count_invoices", "There are **{count}** invoices in the system."),
    r"\bhow\s+many\s+transactions?\s+(?:are\s+there|exist|do\s+we\s+have)\b": ("count_transactions", "There are **{count}** bank transactions recorded."),
    r"\bhow\s+many\s+anomal(?:y|ies)\s+(?:are\s+there|exist|do\s+we\s+have)\b": ("count_anomalies", "There are **{count}** anomalies detected."),
    r"\btotal\s+(?:number\s+of\s+)?invoices?\b": ("count_invoices", "There are **{count}** invoices in total."),
    r"\btotal\s+(?:number\s+of\s+)?anomal(?:y|ies)\b": ("count_anomalies", "There are **{count}** anomalies in total."),
    r"\bhow\s+many\s+high\s+severity\s+anomal(?:y|ies)\b": ("count_high_severity", "There are **{count}** high-severity anomalies."),
    r"\bhow\s+many\s+duplicate\s+payments?\b": ("count_duplicate", "There are **{count}** duplicate payments identified."),
    r"\bhow\s+many\s+missing\s+payments?\b": ("count_missing", "There are **{count}** missing payments to investigate."),
    r"\b(reconciliation|reconciliations?)\s+(?:count|total|number)\b": ("count_reconciliations", "There are **{count}** reconciliation records."),
}

TREND_PATTERNS = (
    r"\btrend\b",
    r"\bover\s+time\b",
    r"\bmonthly\b",
    r"\bweekly\b",
    r"\bgrowth\b",
    r"\bpattern\b",
)

COMPARISON_PATTERNS = (
    r"\bcompare\b",
    r"\bdifference\s+between\b",
    r"\bvs\b",
    r"\bversus\b",
)

RECOMMENDATION_PATTERNS = (
    r"\brecommend\b",
    r"\bsuggest\b",
    r"\bwhat\s+should\s+i\s+do\b",
    r"\bnext\s+step\b",
)

ENTITY_INVOICE_RE = re.compile(r"\b(INV\d{4,8})\b", re.IGNORECASE)
ENTITY_TRANSACTION_RE = re.compile(r"\b(TX\d{4,8})\b", re.IGNORECASE)
ENTITY_ANOMALY_RE = re.compile(r"\b(ANM\d{4,8})\b", re.IGNORECASE)
ENTITY_REPORT_RE = re.compile(r"\b(report|summary|review)\b", re.IGNORECASE)
PRONOUN_RE = re.compile(r"\b(it|this|that|them|those|these)\b", re.IGNORECASE)


class ConversationMemory:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state: Dict[str, Optional[str]] = {
            "last_invoice": None,
            "last_transaction": None,
            "last_anomaly": None,
            "last_report": None,
            "last_entity": None,
        }

    def snapshot(self) -> Dict[str, Optional[str]]:
        with self._lock:
            return dict(self._state)

    def update(self, entities: Dict[str, str], intent: IntentType) -> None:
        with self._lock:
            if entity := entities.get("invoice_id"):
                self._state["last_invoice"] = entity
                self._state["last_entity"] = entity
            if entity := entities.get("transaction_id"):
                self._state["last_transaction"] = entity
                self._state["last_entity"] = entity
            if entity := entities.get("anomaly_id"):
                self._state["last_anomaly"] = entity
                self._state["last_entity"] = entity
            if entity := entities.get("report_id"):
                self._state["last_report"] = entity
                self._state["last_entity"] = entity
            if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY}:
                self._state["last_report"] = intent.value

    def resolve_reference(self, message: str, entities: Dict[str, str]) -> Dict[str, str]:
        if entities.get("invoice_id") or entities.get("transaction_id") or entities.get("anomaly_id") or entities.get("report_id"):
            return entities

        if not PRONOUN_RE.search(message):
            return entities

        state = self.snapshot()
        resolved = dict(entities)
        if state.get("last_invoice"):
            resolved.setdefault("invoice_id", state["last_invoice"])
        if state.get("last_transaction"):
            resolved.setdefault("transaction_id", state["last_transaction"])
        if state.get("last_anomaly"):
            resolved.setdefault("anomaly_id", state["last_anomaly"])
        if state.get("last_report"):
            resolved.setdefault("report_id", state["last_report"])
        if state.get("last_entity"):
            resolved.setdefault("last_entity", state["last_entity"])
        return resolved


class ConversationMemoryRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memories: Dict[str, ConversationMemory] = {}

    def get(self, session_id: str = "default") -> ConversationMemory:
        normalized_session_id = session_id or "default"
        with self._lock:
            if normalized_session_id not in self._memories:
                self._memories[normalized_session_id] = ConversationMemory()
            return self._memories[normalized_session_id]


conversation_memory_registry = ConversationMemoryRegistry()
conversation_memory = conversation_memory_registry.get()


def get_conversation_memory(session_id: str = "default") -> ConversationMemory:
    return conversation_memory_registry.get(session_id)


class IntentClassifier:
    def classify(self, message: str, session_id: str = "default") -> IntentRoute:
        message_clean = message.strip()
        tokens = _tokenize(message_clean)
        entities: Dict[str, str] = {}
        memory = get_conversation_memory(session_id)

        invoice_match = ENTITY_INVOICE_RE.search(message_clean)
        transaction_match = ENTITY_TRANSACTION_RE.search(message_clean)
        anomaly_match = ENTITY_ANOMALY_RE.search(message_clean)
        report_match = ENTITY_REPORT_RE.search(message_clean)

        if invoice_match:
            entities["invoice_id"] = invoice_match.group(1).upper()
        if transaction_match:
            entities["transaction_id"] = transaction_match.group(1).upper()
        if anomaly_match:
            entities["anomaly_id"] = anomaly_match.group(1).upper()
        if report_match and any(word in tokens for word in ("report", "summary", "review")):
            entities["report_id"] = report_match.group(1).lower()

        entities = memory.resolve_reference(message_clean, entities)

        if entities.get("invoice_id"):
            memory.update(entities, IntentType.INVOICE_LOOKUP)
        elif entities.get("transaction_id"):
            memory.update(entities, IntentType.INVOICE_LOOKUP)
        elif entities.get("anomaly_id"):
            memory.update(entities, IntentType.ANOMALY_LOOKUP)
        elif entities.get("report_id"):
            memory.update(entities, IntentType.REPORT_SUMMARY)

        if entities.get("invoice_id") or entities.get("transaction_id"):
            base_score = _regex_score(message_clean, INVOICE_PATTERNS)
            if base_score == 0:
                if entities.get("invoice_id"):
                    return IntentRoute(IntentType.INVOICE_LOOKUP, True, True, 450, retrieved_entities=entities)
                if entities.get("transaction_id"):
                    return IntentRoute(IntentType.INVOICE_LOOKUP, True, True, 450, retrieved_entities=entities)

        scores = {
            IntentType.GREETING: _regex_score(message_clean, GREETING_PATTERNS) + _keyword_score(tokens, ("hi", "hello", "hey")),
            IntentType.GOODBYE: _regex_score(message_clean, GOODBYE_PATTERNS),
            IntentType.THANKS: _regex_score(message_clean, THANKS_PATTERNS) + _keyword_score(tokens, ("thanks", "thank", "appreciate")),
            IntentType.SMALL_TALK: _regex_score(message_clean, SMALL_TALK_PATTERNS),
            IntentType.ASSISTANT_IDENTITY: _regex_score(message_clean, IDENTITY_PATTERNS),
            IntentType.ASSISTANT_CAPABILITIES: _regex_score(message_clean, CAPABILITY_PATTERNS),
            IntentType.FINANCIAL_GENERAL: _regex_score(message_clean, GENERAL_KNOWLEDGE_PATTERNS) + _regex_score(message_clean, FINANCIAL_TERM_PATTERNS),
            IntentType.INVOICE_LOOKUP: _regex_score(message_clean, INVOICE_PATTERNS) + _keyword_score(tokens, ("invoice", "invoices", "paid", "missing", "status", "transaction")),
            IntentType.ANOMALY_LOOKUP: _regex_score(message_clean, ANOMALY_PATTERNS) + _keyword_score(tokens, ("anomaly", "anomalies", "missing", "duplicate", "late", "severity")),
            IntentType.RECONCILIATION_ANALYSIS: _regex_score(message_clean, RECONCILIATION_PATTERNS) + _keyword_score(tokens, ("reconciliation", "matching", "mismatch", "reconcile", "reconciliation_analysis", "results")),
            IntentType.REPORT_SUMMARY: _regex_score(message_clean, REVIEW_PATTERNS) + _keyword_score(tokens, ("report", "summary", "overview")),
            IntentType.DATASET_REVIEW: _regex_score(message_clean, REVIEW_PATTERNS) + _regex_score(message_clean, DATASET_REVIEW_PATTERNS) + _keyword_score(tokens, ("review", "dataset", "database", "data", "records", "overview", "anomalies", "anomaly", "payments", "reconciliation")),
            IntentType.TREND_ANALYSIS: _regex_score(message_clean, TREND_PATTERNS) + _keyword_score(tokens, ("trend", "over", "time", "monthly", "weekly", "growth")),
            IntentType.COMPARISON: _regex_score(message_clean, COMPARISON_PATTERNS) + _keyword_score(tokens, ("compare", "difference", "erp", "bank", "versus", "vs")),
            IntentType.RECOMMENDATIONS: _regex_score(message_clean, RECOMMENDATION_PATTERNS) + _keyword_score(tokens, ("recommend", "suggest", "should", "next", "step")),
            IntentType.FINANCIAL_ANALYSIS: _keyword_score(tokens, ("why", "analyze", "investigate", "explain", "missing", "high", "severity", "issue")),
            IntentType.GENERAL_KNOWLEDGE: _regex_score(message_clean, GENERAL_KNOWLEDGE_PATTERNS),
        }

        # Check for direct-answer patterns first (simple factual queries that skip LLM entirely)
        for pattern, (answer_key, _) in DIRECT_ANSWER_PATTERNS.items():
            if re.search(pattern, message_clean, re.IGNORECASE):
                return IntentRoute(
                    intent=IntentType.FINANCIAL_ANALYSIS,
                    requires_llm=False,
                    needs_database=True,
                    recommended_max_tokens=0,
                    retrieved_entities=entities,
                    direct_answer_key=answer_key,
                )

        if not message_clean:
            return IntentRoute(
                intent=IntentType.UNKNOWN,
                requires_llm=False,
                needs_database=False,
                recommended_max_tokens=0,
                fast_response="Please ask a question.",
                retrieved_entities=entities,
            )

        if scores[IntentType.GREETING] > 0:
            return IntentRoute(IntentType.GREETING, False, False, 0, GREETING_RESPONSE, entities)
        if scores[IntentType.GOODBYE] > 0:
            return IntentRoute(IntentType.GOODBYE, False, False, 0, GOODBYE_RESPONSE, entities)
        if scores[IntentType.THANKS] > 0:
            return IntentRoute(IntentType.THANKS, False, False, 0, THANKS_RESPONSE, entities)
        if scores[IntentType.SMALL_TALK] > 0:
            return IntentRoute(IntentType.SMALL_TALK, False, False, 0, SMALL_TALK_RESPONSE, entities)
        if scores[IntentType.ASSISTANT_IDENTITY] > 0:
            return IntentRoute(IntentType.ASSISTANT_IDENTITY, False, False, 0, ASSISTANT_IDENTITY_RESPONSE, entities)
        if scores[IntentType.ASSISTANT_CAPABILITIES] > 0:
            return IntentRoute(IntentType.ASSISTANT_CAPABILITIES, False, False, 0, ASSISTANT_CAPABILITIES_RESPONSE, entities)

        if scores[IntentType.DATASET_REVIEW] >= 5:
            return IntentRoute(IntentType.DATASET_REVIEW, True, True, 3000, retrieved_entities=entities)
        if scores[IntentType.INVOICE_LOOKUP] >= 2:
            return IntentRoute(IntentType.INVOICE_LOOKUP, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.ANOMALY_LOOKUP] >= 2:
            return IntentRoute(IntentType.ANOMALY_LOOKUP, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.RECONCILIATION_ANALYSIS] >= 2:
            return IntentRoute(IntentType.RECONCILIATION_ANALYSIS, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.REPORT_SUMMARY] >= 3:
            return IntentRoute(IntentType.REPORT_SUMMARY, True, True, 900, retrieved_entities=entities)
        if scores[IntentType.TREND_ANALYSIS] >= 2:
            return IntentRoute(IntentType.TREND_ANALYSIS, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.COMPARISON] >= 2:
            return IntentRoute(IntentType.COMPARISON, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.RECOMMENDATIONS] >= 2:
            return IntentRoute(IntentType.RECOMMENDATIONS, True, True, 800, retrieved_entities=entities)
        if scores[IntentType.FINANCIAL_GENERAL] >= 2:
            return IntentRoute(IntentType.FINANCIAL_GENERAL, True, False, 700, retrieved_entities=entities)
        if scores[IntentType.GENERAL_KNOWLEDGE] >= 2:
            return IntentRoute(IntentType.GENERAL_KNOWLEDGE, True, False, 384, retrieved_entities=entities)

        if entities.get("invoice_id"):
            return IntentRoute(IntentType.INVOICE_LOOKUP, True, True, 800, retrieved_entities=entities)
        if entities.get("transaction_id"):
            return IntentRoute(IntentType.INVOICE_LOOKUP, True, True, 800, retrieved_entities=entities)
        if entities.get("anomaly_id"):
            return IntentRoute(IntentType.ANOMALY_LOOKUP, True, True, 800, retrieved_entities=entities)
        if entities.get("report_id"):
            return IntentRoute(IntentType.REPORT_SUMMARY, True, True, 900, retrieved_entities=entities)

        return IntentRoute(IntentType.FINANCIAL_ANALYSIS, True, True, 900, retrieved_entities=entities)


def _regex_score(message: str, patterns: tuple[str, ...]) -> int:
    score = 0
    for pattern in patterns:
        if re.search(pattern, message, re.IGNORECASE):
            score += 2
    return score


def _keyword_score(tokens: Counter[str], keywords: tuple[str, ...]) -> int:
    score = 0
    for keyword in keywords:
        if tokens[keyword] > 0:
            score += tokens[keyword]
    return score


def _tokenize(message: str) -> Counter[str]:
    tokens = re.findall(r"[a-z0-9_]+", message.lower())
    return Counter(tokens)
