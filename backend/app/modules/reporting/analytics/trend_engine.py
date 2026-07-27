from typing import Any, Dict, List, Optional

from app.shared.database.retrieval import retrieve_context


def get_time_bucketed_series(
    data: Optional[List[Dict[str, Any]]] = None,
    bucket: str = "month",
    value_key: str = "amount",
    date_key: str = "date",
) -> List[Dict[str, Any]]:
    if data is None:
        data = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    buckets: Dict[str, float] = {}
    for item in data:
        date_val = item.get(date_key, "")
        if not date_val:
            continue
        bucket_key = _get_bucket_key(date_val, bucket)
        buckets[bucket_key] = buckets.get(bucket_key, 0.0) + float(item.get(value_key, 0) or 0)

    sorted_keys = sorted(buckets.keys())
    return [
        {"period": key, "value": round(buckets[key], 2)}
        for key in sorted_keys
    ]


def calculate_period_over_period(
    current_series: Optional[List[Dict[str, Any]]] = None,
    prior_series: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if current_series is None:
        current_series = []
    if prior_series is None:
        prior_series = []

    current_map = {item["period"]: item["value"] for item in current_series}
    prior_map = {item["period"]: item["value"] for item in prior_series}

    all_periods = sorted(set(list(current_map.keys()) + list(prior_map.keys())))
    result = []
    for period in all_periods:
        current_val = current_map.get(period, 0.0)
        prior_val = prior_map.get(period, 0.0)
        delta = current_val - prior_val
        pct_change = (delta / prior_val * 100) if prior_val != 0 else 0.0
        result.append({
            "period": period,
            "current": round(current_val, 2),
            "prior": round(prior_val, 2),
            "delta": round(delta, 2),
            "pct_change": round(pct_change, 2),
        })

    return result


def _get_bucket_key(date_val: str, bucket: str) -> str:
    if len(date_val) >= 7 and bucket == "month":
        return date_val[:7]
    if len(date_val) >= 4 and bucket == "year":
        return date_val[:4]
    if len(date_val) >= 10 and bucket == "day":
        return date_val[:10]
    if len(date_val) >= 7 and bucket == "quarter":
        year = date_val[:4]
        month = int(date_val[5:7])
        quarter = (month - 1) // 3 + 1
        return f"{year}-Q{quarter}"
    return date_val