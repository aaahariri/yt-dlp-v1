"""
Logging Utilities for RunPod Serverless Environment

This module provides centralized logging configuration for the RunPod serverless
handler and FastAPI application. It ensures consistent log formatting with
request/job ID tracing across all operations.

The logging setup is optimized for RunPod's stdout/stderr capture system while
providing structured, traceable logs for debugging and monitoring.
"""
import logging
from typing import Optional


def setup_logger(
    log_level: int = logging.INFO,
    logger_name: str = "runpod_handler"
) -> logging.Logger:
    """
    Configure logger for RunPod serverless environment.

    RunPod captures stdout/stderr and displays in the console. Using Python's
    logging module provides better formatting and control over log output.

    Args:
        log_level: Logging level constant from logging module.
                  Defaults to logging.INFO (20).
        logger_name: Name for the logger instance. Defaults to "runpod_handler".

    Returns:
        Configured Logger instance ready for use with get_job_logger().

    Example:
        >>> logger = setup_logger(log_level=logging.DEBUG)
        >>> job_logger = get_job_logger("job-123")
        >>> job_logger.info("Processing started")
        2025-12-22 10:30:45 | INFO | [job-123] Processing started
    """
    log_format = logging.Formatter(
        '%(asctime)s | %(levelname)s | [%(request_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers if logger already configured
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    return logger


def get_job_logger(
    job_id: str,
    base_logger: Optional[logging.Logger] = None
) -> logging.LoggerAdapter:
    """
    Create a logger adapter with the job/request ID for tracing.

    The LoggerAdapter injects the job_id into all log messages, enabling
    end-to-end tracing of a single job through the entire processing pipeline.

    Args:
        job_id: Unique identifier for the job or request.
        base_logger: Optional base logger to wrap. If None, uses the default
                    logger with name "runpod_handler".

    Returns:
        LoggerAdapter configured to inject job_id into all log messages.

    Example:
        >>> base = setup_logger()
        >>> logger = get_job_logger("job-abc123", base)
        >>> logger.info("Starting video download")
        2025-12-22 10:30:45 | INFO | [job-abc123] Starting video download
    """
    if base_logger is None:
        base_logger = logging.getLogger("runpod_handler")

    return logging.LoggerAdapter(base_logger, {"request_id": job_id})
