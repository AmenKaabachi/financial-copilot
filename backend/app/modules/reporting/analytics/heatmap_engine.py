from typing import Any, Dict, List, Optional

from app.shared.database.retrieval import retrieve_context
from app.shared.analytics import calculate_anomaly_statistics


def get_heatmap_data(
    anomalies: Optional[List[Dict[str, Any]]] = None,
    date_field: str = "created_at",
    severity_field: str = "severity",
) -> Dict[str, Any]:
    if anomalies is None:
        anomalies = retrieve_context("financial_analysis", "", {}).get("high_severity_anomalies", [])

    severity_counts: Dict[str, Dict[str, int]] = {}
    date_labels: set = set()

    for item in anomalies:
        date_val = item.get(date_field, "")
        severity = item.get(severity_field, "unknown")

        if len(date_val) >= 7:
            period = date_val[:7]
        elif len(date_val) >= 4:
            period = date_val[:4]
        else:
            period = "unknown"

        date_labels.add(period)
        if period not in severity_counts:
            severity_counts[period] = {}
        severity_counts[period][severity] = severity_counts[period].get(severity, 0) + 1

    severity_types = sorted(
        {sev for periods in severity_counts.values() for sev in periods}
    )
    dates = sorted(date_labels)

    matrix = []
    for date in dates:
        row = []
        for sev in severity_types:
            row.append(severity_counts.get(date, {}).get(sev, 0))
        matrix.append(row)

    stats = calculate_anomaly_statistics(anomalies)

    return {
        "dates": dates,
        "severities": severity_types,
        "matrix": matrix,
        "total_anomalies": stats.get("total", 0) if isinstance(stats, dict) else 0,
        "high_severity_count": stats.get("high_severity", 0) if isinstance(stats, dict) else 0,
    }