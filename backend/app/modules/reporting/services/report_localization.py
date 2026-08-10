"""Report Localization - Central source of truth for report labels across languages.

Provides localized labels for all human-readable content rendered in PDF reports:
KPI labels, section titles, financial summary headings, table headers, chart titles,
and fallback content. Supported languages: en, fr, ar.

This ensures the preferred language controls the ENTIRE report, not just AI
narrative text.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Language normalization map
_LANG_MAP = {
    "en": "en",
    "english": "en",
    "fr": "fr",
    "french": "fr",
    "ar": "ar",
    "arabic": "ar",
}

# Field-level labels (invoice keys, supplier, status, etc.)
_FIELD_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "invoice_id": "Invoice ID",
        "supplier": "Supplier",
        "invoice_date": "Invoice Date",
        "due_date": "Due Date",
        "amount": "Amount",
        "currency": "Currency",
        "status": "Status",
        "reconciliation_id": "Reconciliation ID",
        "matched_date": "Matched Date",
        "anomaly_id": "Anomaly ID",
        "type": "Type",
        "severity": "Severity",
        "detected_at": "Detected At",
        "expense_id": "Expense ID",
        "category": "Category",
        "vendor": "Vendor",
        "date": "Date",
        "id": "ID",
        "created_at": "Created At",
        "updated_at": "Updated At",
    },
    "fr": {
        "invoice_id": "N° Facture",
        "supplier": "Fournisseur",
        "invoice_date": "Date Facture",
        "due_date": "Date Échéance",
        "amount": "Montant",
        "currency": "Devise",
        "status": "Statut",
        "reconciliation_id": "N° Rapprochement",
        "matched_date": "Date Rapprochée",
        "anomaly_id": "N° Anomalie",
        "type": "Type",
        "severity": "Sévérité",
        "detected_at": "Détecté À",
        "expense_id": "N° Dépense",
        "category": "Catégorie",
        "vendor": "Fournisseur",
        "date": "Date",
        "id": "ID",
        "created_at": "Créé À",
        "updated_at": "Mis À Jour",
    },
    "ar": {
        "invoice_id": "رقم الفاتورة",
        "supplier": "المورد",
        "invoice_date": "تاريخ الفاتورة",
        "due_date": "تاريخ الاستحقاق",
        "amount": "المبلغ",
        "currency": "العملة",
        "status": "الحالة",
        "reconciliation_id": "رقم المطابقة",
        "matched_date": "تاريخ المطابقة",
        "anomaly_id": "رقم الشذوذ",
        "type": "النوع",
        "severity": "الخطورة",
        "detected_at": "تاريخ الاكتشاف",
        "expense_id": "رقم المصروف",
        "category": "الفئة",
        "vendor": "المورد",
        "date": "التاريخ",
        "id": "المعرف",
        "created_at": "تاريخ الإنشاء",
        "updated_at": "تاريخ التحديث",
    },
}

# KPI labels (canonical analytics keys)
_KPI_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "total_revenue": "Total Revenue",
        "collected_revenue": "Collected Revenue",
        "outstanding_revenue": "Outstanding Revenue",
        "invoice_count": "Total Invoices",
        "paid_invoice_count": "Paid Invoices",
        "unpaid_invoice_count": "Unpaid Invoices",
        "total_expenses": "Total Expenses",
        "expense_count": "Expense Count",
        "net_cash_result": "Net Cash Result",
        "cash_margin": "Cash Margin",
        "total_inflows": "Total Inflows",
        "total_outflows": "Total Outflows",
        "net_cash_flow": "Net Cash Flow",
        "outstanding_count": "Outstanding Count",
        "total_outstanding": "Total Outstanding",
        "average_outstanding": "Average Outstanding",
        "delayed_count": "Delayed Count",
        "total_delayed_amount": "Total Delayed Amount",
        "reconciliation_rate": "Reconciliation Rate",
        "total_invoices": "Total Invoices",
        "reconciled_count": "Reconciled Count",
        "unreconciled_count": "Unreconciled Count",
        "erp_count": "ERP Count",
        "bank_count": "Bank Count",
        "total_count": "Total Count",
        "erp_volume": "ERP Volume",
        "bank_volume": "Bank Volume",
        "total_volume": "Total Volume",
        "total_anomalies": "Total Anomalies",
        "high_severity_count": "High Severity",
        "medium_severity_count": "Medium Severity",
        "low_severity_count": "Low Severity",
        "matching_accuracy": "Matching Accuracy",
        "total_reconciliations": "Total Reconciliations",
        "matched_count": "Matched Count",
        "unmatched_count": "Unmatched Count",
        "pending_count": "Pending Count",
        "partial_count": "Partial Count",
        "net_profit": "Net Profit",
        "profit_margin": "Profit Margin",
        "accuracy_rate": "Accuracy Rate",
    },
    "fr": {
        "total_revenue": "Revenu Total",
        "collected_revenue": "Revenu Encaissé",
        "outstanding_revenue": "Revenu En Attente",
        "invoice_count": "Total Factures",
        "paid_invoice_count": "Factures Payées",
        "unpaid_invoice_count": "Factures Impayées",
        "total_expenses": "Dépenses Totales",
        "expense_count": "Nombre de Dépenses",
        "net_cash_result": "Résultat Net de Trésorerie",
        "cash_margin": "Marge de Trésorerie",
        "total_inflows": "Entrées Totales",
        "total_outflows": "Sorties Totales",
        "net_cash_flow": "Flux de Trésorerie Net",
        "outstanding_count": "Nombre d'Impayés",
        "total_outstanding": "Total Impayé",
        "average_outstanding": "Impayé Moyen",
        "delayed_count": "Nombre de Retards",
        "total_delayed_amount": "Montant Total des Retards",
        "reconciliation_rate": "Taux de Rapprochement",
        "total_invoices": "Total Factures",
        "reconciled_count": "Nombre Rapproché",
        "unreconciled_count": "Nombre Non Rapproché",
        "erp_count": "Nombre ERP",
        "bank_count": "Nombre Banque",
        "total_count": "Nombre Total",
        "erp_volume": "Volume ERP",
        "bank_volume": "Volume Banque",
        "total_volume": "Volume Total",
        "total_anomalies": "Total Anomalies",
        "high_severity_count": "Sévérité Élevée",
        "medium_severity_count": "Sévérité Moyenne",
        "low_severity_count": "Sévérité Faible",
        "matching_accuracy": "Précision de Correspondance",
        "total_reconciliations": "Total Rapprochements",
        "matched_count": "Nombre Correspondant",
        "unmatched_count": "Nombre Non Correspondant",
        "pending_count": "Nombre En Attente",
        "partial_count": "Nombre Partiel",
        "net_profit": "Bénéfice Net",
        "profit_margin": "Marge Bénéficiaire",
        "accuracy_rate": "Taux de Précision",
    },
    "ar": {
        "total_revenue": "إجمالي الإيرادات",
        "collected_revenue": "الإيرادات المحصّلة",
        "outstanding_revenue": "الإيرادات المستحقة",
        "invoice_count": "إجمالي الفواتير",
        "paid_invoice_count": "الفواتير المدفوعة",
        "unpaid_invoice_count": "الفواتير غير المدفوعة",
        "total_expenses": "إجمالي المصروفات",
        "expense_count": "عدد المصروفات",
        "net_cash_result": "صافي النتيجة النقدية",
        "cash_margin": "هامش النقدية",
        "total_inflows": "إجمالي التدفقات الداخلة",
        "total_outflows": "إجمالي التدفقات الخارجة",
        "net_cash_flow": "صافي التدفق النقدي",
        "outstanding_count": "عدد المستحقات",
        "total_outstanding": "إجمالي المستحقات",
        "average_outstanding": "متوسط المستحقات",
        "delayed_count": "عدد المؤجلات",
        "total_delayed_amount": "إجمالي المبلغ المؤجل",
        "reconciliation_rate": "معدل المطابقة",
        "total_invoices": "إجمالي الفواتير",
        "reconciled_count": "عدد المطابَق",
        "unreconciled_count": "عدد غير المطابَق",
        "erp_count": "عدد ERP",
        "bank_count": "عدد البنك",
        "total_count": "العدد الإجمالي",
        "erp_volume": "حجم ERP",
        "bank_volume": "حجم البنك",
        "total_volume": "الحجم الإجمالي",
        "total_anomalies": "إجمالي الحالات الشاذة",
        "high_severity_count": "خطورة عالية",
        "medium_severity_count": "خطورة متوسطة",
        "low_severity_count": "خطورة منخفضة",
        "matching_accuracy": "دقة المطابقة",
        "total_reconciliations": "إجمالي المطابقات",
        "matched_count": "عدد المتطابق",
        "unmatched_count": "عدد غير المتطابق",
        "pending_count": "عدد معلق",
        "partial_count": "عدد جزئي",
        "net_profit": "صافي الربح",
        "profit_margin": "هامش الربح",
        "accuracy_rate": "معدل الدقة",
    },
}

# Section/summary label keys
_SUMMARY_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "reporting_period": "Reporting Period",
        "recommendations": "Recommendations",
        "ai_insights": "AI Insights",
        "ai_unavailable": "AI insight is temporarily unavailable.",
        "revenue_summary": "Revenue Summary",
        "expenses_summary": "Expenses Summary",
        "cash_flow_summary": "Cash Flow Summary",
        "reconciliation_summary": "Reconciliation Summary",
        "metric": "Metric",
        "value": "Value",
        "no_data": "No data available for this table.",
        "showing_records": "Showing {shown} of {total} records",
        "executive_overview": "Executive Overview",
        "kpis": "Key Performance Indicators",
        "trends": "Performance Trends",
        "transactions": "Transaction Overview",
        "risk": "Risk Assessment & Analysis",
        "strategic_recommendations": "Strategic Recommendations",
        "financial_insights": "Financial Insights",
        "ai_financial_insights": "AI Financial Insights",
        "no_sections": "No sections in this report.",
        "financial_data_unavailable": "Financial data unavailable.",
    },
    "fr": {
        "reporting_period": "Période couverte",
        "recommendations": "Recommandations",
        "ai_insights": "Analyses IA",
        "ai_unavailable": "L'analyse IA est temporairement indisponible.",
        "revenue_summary": "Synthèse des Revenus",
        "expenses_summary": "Synthèse des Dépenses",
        "cash_flow_summary": "Synthèse des Flux de Trésorerie",
        "reconciliation_summary": "Synthèse du Rapprochement",
        "metric": "Indicateur",
        "value": "Valeur",
        "no_data": "Aucune donnée disponible pour ce tableau.",
        "showing_records": "Affichage de {shown} sur {total} enregistrements",
        "executive_overview": "Vue d'ensemble exécutive",
        "kpis": "Indicateurs clés de performance",
        "trends": "Tendances de performance",
        "transactions": "Aperçu des transactions",
        "risk": "Évaluation des risques",
        "strategic_recommendations": "Recommandations stratégiques",
        "financial_insights": "Analyses financières",
        "ai_financial_insights": "Analyses financières IA",
        "no_sections": "Aucune section dans ce rapport.",
        "financial_data_unavailable": "Données financières indisponibles.",
    },
    "ar": {
        "reporting_period": "الفترة المشمولة بالتقرير",
        "recommendations": "التوصيات",
        "ai_insights": "رؤى الذكاء الاصطناعي",
        "ai_unavailable": "تحليل الذكاء الاصطناعي غير متاح مؤقتًا.",
        "revenue_summary": "ملخص الإيرادات",
        "expenses_summary": "ملخص المصروفات",
        "cash_flow_summary": "ملخص التدفق النقدي",
        "reconciliation_summary": "ملخص المطابقة",
        "metric": "المؤشر",
        "value": "القيمة",
        "no_data": "لا توجد بيانات متاحة لهذا الجدول.",
        "showing_records": "عرض {shown} من {total} سجلاً",
        "executive_overview": "نظرة تنفيذية عامة",
        "kpis": "مؤشرات الأداء الرئيسية",
        "trends": "اتجاهات الأداء",
        "transactions": "نظرة عامة على المعاملات",
        "risk": "تقييم المخاطر",
        "strategic_recommendations": "توصيات استراتيجية",
        "financial_insights": "التحليلات المالية",
        "ai_financial_insights": "تحليلات الذكاء الاصطناعي المالية",
        "no_sections": "لا توجد أقسام في هذا التقرير.",
        "financial_data_unavailable": "البيانات المالية غير متاحة.",
    },
}

# Chart dataset labels (line/bar legends)
_CHART_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "successful": "Successful",
        "failed": "Failed",
        "transaction_volume": "Transaction Volume",
        "erp_volume": "ERP Volume",
        "bank_volume": "Bank Volume",
        "paid": "Paid",
        "outstanding": "Outstanding",
        "anomaly_types": "Anomaly Types",
    },
    "fr": {
        "successful": "Réussi",
        "failed": "Échoué",
        "transaction_volume": "Volume des Transactions",
        "erp_volume": "Volume ERP",
        "bank_volume": "Volume Banque",
        "paid": "Payé",
        "outstanding": "Impayé",
        "anomaly_types": "Types d'Anomalies",
    },
    "ar": {
        "successful": "ناجح",
        "failed": "فاشل",
        "transaction_volume": "حجم المعاملات",
        "erp_volume": "حجم ERP",
        "bank_volume": "حجم البنك",
        "paid": "مدفوع",
        "outstanding": "مستحق",
        "anomaly_types": "أنواع الحالات الشاذة",
    },
}

# Fallback content (used when LLM generation fails)
_FALLBACK_CONTENT: Dict[str, Dict[str, str]] = {
    "en": {
        "exec_intro": "This report provides a concise financial analysis and management-oriented overview.",
        "text_section": "This report section provides executive analysis and financial commentary for the evaluated period.",
        "recommendations": ["Review reconciliation automation rules to increase automatic matching rate.", "Investigate high-severity transaction anomalies promptly.", "Monitor cash flow forecasts and manage outstanding unpaid invoices.", "Perform weekly bank statement reconciliations to reduce month-end lag."],
    },
    "fr": {
        "exec_intro": "Ce rapport fournit une analyse financière concise et une vue d'ensemble orientée gestion.",
        "text_section": "Cette section du rapport fournit une analyse exécutive et des commentaires financiers pour la période évaluée.",
        "recommendations": ["Révisez les règles d'automatisation du rapprochement pour augmenter le taux de correspondance automatique.", "Enquêtez rapidement sur les anomalies de transaction à haute sévérité.", "Surveillez les prévisions de trésorerie et gérez les factures impayées.", "Effectuez des rapprochements bancaires hebdomadaires pour réduire le décalage de fin de mois."],
    },
    "ar": {
        "exec_intro": "يوفر هذا التقرير تحليلاً مالياً موجزاً ونظرة عامة موجهة للإدارة.",
        "text_section": "توفر هذه الصفحة من التقرير تحليلاً تنفيذياً وتعليقات مالية للفترة التي تمت مراجعتها.",
        "recommendations": ["راجع قواعد أتمتة المطابقة لزيادة معدل المطابقة التلقائية.", "حقق بسرعة في حالات الشذوذ المالية عالية الخطورة.", "راقب توقعات التدفق النقدي وأدر الفواتير غير المدفوعة.", "قم بإجراء مطابقة بنكية أسبوعية لتقليل تأخر نهاية الشهر."],
    },
}


def normalize_language(language: Optional[str]) -> str:
    """Normalize a language value to a short code (en/fr/ar)."""
    if not language:
        return "en"
    return _LANG_MAP.get(str(language).strip().lower(), "en")


class ReportLocalization:
    """Static localization helper for report labels."""

    @staticmethod
    def normalize_language(language: Optional[str]) -> str:
        return normalize_language(language)

    @staticmethod
    def field_label(key: str, language: Optional[str] = "en") -> str:
        """Get the localized label for a table/data field key."""
        lang = normalize_language(language)
        return _FIELD_LABELS.get(lang, _FIELD_LABELS["en"]).get(key, key.replace("_", " ").title())

    @staticmethod
    def kpi_label(key: str, language: Optional[str] = "en") -> str:
        """Get the localized label for a KPI key."""
        lang = normalize_language(language)
        return _KPI_LABELS.get(lang, _KPI_LABELS["en"]).get(key, key.replace("_", " ").title())

    @staticmethod
    def summary_label(key: str, language: Optional[str] = "en") -> str:
        """Get a localized summary/section label."""
        lang = normalize_language(language)
        return _SUMMARY_LABELS.get(lang, _SUMMARY_LABELS["en"]).get(key, key.replace("_", " ").title())

    @staticmethod
    def chart_label(key: str, language: Optional[str] = "en") -> str:
        """Get a localized chart dataset label."""
        lang = normalize_language(language)
        return _CHART_LABELS.get(lang, _CHART_LABELS["en"]).get(key, key.replace("_", " ").title())

    @staticmethod
    def showing_records(shown: int, total: int, language: Optional[str] = "en") -> str:
        """Localized 'Showing X of Y records' string."""
        lang = normalize_language(language)
        template = _SUMMARY_LABELS.get(lang, _SUMMARY_LABELS["en"]).get("showing_records", "Showing {shown} of {total} records")
        return template.format(shown=shown, total=total)

    @staticmethod
    def fallback_text(key: str, language: Optional[str] = "en") -> str:
        """Get a localized fallback content string."""
        lang = normalize_language(language)
        return _FALLBACK_CONTENT.get(lang, _FALLBACK_CONTENT["en"]).get(key, "")

    @staticmethod
    def fallback_recommendations(language: Optional[str] = "en") -> list:
        """Get localized fallback recommendation list."""
        lang = normalize_language(language)
        return _FALLBACK_CONTENT.get(lang, _FALLBACK_CONTENT["en"]).get("recommendations", [])

    @staticmethod
    def translate_title(title: str, language: Optional[str] = "en") -> str:
        """Translate a known English title key to the target language.

        Only translates known section titles; returns the title unchanged
        if it's not a known key (e.g. user-supplied custom titles).
        """
        lang = normalize_language(language)
        return _SUMMARY_LABELS.get(lang, _SUMMARY_LABELS["en"]).get(title, title)