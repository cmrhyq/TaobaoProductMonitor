"""
Structured logging configuration using structlog.
Provides JSON output in production and colored console output in development.
"""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR)
        debug: If True, use colored console output; otherwise JSON
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if debug:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    else:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        A bound structlog logger
    """
    return structlog.get_logger(name)
