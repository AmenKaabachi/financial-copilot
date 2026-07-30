"""
Component Registry — Single source of truth for all available analytics components.

This registry defines every analytics widget, KPI, chart, table, and insight
that can be consumed by:
  - Analytics Workspace (visual dashboard)
  - Manual Report Builder (drag-and-drop palette)
  - AI Report Generator (intelligent component selection)
  - Preview endpoints (live data rendering)

Each component includes AI metadata (use_cases, keywords) to enable
intent-based selection by the AI report generator.
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Synonyms for better AI matching
# ---------------------------------------------------------------------------
SYNONYMS = {
    "revenue": [
        "income",
        "sales",
        "turnover"
    ],
    "outstanding": [
        "unpaid",
        "receivable",
        "due",
        "pending"
    ],
    "anomaly": [
        "risk",
        "fraud",
        "suspicious"
    ],
    "profit": [
        "earnings",
        "net income",
        "bottom line"
    ],
    "expenses": [
        "costs",
        "spending",
        "outflows",
        "expenditure"
    ],
    "reconciliation": [
        "matching",
        "reconciling",
        "bank rec"
    ],
    "cash_flow": [
        "liquidity",
        "cash movement",
        "money flow"
    ],
}

# ---------------------------------------------------------------------------
# KPI Components
# ---------------------------------------------------------------------------
KPI_COMPONENTS = [
    {
        "id": "kpi_revenue",
        "name": "Revenue KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "revenue"},
        "description": "Total revenue with paid invoice count and outstanding revenue",
        "component_group": "kpis",
        "icon": "💰",
        "use_cases": [
            "revenue analysis",
            "financial performance",
            "sales overview",
            "monthly finance review",
        ],
        "keywords": ["revenue", "income", "sales", "paid invoices", "outstanding"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_expenses",
        "name": "Expenses KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "expenses"},
        "description": "Total expenses with expense count",
        "component_group": "kpis",
        "icon": "💸",
        "use_cases": ["expense analysis", "cost overview", "financial performance"],
        "keywords": ["expenses", "costs", "spending", "outflows"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_profit",
        "name": "Profit KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "profit"},
        "description": "Net profit with profit margin percentage",
        "component_group": "kpis",
        "icon": "📈",
        "use_cases": ["profitability analysis", "financial performance", "executive summary"],
        "keywords": ["profit", "margin", "net income", "profitability"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_cash_flow",
        "name": "Cash Flow KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "cash_flow"},
        "description": "Net cash flow with inflow and outflow breakdown",
        "component_group": "kpis",
        "icon": "💵",
        "use_cases": ["cash flow analysis", "liquidity review", "financial health"],
        "keywords": ["cash flow", "liquidity", "inflows", "outflows"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_outstanding_invoices",
        "name": "Outstanding Invoices KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "outstanding_invoices"},
        "description": "Outstanding invoice count and total amount",
        "component_group": "kpis",
        "icon": "📋",
        "use_cases": ["accounts receivable", "payment collection", "aging analysis"],
        "keywords": ["outstanding", "unpaid", "receivable", "due"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_payment_delays",
        "name": "Payment Delays KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "payment_delays"},
        "description": "Delayed payment count and total delayed amount",
        "component_group": "kpis",
        "icon": "⏰",
        "use_cases": ["payment delay analysis", "late payment investigation", "risk assessment"],
        "keywords": ["delays", "late", "overdue", "payment delay"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_reconciliation_rate",
        "name": "Reconciliation Rate KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "reconciliation_rate"},
        "description": "Reconciliation success rate with matched/unmatched counts",
        "component_group": "kpis",
        "icon": "🔄",
        "use_cases": ["reconciliation analysis", "matching performance", "monthly finance review"],
        "keywords": ["reconciliation", "matching", "reconciled", "unreconciled"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_total_transactions",
        "name": "Transaction Summary KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "total_transactions"},
        "description": "ERP and bank transaction counts with total volume",
        "component_group": "kpis",
        "icon": "📦",
        "use_cases": ["transaction overview", "volume analysis", "data completeness check"],
        "keywords": ["transactions", "volume", "erp", "bank"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_anomaly_stats",
        "name": "Anomaly Stats KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "anomaly_stats"},
        "description": "Total anomalies with severity and type distribution",
        "component_group": "kpis",
        "icon": "⚠️",
        "use_cases": ["anomaly detection", "risk analysis", "fraud investigation"],
        "keywords": ["anomalies", "anomaly", "suspicious", "irregularities"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "kpi_matching_accuracy",
        "name": "Matching Accuracy KPI",
        "type": "kpi",
        "analytics_source": "kpi",
        "analytics_params": {"kpi_key": "matching_accuracy"},
        "description": "Detailed reconciliation matching accuracy statistics",
        "component_group": "kpis",
        "icon": "🎯",
        "use_cases": ["reconciliation accuracy", "matching quality", "process improvement"],
        "keywords": ["accuracy", "matching", "precision", "quality"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
]

# ---------------------------------------------------------------------------
# Chart Components
# ---------------------------------------------------------------------------
CHART_COMPONENTS = [
    {
        "id": "chart_reconciliation_trend",
        "name": "Reconciliation Trend",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "reconciliation_trend"},
        "description": "Shows successful and failed reconciliations over time (line chart)",
        "component_group": "charts",
        "icon": "📊",
        "use_cases": ["reconciliation analysis", "failure investigation", "monthly finance review", "trend analysis"],
        "keywords": ["matching", "failed reconciliation", "bank reconciliation", "reconciliation trend"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "bucket": {"type": "string", "default": "month", "description": "Time bucket"},
        },
    },
    {
        "id": "chart_transaction_volume",
        "name": "Transaction Volume",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "transaction_volume"},
        "description": "Monthly transaction amounts (bar chart)",
        "component_group": "charts",
        "icon": "📊",
        "use_cases": ["volume analysis", "financial trends", "monthly review"],
        "keywords": ["volume", "transactions", "monthly volume"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "bucket": {"type": "string", "default": "month", "description": "Time bucket"},
        },
    },
    {
        "id": "chart_anomaly_distribution",
        "name": "Anomaly Distribution",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "anomaly_distribution"},
        "description": "Anomalies by severity level (donut chart)",
        "component_group": "charts",
        "icon": "🍩",
        "use_cases": ["anomaly analysis", "risk assessment", "severity breakdown"],
        "keywords": ["anomaly distribution", "severity", "risk levels"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "chart_anomaly_type",
        "name": "Anomaly Types",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "anomaly_type"},
        "description": "Anomalies by type category (bar chart)",
        "component_group": "charts",
        "icon": "📊",
        "use_cases": ["anomaly investigation", "type analysis", "fraud detection"],
        "keywords": ["anomaly types", "categories", "classification"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
    {
        "id": "chart_bank_vs_erp",
        "name": "Bank vs ERP Comparison",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "bank_vs_erp"},
        "description": "Side-by-side volume comparison of bank and ERP transactions (grouped bar)",
        "component_group": "charts",
        "icon": "📊",
        "use_cases": ["reconciliation analysis", "data comparison", "discrepancy detection"],
        "keywords": ["bank vs erp", "comparison", "discrepancy", "mismatch"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "bucket": {"type": "string", "default": "month", "description": "Time bucket"},
        },
    },
    {
        "id": "chart_payment_status",
        "name": "Payment Status",
        "type": "chart",
        "analytics_source": "chart_data",
        "analytics_params": {"chart_type": "payment_status"},
        "description": "Paid vs outstanding invoice distribution (pie chart)",
        "component_group": "charts",
        "icon": "🥧",
        "use_cases": ["payment analysis", "collection status", "accounts receivable"],
        "keywords": ["payment status", "paid", "outstanding", "collection"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
        },
    },
]

# ---------------------------------------------------------------------------
# Table Components
# ---------------------------------------------------------------------------
TABLE_COMPONENTS = [
    {
        "id": "table_reconciliations",
        "name": "Reconciliation Records",
        "type": "table",
        "analytics_source": "table_data",
        "analytics_params": {"data_source": "reconciliations"},
        "description": "Detailed reconciliation records with status and amounts",
        "component_group": "tables",
        "icon": "📋",
        "use_cases": ["reconciliation review", "detailed matching analysis", "audit"],
        "keywords": ["reconciliation records", "matching details", "audit trail"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "limit": {"type": "number", "default": 50, "description": "Max records"},
        },
    },
    {
        "id": "table_anomalies",
        "name": "Anomaly Records",
        "type": "table",
        "analytics_source": "table_data",
        "analytics_params": {"data_source": "anomalies"},
        "description": "Anomaly records with severity, type, and amounts",
        "component_group": "tables",
        "icon": "📋",
        "use_cases": ["anomaly investigation", "fraud review", "risk analysis"],
        "keywords": ["anomaly records", "suspicious transactions", "investigation"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "limit": {"type": "number", "default": 50, "description": "Max records"},
        },
    },
    {
        "id": "table_transactions",
        "name": "ERP Transactions",
        "type": "table",
        "analytics_source": "table_data",
        "analytics_params": {"data_source": "erp_transactions"},
        "description": "ERP transaction records with supplier and status details",
        "component_group": "tables",
        "icon": "📋",
        "use_cases": ["transaction review", "supplier analysis", "data audit"],
        "keywords": ["transactions", "erp records", "supplier transactions"],
        "config_schema": {
            "date_from": {"type": "string?", "description": "Start date filter"},
            "date_to": {"type": "string?", "description": "End date filter"},
            "limit": {"type": "number", "default": 50, "description": "Max records"},
        },
    },
]

# ---------------------------------------------------------------------------
# Analytics Widget Components
# ---------------------------------------------------------------------------
ANALYTICS_WIDGET_COMPONENTS = [
    {
        "id": "heatmap_anomalies",
        "name": "Anomaly Heatmap",
        "type": "heatmap",
        "analytics_source": "heatmap",
        "analytics_params": {},
        "description": "Anomaly severity heatmap over time showing patterns",
        "component_group": "analytics_widgets",
        "icon": "🗺️",
        "use_cases": ["anomaly pattern analysis", "temporal analysis", "risk visualization"],
        "keywords": ["heatmap", "anomaly patterns", "severity over time"],
        "config_schema": {},
    },
    {
        "id": "pivot_transactions",
        "name": "Transaction Pivot Table",
        "type": "pivot",
        "analytics_source": "pivot",
        "analytics_params": {},
        "description": "Interactive pivot table for transaction analysis by category and period",
        "component_group": "analytics_widgets",
        "icon": "📊",
        "use_cases": ["cross-tabulation analysis", "category comparison", "detailed breakdown"],
        "keywords": ["pivot", "cross tab", "breakdown", "by category"],
        "config_schema": {
            "row_field": {"type": "string", "default": "category", "description": "Row dimension"},
            "column_field": {"type": "string", "default": "month", "description": "Column dimension"},
            "value_field": {"type": "string", "default": "amount", "description": "Value metric"},
        },
    },
    {
        "id": "trend_analysis",
        "name": "Financial Trends",
        "type": "trend",
        "analytics_source": "trend",
        "analytics_params": {},
        "description": "Time-bucketed financial trend series with period-over-period comparison",
        "component_group": "analytics_widgets",
        "icon": "📈",
        "use_cases": ["trend analysis", "period comparison", "growth analysis"],
        "keywords": ["trends", "growth", "period comparison", "over time"],
        "config_schema": {
            "metric": {"type": "string", "default": "amount", "description": "Metric to trend"},
            "bucket": {"type": "string", "default": "month", "description": "Time bucket"},
        },
    },
]

# ---------------------------------------------------------------------------
# Master Registry
# ---------------------------------------------------------------------------
ALL_COMPONENTS: List[Dict[str, Any]] = (
    KPI_COMPONENTS + CHART_COMPONENTS + TABLE_COMPONENTS + ANALYTICS_WIDGET_COMPONENTS
)

COMPONENT_INDEX: Dict[str, Dict[str, Any]] = {
    comp["id"]: comp for comp in ALL_COMPONENTS
}


def get_all_components() -> List[Dict[str, Any]]:
    """Return all registered analytics components."""
    return ALL_COMPONENTS


def get_component_by_id(component_id: str) -> Optional[Dict[str, Any]]:
    """Look up a single component by its ID."""
    return COMPONENT_INDEX.get(component_id)


def get_components_by_group(group: str) -> List[Dict[str, Any]]:
    """Return all components in a specific group."""
    return [c for c in ALL_COMPONENTS if c["component_group"] == group]


def get_components_by_type(comp_type: str) -> List[Dict[str, Any]]:
    """Return all components of a specific type."""
    return [c for c in ALL_COMPONENTS if c["type"] == comp_type]


def _expand_synonyms(keywords: List[str]) -> List[str]:
    """
    Expand a list of keywords by adding synonyms from the SYNONYMS dictionary.
    """
    expanded = list(keywords)
    for kw in keywords:
        kw_lower = kw.lower()
        for key, syn_list in SYNONYMS.items():
            if kw_lower == key.lower() or kw_lower in [s.lower() for s in syn_list]:
                # Add all synonyms for this key
                for syn in syn_list:
                    if syn.lower() not in [e.lower() for e in expanded]:
                        expanded.append(syn)
                # Add the main key if not present
                if key.lower() not in [e.lower() for e in expanded]:
                    expanded.append(key)
                break
    return expanded


def select_components_for_prompt(prompt: str) -> List[Dict[str, Any]]:
    """
    Select relevant components based on a user prompt using intent-based matching.
    
    Analyzes the prompt for domain, period, and goal, then maps to
    appropriate components using keywords and use_cases.
    
    Now uses synonyms for better AI matching.
    """
    prompt_lower = prompt.lower()
    
    # Score each component by keyword match count (with synonyms)
    scored: List[tuple[int, str]] = []
    for comp in ALL_COMPONENTS:
        score = 0
        
        # Get original keywords and expand with synonyms
        original_keywords = comp.get("keywords", [])
        expanded_keywords = _expand_synonyms(original_keywords)
        
        # Score using expanded keywords
        for kw in expanded_keywords:
            if kw.lower() in prompt_lower:
                score += 2
        
        # Score using use_cases (also with synonym expansion)
        for uc in comp.get("use_cases", []):
            uc_lower = uc.lower()
            # Check if use case matches prompt directly
            if uc_lower in prompt_lower:
                score += 1
            # Check if any word in use case is a synonym match
            uc_words = uc_lower.split()
            for word in uc_words:
                if word in prompt_lower:
                    score += 1
        
        # Score by name words
        name_words = comp["name"].lower().split()
        for word in name_words:
            if word in prompt_lower:
                score += 1
            # Check if name word has synonyms
            for key, syn_list in SYNONYMS.items():
                if word == key.lower() or word in [s.lower() for s in syn_list]:
                    # Boost score if synonym matches
                    score += 1
                    break
        
        if score > 0:
            scored.append((score, comp["id"]))
    
    # Sort by score (highest first) to maintain ranking
    scored.sort(key=lambda x: -x[0])
    
    # Build result list maintaining order
    selected_ids: List[str] = []
    for score, cid in scored:
        if score >= 3 and cid not in selected_ids:
            selected_ids.append(cid)
    if len(selected_ids) < 3:
        for score, cid in scored:
            if score >= 2 and cid not in selected_ids:
                selected_ids.append(cid)
    if not selected_ids:
        # Better default for reconciliation platform
        selected_ids = [
            "kpi_revenue",
            "kpi_expenses",
            "kpi_profit",
            "kpi_cash_flow",
            "chart_reconciliation_trend",
            "chart_anomaly_distribution",
            "table_reconciliations"
        ]
    
    # Return in ranked order
    return [COMPONENT_INDEX[cid] for cid in selected_ids if cid in COMPONENT_INDEX]