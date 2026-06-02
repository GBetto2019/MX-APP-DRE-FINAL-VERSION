"""Configuração global do pytest — adiciona raiz ao sys.path."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Silenciar libs ruidosas durante testes
for _lib in ("hpack", "httpx", "httpcore", "h2", "asyncio"):
    logging.getLogger(_lib).setLevel(logging.WARNING)
