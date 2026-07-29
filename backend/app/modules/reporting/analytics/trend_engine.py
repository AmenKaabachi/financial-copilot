from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client


def _table(table: str):
    return get_supabase_client().table(table)


def _apply_date_filter(query, date_field: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Apply optional date range filter to a query."""
    if date_from:
        query = query.gte(date_field, date_from)
    if date_to:
        query = query.lte(date_field, date_to)
    return query


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


def get_time_bucketed_series(
    bucket: str = "month",
    value_key: str = "amount",
    date_key: str = "date",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get time-bucketed trend series from erp_transactions with optional date filtering."""
    try:
        query = _table("erp_transactions").select("invoice_date, amount")
        query = _apply_date_filter(query, "invoice_date", date_from, date_to)
        result = query.execute()
        data = result.data or []

        buckets: Dict[str, float] = {}
        for item in data:
            date_val = item.get("invoice_date", "")
            if not date_val:
                continue
            bucket_key = _get_bucket_key(str(date_val), bucket)
            value = float(item.get(value_key, 0) or 0)
            buckets[bucket_key] = buckets.get(bucket_key, 0.0) + value

        sorted_keys = sorted(buckets.keys())
        return [
            {"period": key, "value": round(buckets[key], 2)}
            for key in sorted_keys
        ]
    except Exception as exc:
        return []


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


def get_reconciliation_trend(
    bucket: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get monthly reconciliation success/failure trend from reconciliations table."""
    try:
        query = _table("reconciliations").select("created_at, status")
        query = _apply_date_filter(query, "created_at", date_from, date_to)
        result = query.execute()
        data = result.data or []

        success_buckets: Dict[str, int] = {}
        failure_buckets: Dict[str, int] = {}
        all_periods: set = set()

        for item in data:
            date_val = str(item.get("created_at", ""))
            if not date_val:
                continue
            period = _get_bucket_key(date_val, bucket)
            all_periods.add(period)
            status = str(item.get("status", "")).upper()
            if status == "MATCHED":
                success_buckets[period] = success_buckets.get(period, 0) + 1
            else:
                failure_buckets[period] = failure_buckets.get(period, 0) + 1

        sorted_periods = sorted(all_periods)
        return [
            {
                "period": p,
                "successful": success_buckets.get(p, 0),
                "failed": failure_buckets.get(p, 0),
                "total": success_buckets.get(p, 0) + failure_buckets.get(p, 0),
            }
            for p in sorted_periods
        ]
    except Exception as exc:
        return []


def get_anomaly_trend(
    bucket: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get monthly anomaly counts trend from anomalies table."""
    try:
        query = _table("anomalies").select("created_at, severity")
        query = _apply_date_filter(query, "created_at", date_from, date_to)
        result = query.execute()
        data = result.data or []

        buckets: Dict[str, int] = {}
        high_sev_buckets: Dict[str, int] = {}
        all_periods: set = set()

        for item in data:
            date_val = str(item.get("created_at", ""))
            if not date_val:
                continue
            period = _get_bucket_key(date_val, bucket)
            all_periods.add(period)
            buckets[period] = buckets.get(period, 0) + 1
            severity = str(item.get("severity", "")).upper()
            if severity == "HIGH":
                high_sev_buckets[period] = high_sev_buckets.get(period, 0) + 1

        sorted_periods = sorted(all_periods)
        return [
            {
                "period": p,
                "total": buckets.get(p, 0),
                "high_severity": high_sev_buckets.get(p, 0),
            }
            for p in sorted_periods
        ]
    except Exception as exc:
        return []


def get_bank_vs_erp_trend(
    bucket: str = "month",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get monthly comparison of bank_transactions vs erp_transactions volumes."""
    try:
        print(f"[BANK_VS_ERP] Fetching with bucket={bucket}, date_from={date_from}, date_to={date_to}")
        
        # ERP transactions
        erp_query = _table("erp_transactions").select("invoice_date, amount")
        erp_query = _apply_date_filter(erp_query, "invoice_date", date_from, date_to)
        erp_result = erp_query.execute()
        erp_data = erp_result.data or []
        print(f"[BANK_VS_ERP] ERP data count: {len(erp_data)}")

        # ✅ FIXED: Bank transactions - using 'transaction_date' instead of 'date'
        bank_query = _table("bank_transactions").select("transaction_date, amount")
        bank_query = _apply_date_filter(bank_query, "transaction_date", date_from, date_to)
        bank_result = bank_query.execute()
        bank_data = bank_result.data or []
        print(f"[BANK_VS_ERP] Bank data count: {len(bank_data)}")

        # If no data at all, print first few records to check structure
        if len(erp_data) == 0:
            check_query = _table("erp_transactions").select("invoice_date, amount").limit(5).execute()
            print(f"[BANK_VS_ERP] Sample ERP data: {check_query.data}")
        
        if len(bank_data) == 0:
            check_query = _table("bank_transactions").select("transaction_date, amount").limit(5).execute()
            print(f"[BANK_VS_ERP] Sample Bank data: {check_query.data}")

        erp_buckets: Dict[str, float] = {}
        bank_buckets: Dict[str, float] = {}
        all_periods: set = set()

        for item in erp_data:
            date_val = str(item.get("invoice_date", ""))
            if not date_val:
                continue
            period = _get_bucket_key(date_val, bucket)
            all_periods.add(period)
            amount = float(item.get("amount", 0) or 0)
            erp_buckets[period] = erp_buckets.get(period, 0.0) + amount
        
        # ✅ FIXED: Bank data loop - using 'transaction_date' instead of 'date'
        for item in bank_data:
            date_val = str(item.get("transaction_date", ""))
            if not date_val:
                continue
            period = _get_bucket_key(date_val, bucket)
            all_periods.add(period)
            amount = abs(float(item.get("amount", 0) or 0))
            bank_buckets[period] = bank_buckets.get(period, 0.0) + amount

        sorted_periods = sorted(all_periods)
        print(f"[BANK_VS_ERP] Sorted periods: {sorted_periods}")

        return [
            {
                "period": p,
                "erp_volume": round(erp_buckets.get(p, 0.0), 2),
                "bank_volume": round(bank_buckets.get(p, 0.0), 2),
            }
            for p in sorted_periods
        ]
    except Exception as exc:
        print(f"[BANK_VS_ERP] Error: {exc}")
        import traceback
        traceback.print_exc()
        return []