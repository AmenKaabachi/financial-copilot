"""Report Data Resolver - Unified analytics datasource layer.

This service resolves report section data from the existing AnalyticsService
infrastructure, ensuring that Analytics Workspace and Report Builder display
identical values.

Architecture:
    Report Section Definition → ReportDataResolver → AnalyticsService → Normalized Data → Export Engine

This ensures reporting is a presentation layer over Analytics, not a separate system.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.analytics.component_registry import get_component_by_id

logger = logging.getLogger(__name__)


class ReportDataResolver:
    """Resolves report section data from AnalyticsService."""

    @staticmethod
    def resolve(section: Dict[str, Any], date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolve data for a report section from AnalyticsService.

        Args:
            section: Section definition with type and analytics source
            date_from: Optional date range start
            date_to: Optional date range end

        Returns:
            Normalized data for rendering
        """
        if not section:
            logger.error("[RESOLVER] Section is None or empty")
            return {"error": "Section is None or empty"}
        
        section_type = section.get("type")
        if not section_type:
            logger.error(f"[RESOLVER] Section missing 'type' field. Section keys: {list(section.keys())}")
            return {"error": f"Section missing 'type' field. Available keys: {list(section.keys())}"}
        
        source = section.get("source", "analytics")

        logger.info(f"[RESOLVER] Resolving section type={section_type}, source={source}")

        if source != "analytics":
            logger.warning(f"[RESOLVER] Unknown source type: {source}")
            return {"error": f"Unknown source type: {source}"}

        if section_type == "kpi":
            return ReportDataResolver._resolve_kpi(section, date_from, date_to)
        elif section_type == "chart":
            return ReportDataResolver._resolve_chart(section, date_from, date_to)
        elif section_type == "table":
            return ReportDataResolver._resolve_table(section, date_from, date_to)
        elif section_type == "trend":
            return ReportDataResolver._resolve_trend(section, date_from, date_to)
        elif section_type == "pivot":
            return ReportDataResolver._resolve_pivot(section, date_from, date_to)
        elif section_type == "heatmap":
            return ReportDataResolver._resolve_heatmap(section, date_from, date_to)
        else:
            logger.warning(f"[RESOLVER] Unknown section type: {section_type}")
            return {"error": f"Unknown section type: {section_type}"}

    @staticmethod
    def _resolve_kpi(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve KPI data from AnalyticsService."""
        config = section.get("config", {})
        # Try top-level first, then fall back to config sub-dict
        metric = (
            section.get("metric") or section.get("kpi_key")
            or config.get("metric") or config.get("kpi_key")
            or (config.get("kpis", [None])[0] if isinstance(config.get("kpis"), list) else None)
        )
        component_id = config.get("component_id") or section.get("component_id")

        logger.info(f"[RESOLVER] Resolving KPI: metric={metric}, component_id={component_id}")

        if component_id:
            # Use component registry for component-based KPIs
            try:
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                })
                if preview and preview.get("data"):
                    data = preview["data"]
                    # Normalize to KPI format
                    return {
                        "title": section.get("title", get_component_by_id(component_id).get("name", "KPI")),
                        "data": data,
                        "format": ReportDataResolver._infer_format(data),
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve KPI from component {component_id}: {e}")
                return {"error": str(e)}

        if metric:
            # Use direct KPI calculation
            try:
                kpi_data = AnalyticsService.get_single_kpi(metric, date_from=date_from, date_to=date_to)
                if kpi_data:
                    return {
                        "title": section.get("title", metric.replace("_", " ").title()),
                        "data": kpi_data,
                        "format": ReportDataResolver._infer_format(kpi_data),
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve KPI {metric}: {e}")
                return {"error": str(e)}

        logger.warning("[RESOLVER] KPI section has no metric or component_id")
        return {"error": "KPI section: no data source specified"}

    @staticmethod
    def _resolve_chart(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve chart data from AnalyticsService.

        The Manual Report Builder sends chart sections in this format:

            {
              "type": "chart",
              "config": {
                "chart_type": "line",                 # user-selected render type
                "data_source": "reconciliation_trend", # analytics chart key
                "title": "Chart"
              }
            }

        ``data_source`` is the key understood by ``AnalyticsService.get_chart_data()``
        (e.g. reconciliation_trend, transaction_volume, anomaly_distribution,
        bank_vs_erp, payment_status), while ``chart_type`` is the matplotlib
        render type (line, bar, grouped_bar, pie, donut). This resolver therefore:

        1. Uses ``data_source`` (falling back to ``chart_type``) as the chart key.
        2. Overrides the fetched data's ``chart_type`` with the user's selected
           render type when it is a valid matplotlib type.
        """
        config = section.get("config", {})
        chart_type = section.get("chart_type") or config.get("chart_type")
        data_source = section.get("data_source") or config.get("data_source")
        metric = section.get("metric") or config.get("metric")
        component_id = config.get("component_id") or section.get("component_id")
        bucket = section.get("bucket", "month") or config.get("bucket", "month")

        logger.info(
            f"[RESOLVER] Resolving chart: chart_type={chart_type}, data_source={data_source}, "
            f"metric={metric}, component_id={component_id}"
        )

        if component_id:
            # Use component registry for component-based charts
            try:
                logger.debug(f"[RESOLVER] Fetching component preview for component_id={component_id}")
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                    "bucket": bucket,
                })
                if preview and preview.get("data"):
                    chart_data = preview["data"]
                    logger.debug(f"[RESOLVER] Component preview data keys: {list(chart_data.keys()) if isinstance(chart_data, dict) else 'N/A'}")
                    rendered_type = ReportDataResolver._resolve_render_type(chart_data, chart_type)
                    if rendered_type != chart_data.get("chart_type"):
                        chart_data = dict(chart_data)
                        chart_data["chart_type"] = rendered_type
                    logger.debug(f"[RESOLVER] Component chart resolved: type={rendered_type}, "
                                 f"labels={len(chart_data.get('labels', []))}, "
                                 f"datasets={len(chart_data.get('datasets', []))}")
                    return {
                        "type": rendered_type,
                        "title": section.get("title", get_component_by_id(component_id).get("name", "Chart")),
                        "data": chart_data,
                    }
                else:
                    logger.warning(f"[RESOLVER] Component preview returned no data for {component_id}")
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve chart from component {component_id}: {e}", exc_info=True)
                return {"error": str(e)}

        # Manual builder sends 'data_source' as the analytics chart key while
        # 'chart_type' holds the user-selected render type. Prefer data_source.
        chart_key = data_source or chart_type
        logger.debug(f"[RESOLVER] chart_key selected: '{chart_key}' (data_source={data_source}, chart_type={chart_type})")
        if chart_key:
            # Use direct chart data fetch
            try:
                logger.debug(f"[RESOLVER] Calling AnalyticsService.get_chart_data(chart_key='{chart_key}', bucket='{bucket}')")
                chart_data = AnalyticsService.get_chart_data(
                    chart_key, date_from=date_from, date_to=date_to, bucket=bucket
                )
                if chart_data:
                    logger.debug(f"[RESOLVER] get_chart_data returned: chart_type={chart_data.get('chart_type')}, "
                                 f"labels={len(chart_data.get('labels', []))}, "
                                 f"datasets={len(chart_data.get('datasets', []))}")
                    rendered_type = ReportDataResolver._resolve_render_type(chart_data, chart_type)
                    if rendered_type != chart_data.get("chart_type"):
                        chart_data = dict(chart_data)
                        chart_data["chart_type"] = rendered_type
                    logger.debug(f"[RESOLVER] Final render type after override: {rendered_type}")
                    return {
                        "type": rendered_type,
                        "title": section.get("title", (data_source or chart_type).replace("_", " ").title()),
                        "data": chart_data,
                    }
                else:
                    logger.warning(f"[RESOLVER] AnalyticsService.get_chart_data('{chart_key}') returned None/empty")
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve chart {chart_key}: {e}", exc_info=True)
                return {"error": str(e)}

        logger.warning("[RESOLVER] Chart section has no data_source/chart_type or component_id")
        return {"error": "Chart data is not available for this period"}

    @staticmethod
    def _resolve_render_type(chart_data: Dict[str, Any], requested_type: Optional[str]) -> str:
        """Determine the final chart render type.

        Priority:
        1. Explicit user-selected render type if it is a valid matplotlib type
        2. The chart data's native type
        3. Default to 'line'
        """
        valid_types = {"line", "bar", "grouped_bar", "pie", "donut"}
        if requested_type and requested_type in valid_types:
            return requested_type
        native_type = chart_data.get("chart_type") if isinstance(chart_data, dict) else None
        if native_type in valid_types:
            return native_type
        return "line"

    @staticmethod
    def _resolve_table(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve table data from AnalyticsService."""
        config = section.get("config", {})
        data_source = section.get("data_source") or section.get("analytics_source") or config.get("data_source")
        component_id = config.get("component_id") or section.get("component_id")
        limit = section.get("limit", 50) or config.get("limit", 50)

        logger.info(f"[RESOLVER] Resolving table: data_source={data_source}, component_id={component_id}")

        if component_id:
            # Use component registry for component-based tables
            try:
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                    "limit": limit,
                })
                if preview and preview.get("data"):
                    return {
                        "title": section.get("title", get_component_by_id(component_id).get("name", "Table")),
                        "data": preview["data"],
                        "rows": len(preview["data"]) if isinstance(preview["data"], list) else 1,
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve table from component {component_id}: {e}")
                return {"error": str(e)}

        if data_source:
            # Use direct table data fetch
            try:
                rows = AnalyticsService.get_table_data(
                    data_source, date_from=date_from, date_to=date_to, limit=limit
                )
                return {
                    "title": section.get("title", data_source.replace("_", " ").title()),
                    "data": rows,
                    "rows": len(rows) if rows else 0,
                }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve table {data_source}: {e}")
                return {"error": str(e)}

        logger.warning("[RESOLVER] Table section has no data_source or component_id")
        return {"error": "No data available for this table"}

    @staticmethod
    def _resolve_trend(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve trend data from AnalyticsService."""
        metric = section.get("metric") or section.get("config", {}).get("metric")
        bucket = section.get("bucket", "month") or section.get("config", {}).get("bucket", "month")
        component_id = section.get("config", {}).get("component_id") or section.get("component_id")

        logger.info(f"[RESOLVER] Resolving trend: metric={metric}, component_id={component_id}")

        if component_id:
            # Use component registry for component-based trends
            try:
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                    "bucket": bucket,
                })
                if preview and preview.get("data"):
                    return {
                        "type": preview["data"].get("chart_type", "trend"),
                        "title": section.get("title", get_component_by_id(component_id).get("name", "Trend")),
                        "data": preview["data"],
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve trend from component {component_id}: {e}")
                return {"error": str(e)}

        if metric:
            try:
                trend_data = AnalyticsService.get_trends(
                    metric=metric, bucket=bucket, date_from=date_from, date_to=date_to
                )
                if trend_data:
                    return {
                        "type": "trend",
                        "title": section.get("title", metric.replace("_", " ").title()),
                        "data": trend_data,
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve trend {metric}: {e}")
                return {"error": str(e)}

        logger.warning("[RESOLVER] Trend section has no metric or component_id")
        return {"error": "Trend data not available"}

    @staticmethod
    def _resolve_pivot(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve pivot data from AnalyticsService."""
        data_source = section.get("data_source") or section.get("config", {}).get("data_source")
        component_id = section.get("config", {}).get("component_id") or section.get("component_id")

        logger.info(f"[RESOLVER] Resolving pivot: data_source={data_source}, component_id={component_id}")

        if component_id:
            # Use component registry for component-based pivots
            try:
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                })
                if preview and preview.get("data"):
                    return {
                        "type": "pivot",
                        "title": section.get("title", get_component_by_id(component_id).get("name", "Pivot")),
                        "data": preview["data"],
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve pivot from component {component_id}: {e}")
                return {"error": str(e)}

        if data_source:
            try:
                pivot_data = AnalyticsService.get_pivot(
                    data_source, date_from=date_from, date_to=date_to
                )
                if pivot_data:
                    return {
                        "type": "pivot",
                        "title": section.get("title", data_source.replace("_", " ").title()),
                        "data": pivot_data,
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve pivot {data_source}: {e}")
                return {"error": str(e)}

        logger.warning("[RESOLVER] Pivot section has no data_source or component_id")
        return {"error": "Pivot data not available"}

    @staticmethod
    def _resolve_heatmap(section: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Resolve heatmap data from AnalyticsService."""
        data_source = section.get("data_source") or section.get("config", {}).get("data_source")
        component_id = section.get("config", {}).get("component_id") or section.get("component_id")

        logger.info(f"[RESOLVER] Resolving heatmap: data_source={data_source}, component_id={component_id}")

        if component_id:
            # Use component registry for component-based heatmaps
            try:
                preview = AnalyticsService.get_component_preview(component_id, {
                    "date_from": date_from,
                    "date_to": date_to,
                })
                if preview and preview.get("data"):
                    return {
                        "type": "heatmap",
                        "title": section.get("title", get_component_by_id(component_id).get("name", "Heatmap")),
                        "data": preview["data"],
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve heatmap from component {component_id}: {e}")
                return {"error": str(e)}

        if data_source:
            try:
                heatmap_data = AnalyticsService.get_heatmap(
                    data_source, date_from=date_from, date_to=date_to
                )
                if heatmap_data:
                    return {
                        "type": "heatmap",
                        "title": section.get("title", data_source.replace("_", " ").title()),
                        "data": heatmap_data,
                    }
            except Exception as e:
                logger.error(f"[RESOLVER] Failed to resolve heatmap {data_source}: {e}")
                return {"error": str(e)}

        logger.warning("[RESOLVER] Heatmap section has no data_source or component_id")
        return {"error": "Heatmap data not available"}

    @staticmethod
    def _infer_format(data: Dict[str, Any]) -> str:
        """Infer data format from KPI data structure."""
        if not data:
            return "text"

        # Check for percentage indicators
        for key, value in data.items():
            if "rate" in key.lower() or "ratio" in key.lower() or "margin" in key.lower():
                return "percent"
            if isinstance(value, (int, float)):
                # If value is between 0 and 1, might be percentage
                if 0 <= value <= 1:
                    return "percent"

        # Default to currency for financial metrics
        return "currency"

    @staticmethod
    def resolve_all_sections(sections: List[Dict[str, Any]], date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Resolve data for all sections in a report.

        Args:
            sections: List of section definitions
            date_from: Optional date range start
            date_to: Optional date range end

        Returns:
            Dictionary mapping section IDs to resolved data
        """
        resolved = {}
        for section in sections:
            section_id = section.get("id") or section.get("section_id")
            if section_id:
                resolved[section_id] = ReportDataResolver.resolve(section, date_from, date_to)
        return resolved