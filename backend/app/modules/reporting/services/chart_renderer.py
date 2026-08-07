"""
Chart Renderer — Server-side chart generation for PDF export.

This module generates chart images from AnalyticsService chart data
using matplotlib. Images are saved as temporary PNG files and can be
embedded in ReportLab PDFs.

Flow:
    AnalyticsService.get_chart_data() → ChartRenderer → Temp PNG → ReportLab Image → PDF

Supported chart types:
    - line        → matplotlib line plot
    - bar         → matplotlib vertical bar chart
    - grouped_bar → matplotlib grouped bar chart
    - pie         → matplotlib pie chart
    - donut       → matplotlib donut chart (pie with hole)
"""

import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import matplotlib — fail gracefully if not available
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from matplotlib.patches import FancyBboxPatch

    MATPLOTLIB_AVAILABLE = True
    logger.info("[CHART] matplotlib imported successfully (version: %s)", matplotlib.__version__)
except ImportError as e:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("[CHART] matplotlib is not installed. Chart rendering will not be available. Error: %s", e)
except Exception as e:
    MATPLOTLIB_AVAILABLE = False
    logger.error("[CHART] matplotlib import failed unexpectedly: %s", e)


# ---------------------------------------------------------------------------
# Color Palette
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#2C3E50",
    "secondary": "#3498DB",
    "success": "#27AE60",
    "danger": "#E74C3C",
    "warning": "#F39C12",
    "info": "#1ABC9C",
    "light": "#ECF0F1",
    "dark": "#2C3E50",
}

CHART_COLORS = [
    "#3498DB",  # Blue
    "#E74C3C",  # Red
    "#27AE60",  # Green
    "#F39C12",  # Orange
    "#9B59B6",  # Purple
    "#1ABC9C",  # Teal
    "#E67E22",  # Dark Orange
    "#2ECC71",  # Emerald
    "#34495E",  # Dark Blue
    "#F1C40F",  # Yellow
]


# ---------------------------------------------------------------------------
# Chart Renderer
# ---------------------------------------------------------------------------

