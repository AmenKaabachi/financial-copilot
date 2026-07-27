from typing import Any, Dict, List, Optional


def forecast_stub(
    historical_data: Optional[List[Dict[str, Any]]] = None,
    periods: int = 3,
    metric: str = "revenue",
) -> Dict[str, Any]:
    return {
        "status": "not_implemented",
        "message": "Forecasting is not yet available. This endpoint will return computed forecasts in a future release.",
        "historical_periods": len(historical_data) if historical_data else 0,
        "requested_periods": periods,
        "metric": metric,
    }