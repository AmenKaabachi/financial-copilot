from typing import Any, Dict, List, Optional

from app.shared.database.retrieval import retrieve_context


def pivot_aggregate(
    data: Optional[List[Dict[str, Any]]] = None,
    row_field: str = "category",
    column_field: str = "month",
    value_field: str = "amount",
    agg_func: str = "sum",
) -> Dict[str, Any]:
    if data is None:
        data = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    rows: Dict[str, Dict[str, float]] = {}
    column_values: set = set()

    for item in data:
        row_key = str(item.get(row_field, "unknown"))
        col_key = str(item.get(column_field, "unknown"))
        value = float(item.get(value_field, 0) or 0)

        if row_key not in rows:
            rows[row_key] = {}
        rows[row_key][col_key] = rows[row_key].get(col_key, 0.0) + value
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


def pivot_group_by(
    data: Optional[List[Dict[str, Any]]] = None,
    group_by: str = "category",
    value_field: str = "amount",
    agg_func: str = "sum",
) -> List[Dict[str, Any]]:
    if data is None:
        data = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    groups: Dict[str, float] = {}
    counts: Dict[str, int] = {}

    for item in data:
        key = str(item.get(group_by, "unknown"))
        value = float(item.get(value_field, 0) or 0)
        groups[key] = groups.get(key, 0.0) + value
        counts[key] = counts.get(key, 0) + 1

    result = []
    for key in sorted(groups.keys()):
        entry: Dict[str, Any] = {
            "group": key,
            "total": round(groups[key], 2),
            "count": counts[key],
        }
        if agg_func == "avg":
            entry["average"] = round(groups[key] / counts[key], 2) if counts[key] > 0 else 0.0
        result.append(entry)

    return result