class ChartRenderer:
    """Generates chart images from AnalyticsService chart data."""

    @staticmethod
    def validate_chart_data(chart_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate chart data structure before rendering.

        Args:
            chart_data: Dictionary with chart data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not chart_data:
            return False, "Chart data is empty"

        chart_type = chart_data.get("chart_type")
        if not chart_type:
            return False, "Missing chart_type in chart data"

        labels = chart_data.get("labels")
        if not labels or not isinstance(labels, list):
            return False, "Missing or invalid labels in chart data"

        datasets = chart_data.get("datasets")
        if not datasets or not isinstance(datasets, list):
            return False, "Missing or invalid datasets in chart data"

        if len(datasets) == 0:
            return False, "Datasets list is empty"

        for i, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                return False, f"Dataset {i} is not a dictionary"
            if "data" not in dataset:
                return False, f"Dataset {i} missing 'data' key"
            if not isinstance(dataset["data"], list):
                return False, f"Dataset {i} 'data' is not a list"
            if len(dataset["data"]) == 0:
                return False, f"Dataset {i} 'data' list is empty"

        return True, ""

    @staticmethod
    def _normalize_chart_data(chart_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize chart payloads into a renderer-safe structure.

        This keeps chart rendering resilient when upstream analytics data has
        mixed value types or uneven dataset lengths.
        """
        if not isinstance(chart_data, dict):
            return None

        chart_type = chart_data.get("chart_type") or "bar"
        labels = chart_data.get("labels")
        labels_list = labels if isinstance(labels, list) else []

        datasets_raw = chart_data.get("datasets")
        if not isinstance(datasets_raw, list) or not datasets_raw:
            return None

        normalized_datasets: List[Dict[str, Any]] = []
        max_points = len(labels_list)
        for i, dataset in enumerate(datasets_raw):
            if not isinstance(dataset, dict):
                continue

            raw_values = dataset.get("data")
            if not isinstance(raw_values, list):
                continue

            numeric_values: List[float] = []
            for raw in raw_values:
                if raw is None:
                    numeric_values.append(0.0)
                    continue
                try:
                    numeric_values.append(float(raw))
                except (TypeError, ValueError):
                    numeric_values.append(0.0)

            if not numeric_values:
                continue

            max_points = max(max_points, len(numeric_values))
            normalized_datasets.append(
                {
                    "label": dataset.get("label", f"Series {i + 1}"),
                    "data": numeric_values,
                }
            )

        if not normalized_datasets:
            return None

        if not labels_list and max_points > 0:
            labels_list = [f"Item {index + 1}" for index in range(max_points)]

        labels_list = [str(label) for label in labels_list]
        target_len = len(labels_list)
        if target_len == 0:
            return None

        for dataset in normalized_datasets:
            values = dataset["data"]
            if len(values) < target_len:
                dataset["data"] = values + [0.0] * (target_len - len(values))
            elif len(values) > target_len:
                dataset["data"] = values[:target_len]

        return {
            "chart_type": chart_type,
            "labels": labels_list,
            "datasets": normalized_datasets,
        }

    @staticmethod
    def render_chart(chart_data: Dict[str, Any], output_path: Optional[str] = None) -> Optional[str]:
        """
        Render a chart from structured chart data.

        Args:
            chart_data: Dictionary with keys:
                - chart_type: str (line, bar, grouped_bar, pie, donut)
                - labels: list of str
                - datasets: list of dicts with 'label' and 'data' keys
            output_path: Optional path to save the image. If None, a temp file is created.

        Returns:
            Path to the rendered PNG image, or None on failure.
        """
        invocation = uuid.uuid4().hex[:8]
        logger.debug(f"[CHART][{invocation}] render_chart() called. MATPLOTLIB_AVAILABLE={MATPLOTLIB_AVAILABLE}")
        if not MATPLOTLIB_AVAILABLE:
            logger.warning(f"[CHART][{invocation}] matplotlib not available — cannot render chart")
            logger.debug(f"[CHART][{invocation}] returning None (matplotlib_unavailable)")
            return None

        normalized_data = ChartRenderer._normalize_chart_data(chart_data)
        if not normalized_data:
            logger.warning(f"[CHART][{invocation}] Chart data normalization failed")
            logger.debug(f"[CHART][{invocation}] Raw chart_data: {chart_data}")
            logger.debug(f"[CHART][{invocation}] returning None (normalization_failed)")
            return None

        # Validate chart data structure
        is_valid, error_msg = ChartRenderer.validate_chart_data(normalized_data)
        if not is_valid:
            logger.warning(f"[CHART][{invocation}] Chart data validation failed: {error_msg}")
            logger.debug(f"[CHART][{invocation}] Invalid normalized chart_data structure: {normalized_data}")
            logger.debug(f"[CHART][{invocation}] returning None (validation_failed)")
            return None

        chart_type = normalized_data.get("chart_type", "bar")
        labels = normalized_data.get("labels", [])
        datasets = normalized_data.get("datasets", [])

        logger.info(f"[CHART][{invocation}] Rendering chart type='{chart_type}' with {len(labels)} data points, {len(datasets)} datasets")
        logger.debug(f"[CHART][{invocation}] labels: {labels[:5]}... (showing first 5)")
        logger.debug(f"[CHART][{invocation}] datasets: {len(datasets)} datasets")
        for i, ds in enumerate(datasets):
            logger.debug(f"[CHART][{invocation}]   dataset[{i}]: label={ds.get('label', 'N/A')}, data_len={len(ds.get('data', []))}")

        try:
            fig = None
            logger.debug(f"[CHART][{invocation}] Dispatching chart_type='{chart_type}' to renderer")
            if chart_type == "line":
                fig = ChartRenderer._render_line_chart(labels, datasets)
            elif chart_type == "bar":
                fig = ChartRenderer._render_bar_chart(labels, datasets)
            elif chart_type == "grouped_bar":
                fig = ChartRenderer._render_grouped_bar_chart(labels, datasets)
            elif chart_type in ("pie", "donut"):
                fig = ChartRenderer._render_pie_chart(labels, datasets, donut=(chart_type == "donut"))
            else:
                logger.warning(f"[CHART][{invocation}] Unknown chart type: '{chart_type}' — falling back to bar")
                fig = ChartRenderer._render_bar_chart(labels, datasets)

            if fig is None:
                logger.error(f"[CHART][{invocation}] Figure creation returned None")
                logger.debug(f"[CHART][{invocation}] returning None (figure_none)")
                return None

            # Save to file
            if output_path is None:
                output_path = os.path.join(
                    tempfile.gettempdir(),
                    f"chart_{uuid.uuid4().hex[:8]}.png"
                )

            logger.debug(f"[CHART][{invocation}] Saving chart to: {output_path}")
            fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
            plt.close(fig)

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"[CHART] Generated image: {output_path} ({file_size} bytes)")
                logger.debug(f"[CHART][{invocation}] returning success (path)")
                return output_path

            logger.error(f"[CHART] Failed generating chart: output file was not created at {output_path}")
            logger.debug(f"[CHART][{invocation}] returning None (file_missing)")
            return None

        except Exception as exc:
            logger.error(f"[CHART] Failed generating chart: {exc}", exc_info=True)
            if fig:
                plt.close(fig)
            logger.debug(f"[CHART][{invocation}] returning None (exception)")
            return None

    # ------------------------------------------------------------------
    # Line Chart
    # ------------------------------------------------------------------

    @staticmethod
    def _render_line_chart(labels: List[str], datasets: List[Dict[str, Any]]):
        """Render a line chart."""
        fig, ax = plt.subplots(figsize=(7, 3.5))
        fig.patch.set_facecolor("white")

        for i, ds in enumerate(datasets):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            ax.plot(
                labels,
                ds.get("data", []),
                marker="o",
                linewidth=2,
                color=color,
                label=ds.get("label", f"Series {i+1}"),
                markersize=4,
            )

        ax.set_xlabel("Period", fontsize=9, color=COLORS["dark"])
        ax.set_ylabel("Value", fontsize=9, color=COLORS["dark"])
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(fontsize=8, loc="best")

        # Rotate x labels for readability
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)

        # Format y-axis with commas
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))

        fig.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Bar Chart
    # ------------------------------------------------------------------

    @staticmethod
    def _render_bar_chart(labels: List[str], datasets: List[Dict[str, Any]]):
        """Render a vertical bar chart."""
        fig, ax = plt.subplots(figsize=(7, 3.5))
        fig.patch.set_facecolor("white")

        x = range(len(labels))
        width = 0.6

        for i, ds in enumerate(datasets):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            bars = ax.bar(
                x,
                ds.get("data", []),
                width=width,
                color=color,
                alpha=0.85,
                label=ds.get("label", f"Series {i+1}"),
                edgecolor="white",
                linewidth=0.5,
            )

        ax.set_xlabel("Category", fontsize=9, color=COLORS["dark"])
        ax.set_ylabel("Value", fontsize=9, color=COLORS["dark"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))

        if len(datasets) > 1:
            ax.legend(fontsize=8, loc="best")

        fig.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Grouped Bar Chart
    # ------------------------------------------------------------------

    @staticmethod
    def _render_grouped_bar_chart(labels: List[str], datasets: List[Dict[str, Any]]):
        """Render a grouped bar chart for comparing multiple datasets."""
        fig, ax = plt.subplots(figsize=(7, 3.5))
        fig.patch.set_facecolor("white")

        x = range(len(labels))
        n_datasets = len(datasets)
        total_width = 0.8
        single_width = total_width / n_datasets
        offset = -total_width / 2 + single_width / 2

        for i, ds in enumerate(datasets):
            color = CHART_COLORS[i % len(CHART_COLORS)]
            bar_positions = [pos + offset + i * single_width for pos in x]
            ax.bar(
                bar_positions,
                ds.get("data", []),
                width=single_width * 0.85,
                color=color,
                alpha=0.85,
                label=ds.get("label", f"Series {i+1}"),
                edgecolor="white",
                linewidth=0.5,
            )

        ax.set_xlabel("Period", fontsize=9, color=COLORS["dark"])
        ax.set_ylabel("Value", fontsize=9, color=COLORS["dark"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
        ax.legend(fontsize=8, loc="best")

        fig.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Pie / Donut Chart
    # ------------------------------------------------------------------

    @staticmethod
    def _render_pie_chart(labels: List[str], datasets: List[Dict[str, Any]], donut: bool = False):
        """Render a pie or donut chart."""
        fig, ax = plt.subplots(figsize=(5, 4))
        fig.patch.set_facecolor("white")

        # Use the first dataset's data
        if not datasets:
            return None

        data = datasets[0].get("data", [])
        if not data:
            return None

        # Filter out zero values
        filtered_labels = []
        filtered_data = []
        for i, val in enumerate(data):
            if val and float(val) > 0:
                filtered_labels.append(labels[i] if i < len(labels) else f"Item {i+1}")
                filtered_data.append(float(val))

        if not filtered_data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12, color=COLORS["dark"])
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            fig.tight_layout()
            return fig

        colors = CHART_COLORS[:len(filtered_data)]

        wedges, texts, autotexts = ax.pie(
            filtered_data,
            labels=filtered_labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.75 if donut else 0.6,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
            textprops={"fontsize": 8},
        )

        if donut:
            # Draw a white circle in the center to create the donut hole
            centre_circle = plt.Circle((0, 0), 0.45, fc="white", edgecolor="white", linewidth=0)
            ax.add_artist(centre_circle)

        ax.axis("equal")  # Equal aspect ratio ensures pie is circular

        # Add legend
        ax.legend(
            wedges,
            [f"{l}: {v:,.0f}" for l, v in zip(filtered_labels, filtered_data)],
            title="Values",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),
            fontsize=7,
            title_fontsize=8,
        )

        fig.tight_layout()
        return fig

    # ------------------------------------------------------------------
    # Convenience: Render from AnalyticsService component preview
    # ------------------------------------------------------------------

    @staticmethod
    def render_from_component(component_id: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Convenience method: render a chart from a component ID.

        This is useful for the export engine where sections reference
        analytics components by their component_id.

        Args:
            component_id: The analytics component ID (e.g., "chart_reconciliation_trend")
            params: Optional parameters (date_from, date_to, bucket, etc.)

        Returns:
            Path to the rendered PNG image, or None on failure.
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            from app.modules.reporting.services.analytics_service import AnalyticsService
            preview = AnalyticsService.get_component_preview(component_id, params or {})
            if not preview:
                logger.warning(f"[CHART] No preview data for component: {component_id}")
                return None

            chart_data = preview.get("data")
            if not chart_data:
                logger.warning(f"[CHART] No chart data in preview for component: {component_id}")
                return None

            return ChartRenderer.render_chart(chart_data)
        except Exception as exc:
            logger.error(f"[CHART] Failed to render from component {component_id}: {exc}", exc_info=True)
            return None