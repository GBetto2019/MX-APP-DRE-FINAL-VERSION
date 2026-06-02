"""
Logging estruturado via structlog.

Em produção: JSON por linha (pronto para ingestão em Datadog, Loki, CloudWatch).
Em dev: texto colorido legível no terminal.

Uso:
    from app.logging_config import get_logger
    log = get_logger(__name__)
    log.info("dre_calculado", periodo=periodo, usuario_id=user_id, duracao_ms=elapsed)
"""
from __future__ import annotations

import logging
import sys

import structlog

from app.config import cfg


def setup_logging() -> None:
    """Configura structlog + logging stdlib. Chamar uma única vez no startup."""

    # Processors compartilhados entre stdlib e structlog
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if cfg.is_production:
        # JSON compacto — ingestão por ferramentas de log
        renderer = structlog.processors.JSONRenderer()
    else:
        # Colorido + legível para desenvolvimento
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if not cfg.is_production else logging.INFO)

    # Silenciar libs ruidosas em produção
    for lib in ("httpx", "httpcore", "asyncpg", "uvicorn.access"):
        logging.getLogger(lib).setLevel(
            logging.WARNING if cfg.is_production else logging.INFO
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retorna logger structlog para o módulo informado."""
    return structlog.get_logger(name)
