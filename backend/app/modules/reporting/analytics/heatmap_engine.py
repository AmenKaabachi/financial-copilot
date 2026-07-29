from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client


def _table(table: str):
    return get_supabase_client().table(table)


def get_heatmap_data(
    date_field: str = "created_at",
    severity_field: str = "severity",
) -> Dict[str, Any]:
    """Get heatmap data from anomalies table using direct DB query."""
    try:
        result = _table("anomalies").select("*").execute()
        anomalies = result.data or []

        severity_counts: Dict[str, Dict[str, int]] = {}
        date_labels: set = set()

        for item in anomalies:
            date_val = str(item.get(date_field, ""))
            severity = str(item.get(severity_field, "unknown"))

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

        # Calculate anomaly statistics from the full dataset
        severity_dist: Dict[str, int] = {}
        type_dist: Dict[str, int] = {}
        for item in anomalies:
            sev = str(item.get("severity", "UNKNOWN")).upper()
            typ = str(item.get("anomaly_type", "UNKNOWN")).upper()
            severity_dist[sev] = severity_dist.get(sev, 0) + 1
            type_dist[typ] = type_dist.get(typ, 0) + 1

        return {
            "dates": dates,
            "severities": severity_types,
            "matrix": matrix,
            "total_anomalies": len(anomalies),
            "high_severity_count": severity_dist.get("HIGH", 0),
            "severity_distribution": severity_dist,
            "type_distribution": type_dist,
        }
    except Exception as exc:
        return {"dates": [], "severities": [], "matrix": [], "total_anomalies": 0, "high_severity_count": 0}