"""
MX Seguros — DRE-IA | Router: /chat (streaming SSE) com histórico persistido.

Fluxo:
1. Usuário envia POST /chat com {"mensagem": "...", "conversa_id": null}
2. Backend valida JWT → extrai perfil
3. Orquestrador carrega histórico, chama Claude API com tool_use
4. Resposta streamada via Server-Sent Events
5. Frontend consome os eventos conforme chegam
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/chat", tags=["IA"])

MAX_PERGUNTA_CHARS = 2000


class ChatRequest(BaseModel):
    mensagem:    str
    conversa_id: UUID | None = None   # None = nova conversa

    @field_validator("mensagem")
    @classmethod
    def nao_vazia(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mensagem não pode ser vazia")
        if len(v) > MAX_PERGUNTA_CHARS:
            raise ValueError(f"Mensagem muito longa (máx {MAX_PERGUNTA_CHARS} caracteres)")
        return v


@router.post("", summary="Chat com IA (streaming SSE)")
@limiter.limit("10/minute")
async def chat(
    body:    ChatRequest,
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """
    Endpoint de chat com IA. Resposta via Server-Sent Events (SSE).

    Ao iniciar, emite `{"tipo": "conversa_id", "conversa_id": "uuid"}` para
    que o frontend possa retomar a mesma conversa em chamadas seguintes.

    **Tipos de evento:**
    - `{"tipo": "conversa_id", "conversa_id": "..."}` — ID da conversa (1º evento)
    - `{"tipo": "texto", "conteudo": "..."}` — chunk de texto do LLM
    - `{"tipo": "tool", "nome": "...", "status": "chamando|concluido"}` — tool sendo executada
    - `{"tipo": "erro", "mensagem": "..."}` — erro
    - `{"tipo": "fim"}` — resposta completa
    """
    from app.ai.orchestrator import processar_pergunta
    from app.middleware.limites import verificar_tenant_ativo, verificar_limite_msgs_ia

    tenant_id = getattr(request.state, "tenant_id", None)
    await verificar_tenant_ativo(tenant_id)
    await verificar_limite_msgs_ia(tenant_id, usuario.user_id)

    token    = request.headers.get("authorization", "").replace("Bearer ", "")
    db       = get_supabase_usuario(token)
    db_admin = get_supabase_admin()

    return StreamingResponse(
        processar_pergunta(body.mensagem, usuario, db, db_admin, body.conversa_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversas", summary="Listar histórico de conversas do usuário")
async def listar_conversas(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """
    Retorna as últimas 50 conversas do usuário autenticado, mais recentes primeiro.
    """
    from app.services.chat_service import listar_conversas as _listar

    db_admin = get_supabase_admin()
    conversas = await _listar(usuario.user_id, db_admin)
    return {"total": len(conversas), "items": conversas}


@router.get("/conversas/{conversa_id}/mensagens", summary="Carregar mensagens de uma conversa")
async def mensagens_conversa(
    conversa_id: UUID,
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """
    Retorna todas as mensagens de uma conversa do usuário autenticado.
    RLS garante que o usuário só acessa suas próprias conversas.
    """
    from app.services.chat_service import carregar_historico

    db_admin = get_supabase_admin()

    # Verificar que a conversa pertence ao usuário
    # maybe_single() retorna None (não obj.data) quando não há resultado
    resp = db_admin.table("chat_conversas")\
        .select("id")\
        .eq("id", str(conversa_id))\
        .eq("usuario_id", usuario.user_id)\
        .maybe_single()\
        .execute()

    encontrado = resp is not None and getattr(resp, "data", None)
    if not encontrado:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")

    mensagens = await carregar_historico(str(conversa_id), db_admin)
    return {"conversa_id": str(conversa_id), "total": len(mensagens), "mensagens": mensagens}
