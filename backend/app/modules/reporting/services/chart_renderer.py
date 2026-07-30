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
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib is not installed. Chart rendering will not be available.")


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
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("[CHART] matplotlib not available — cannot render chart")
            return None

        chart_type = chart_data.get("chart_type", "bar")
        labels = chart_data.get("labels", [])
        datasets = chart_data.get("datasets", [])

        if not labels or not datasets:
            logger.warning(f"[CHART] No chart data to render (labels={len(labels)}, datasets={len(datasets)})")
            return None

        logger.info(f"[CHART] Rendering chart type='{chart_type}' with {len(labels)} data points, {len(datasets)} datasets")

        try:
            fig = None
            if chart_type == "line":
                fig = ChartRenderer._render_line_chart(labels, datasets)
            elif chart_type == "bar":
                fig = ChartRenderer._render_bar_chart(labels, datasets)
            elif chart_type == "grouped_bar":
                fig = ChartRenderer._render_grouped_bar_chart(labels, datasets)
            elif chart_type in ("pie", "donut"):
                fig = ChartRenderer._render_pie_chart(labels, datasets, donut=(chart_type == "donut"))
            else:
                logger.warning(f"[CHART] Unknown chart type: '{chart_type}' — falling back to bar")
                fig = ChartRenderer._render_bar_chart(labels, datasets)

            if fig is None:
                return None

            # Save to file
            if output_path is None:
                output_path = os.path.join(
                    tempfile.gettempdir(),
                    f"chart_{uuid.uuid4().hex[:8]}.png"
                )

            fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
            plt.close(fig)

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"[CHART] Chart saved to {output_path} ({file_size} bytes)")
                return output_path

            logger.error(f"[CHART] Chart file was not created at {output_path}")
            return None

        except Exception as exc:
            logger.error(f"[CHART] Failed to render chart: {exc}", exc_info=True)
            if fig:
                plt.close(fig)
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