from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client


def _table(table: str):
    return get_supabase_client().table(table)


def pivot_aggregate(
    row_field: str = "category",
    column_field: str = "month",
    value_field: str = "amount",
    agg_func: str = "sum",
) -> Dict[str, Any]:
    """Get pivot data from erp_transactions using direct DB query."""
    try:
        result = _table("erp_transactions").select("*").execute()
        data = result.data or []

        rows: Dict[str, Dict[str, float]] = {}
        column_values: set = set()

        for item in data:
            invoice_date = str(item.get("invoice_date", ""))
            month_key = invoice_date[:7] if len(invoice_date) >= 7 else "unknown"
            category = str(item.get("supplier", "unknown"))
            amount = float(item.get("amount", 0) or 0)

            row_key = category if row_field == "category" else str(item.get(row_field, "unknown"))
            col_key = month_key if column_field == "month" else str(item.get(column_field, "unknown"))

            if row_key not in rows:
                rows[row_key] = {}
            rows[row_key][col_key] = rows[row_key].get(col_key, 0.0) + amount
            column_values.add(col_key)

        columns = sorted(column_values)
        row_totals = {}
        for row_key, col_vals in rows.items():
            row_totals[row_key] = round(sum(col_vals.values()), 2)

        return {
            "rows": list(rows.keys()),
            "columns": columns,
            "data": rows,
            "row_totals": row_totals,
            "column_totals": {
                col: round(sum(rows[row_key].get(col, 0.0) for row_key in rows), 2)
                for col in columns
            },
            "grand_total": round(sum(row_totals.values()), 2),
        }
    except Exception as exc:
        return {"rows": [], "columns": [], "data": {}, "row_totals": {}, "column_totals": {}, "grand_total": 0.0}


def pivot_group_by(
    group_by: str = "category",
    value_field: str = "amount",
    agg_func: str = "sum",
) -> List[Dict[str, Any]]:
    """Get grouped data from erp_transactions using direct DB query."""
    try:
        result = _table("erp_transactions").select("supplier, amount, status").execute()
        data = result.data or []

        groups: Dict[str, float] = {}
        counts: Dict[str, int] = {}

        for item in data:
            key = str(item.get("supplier", "unknown")) if group_by == "category" else str(item.get(group_by, "unknown"))
            value = float(item.get(value_field, 0) or 0)
            groups[key] = groups.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1

        result_list = []
        for key in sorted(groups.keys()):
            entry: Dict[str, Any] = {
                "group": key,
                "total": round(groups[key], 2),
                "count": counts[key],
            }
            if agg_func == "avg":
                entry["average"] = round(groups[key] / counts[key], 2) if counts[key] > 0 else 0.0
            result_list.append(entry)

        return result_list
    except Exception as exc:
        return []