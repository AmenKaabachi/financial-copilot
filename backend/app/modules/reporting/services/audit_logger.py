"""Audit logger for AI report generation.

Tracks report generation for SaaS production requirements:
- Report generation request
- Model used
- Generation time
- Token usage
- Validation result
- Fallback usage
"""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path

from app.modules.reporting.schemas.ai_report_schemas import (
    GenerationAuditLog,
    ReportGenerationRequest,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs AI report generation events for audit trail."""

    # Audit log storage path (can be configured via environment)
    AUDIT_LOG_PATH = Path("logs/ai_report_audit.log")
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def log_generation(
        request: ReportGenerationRequest,
        model_used: str,
        generation_time_seconds: float,
        token_usage: Dict[str, int],
        validation_result: ValidationResult,
        fallback_used: bool,
        sections_generated: list[str],
        report_id: Optional[str] = None,
    ) -> GenerationAuditLog:
        """
        Log a report generation event.

        Args:
            request: The generation request
            model_used: Model used for generation
            generation_time_seconds: Time taken to generate
            token_usage: Token usage statistics
            validation_result: Validation result
            fallback_used: Whether fallback was used
            sections_generated: List of sections successfully generated
            report_id: Optional report ID if associated with saved report

        Returns:
            GenerationAuditLog object
        """
        audit_log = GenerationAuditLog(
            report_id=report_id,
            request=request,
            model_used=model_used,
            generation_time_seconds=generation_time_seconds,
            token_usage=token_usage,
            validation_result=validation_result,
            fallback_used=fallback_used,
            sections_generated=sections_generated,
            generated_at=datetime.utcnow(),
        )

        # Write to audit log file
        AuditLogger._write_to_log_file(audit_log)

        # Log to application logger
        AuditLogger._log_to_app_logger(audit_log)

        return audit_log

    @staticmethod
    def _write_to_log_file(audit_log: GenerationAuditLog) -> None:
        """Write audit log entry to file."""
        try:
            log_entry = {
                "timestamp": audit_log.generated_at.isoformat(),
                "report_id": audit_log.report_id,
                "report_type": audit_log.request.report_type,
                "period": {
                    "from": audit_log.request.date_from,
                    "to": audit_log.request.date_to,
                },
                "language": audit_log.request.language,
                "sections_requested": audit_log.request.sections,
                "model_used": audit_log.model_used,
                "generation_time_seconds": audit_log.generation_time_seconds,
                "token_usage": audit_log.token_usage,
                "validation": {
                    "is_valid": audit_log.validation_result.is_valid,
                    "errors": audit_log.validation_result.errors,
                    "warnings": audit_log.validation_result.warnings,
                    "corrected": audit_log.validation_result.corrected,
                },
                "fallback_used": audit_log.fallback_used,
                "sections_generated": audit_log.sections_generated,
            }

            with open(AuditLogger.AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            logger.error("Failed to write audit log to file: %s", e)

    @staticmethod
    def _log_to_app_logger(audit_log: GenerationAuditLog) -> None:
        """Log audit entry to application logger."""
        logger.info(
            "AI Report Generation Audit | "
            "report_type=%s | "
            "model=%s | "
            "time=%.2fs | "
            "tokens=%s | "
            "valid=%s | "
            "fallback=%s | "
            "sections=%s",
            audit_log.request.report_type,
            audit_log.model_used,
            audit_log.generation_time_seconds,
            audit_log.token_usage.get("total_tokens", "N/A"),
            audit_log.validation_result.is_valid,
            audit_log.fallback_used,
            ",".join(audit_log.sections_generated),
        )

        if not audit_log.validation_result.is_valid:
            logger.warning(
                "Validation failed for report generation: %s",
                audit_log.validation_result.errors
            )

        if audit_log.fallback_used:
            logger.warning(
                "Fallback used for report generation: %s",
                audit_log.request.report_type
            )

    @staticmethod
    def log_section_generation(
        section_type: str,
        model_used: str,
        generation_time_seconds: float,
        token_usage: Dict[str, int],
        validation_result: ValidationResult,
        fallback_used: bool,
    ) -> None:
        """
        Log individual section generation event.

        Args:
            section_type: Type of section generated
            model_used: Model used
            generation_time_seconds: Time taken
            token_usage: Token usage
            validation_result: Validation result
            fallback_used: Whether fallback was used
        """
        logger.info(
            "Section Generation | "
            "section=%s | "
            "model=%s | "
            "time=%.2fs | "
            "tokens=%s | "
            "valid=%s | "
            "fallback=%s",
            section_type,
            model_used,
            generation_time_seconds,
            token_usage.get("total_tokens", "N/A"),
            validation_result.is_valid,
            fallback_used,
        )

    @staticmethod
    def log_error(
        section_type: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log an error during report generation.

        Args:
            section_type: Type of section being generated
            error: The exception that occurred
            context: Optional context information
        """
        logger.error(
            "Report Generation Error | section=%s | error=%s | context=%s",
            section_type,
            str(error),
            json.dumps(context) if context else "None",
            exc_info=True,
        )

    @staticmethod
    def get_recent_audit_logs(limit: int = 100) -> list[Dict[str, Any]]:
        """
        Retrieve recent audit log entries.

        Args:
            limit: Maximum number of entries to retrieve

        Returns:
            List of audit log entries
        """
        logs = []
        try:
            if not AuditLogger.AUDIT_LOG_PATH.exists():
                return logs

            with open(AuditLogger.AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            logs.append(json.loads(line))
                            if len(logs) >= limit:
                                break
                        except json.JSONDecodeError:
                            continue

            # Return in reverse order (most recent first)
            return list(reversed(logs))

        except Exception as e:
            logger.error("Failed to read audit logs: %s", e)
            return logs

    @staticmethod
    def get_generation_statistics(hours: int = 24) -> Dict[str, Any]:
        """
        Get generation statistics for a time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Statistics dictionary
        """
        logs = AuditLogger.get_recent_audit_logs(limit=1000)
        
        if not logs:
            return {
                "total_generations": 0,
                "successful_generations": 0,
                "failed_generations": 0,
                "fallback_usage_count": 0,
                "average_generation_time": 0,
                "total_tokens_used": 0,
                "most_used_model": None,
            }

        # Filter by time period
        cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
        recent_logs = [
            log for log in logs
            if datetime.fromisoformat(log["timestamp"]).timestamp() > cutoff_time
        ]

        if not recent_logs:
            return {
                "total_generations": 0,
                "successful_generations": 0,
                "failed_generations": 0,
                "fallback_usage_count": 0,
                "average_generation_time": 0,
                "total_tokens_used": 0,
                "most_used_model": None,
            }

        # Calculate statistics
        total_generations = len(recent_logs)
        successful_generations = sum(1 for log in recent_logs if log["validation"]["is_valid"])
        failed_generations = total_generations - successful_generations
        fallback_usage_count = sum(1 for log in recent_logs if log["fallback_used"])
        
        generation_times = [log["generation_time_seconds"] for log in recent_logs]
        average_generation_time = sum(generation_times) / len(generation_times) if generation_times else 0
        
        total_tokens = sum(log["token_usage"].get("total_tokens", 0) for log in recent_logs)
        
        # Find most used model
        model_counts = {}
        for log in recent_logs:
            model = log["model_used"]
            model_counts[model] = model_counts.get(model, 0) + 1
        most_used_model = max(model_counts, key=model_counts.get) if model_counts else None

        return {
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "failed_generations": failed_generations,
            "fallback_usage_count": fallback_usage_count,
            "average_generation_time": round(average_generation_time, 2),
            "total_tokens_used": total_tokens,
            "most_used_model": most_used_model,
        }
