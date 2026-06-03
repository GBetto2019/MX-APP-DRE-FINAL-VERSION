"""MX Seguros — DRE-IA | Router: GET /dashboard (resposta agregada)"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth import UsuarioAtual, obter_usuario_atual
from app.config import cfg
from app.database import get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.models.schemas import DashboardResponse
from app.services import dashboard_service, dre_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse, summary="Dashboard agregado")
@limiter.limit("30/minute")
async def get_dashboard(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Retorna DRE agregado com alertas.
    Campos visíveis variam conforme o perfil (§4.5 do SDD).
    """
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dashboard_service.buscar_dashboard(inicio, fim, usuario, db)

    await dre_service.registrar_auditoria(
        usuario, "consulta_dashboard",
        {"inicio": str(inicio), "fim": str(fim), "latencia_ms": resultado.latencia_ms},
        request.client.host if request.client else None,
        __import__("app.database", fromlist=["get_supabase_admin"]).get_supabase_admin(),
    )

    return resultado


# ── INSIGHTS DE MERCADO ───────────────────────────────────────

_RSS_SOURCES = [
    "https://news.google.com/rss/search?q=mercado+seguros+corretoras+brasil+SUSEP&hl=pt-BR&gl=BR&ceid=BR:pt-BR",
    "https://news.google.com/rss/search?q=seguro+auto+vida+saude+brasil+2025&hl=pt-BR&gl=BR&ceid=BR:pt-BR",
]


async def _buscar_noticias_seguros() -> list[str]:
    """Busca manchetes recentes do mercado de seguros via Google News RSS."""
    noticias: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for url in _RSS_SOURCES:
                try:
                    resp = await client.get(url)
                    root = ET.fromstring(resp.content)
                    for item in root.findall(".//item")[:4]:
                        t = item.find("title")
                        if t is not None and t.text:
                            titulo = t.text.split(" - ")[0].strip()
                            if titulo and titulo not in noticias:
                                noticias.append(titulo)
                    if len(noticias) >= 6:
                        break
                except Exception:
                    continue
    except Exception:
        pass
    return noticias[:6]


@router.get("/insights", summary="Insights do mercado de seguros (streaming SSE)")
@limiter.limit("10/minute")
async def get_insights(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Busca manchetes recentes de seguros (Google News RSS) e usa Claude para
    sintetizar 3 insights práticos para corretoras brasileiras. Streaming SSE.
    """
    import anthropic as ant

    noticias = await _buscar_noticias_seguros()

    if noticias:
        bloco_noticias = (
            "Manchetes recentes do mercado segurador brasileiro:\n"
            + "\n".join(f"• {n}" for n in noticias)
            + "\n\nCom base nestas notícias e no seu conhecimento do setor,"
        )
    else:
        bloco_noticias = "Com base no seu conhecimento atualizado sobre o setor segurador brasileiro,"

    prompt = f"""{bloco_noticias} forneça exatamente 3 insights práticos e objetivos para corretoras de seguros.

Formato obrigatório (siga à risca):
**1. [Título curto]**
[2 linhas de análise prática e direta]

**2. [Título curto]**
[2 linhas]

**3. [Título curto]**
[2 linhas]

Foco: regulação SUSEP/CNSP, tendências de ramos (auto, vida, saúde, rural), tecnologia/insurtech, ou oportunidades de crescimento. Responda em português brasileiro."""

    api_key = cfg.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    cliente = ant.Anthropic(api_key=api_key)

    async def gerar():
        try:
            with cliente.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield f"data: {json.dumps({'conteudo': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'erro': 'Não foi possível carregar os insights.'})}\n\n"
        finally:
            yield 'data: {"fim": true}\n\n'

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
