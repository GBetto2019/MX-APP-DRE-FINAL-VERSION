"""MX Seguros — DRE-IA | Router: /importacao (ETL via API — Task 3.5)"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin
from app.middleware.rate_limit import limiter
from app.services import dre_service
from app.services.etl_service import (
    LancamentoPreview, PreviewImportacao, ResultadoImportacao,
    efetivar_importacao, processar_preview,
)

router = APIRouter(prefix="/importacao", tags=["ETL / Importação"])

_ROLES_IMPORTACAO = ("admin", "contador")
_MAX_ARQUIVO_MB = 10


def _exigir_importacao(usuario: UsuarioAtual) -> None:
    if usuario.role not in _ROLES_IMPORTACAO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Importação restrita a Admin e Contador.",
        )


@router.post(
    "/balancete",
    response_model=PreviewImportacao,
    summary="Preview da importação de balancete Excel",
)
@limiter.limit("5/minute")
async def preview_balancete(
    request: Request,
    arquivo: UploadFile = File(..., description="Arquivo .xlsx do balancete"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Recebe um arquivo Excel do balancete, classifica os lançamentos
    e retorna um preview sem gravar nada no banco.

    Fluxo:
    1. Upload aqui → visualizar preview
    2. Confirmar em POST /importacao/balancete/confirmar
    """
    _exigir_importacao(usuario)

    if not arquivo.filename or not arquivo.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo deve ser .xlsx ou .xls",
        )

    conteudo = await arquivo.read()
    if len(conteudo) > _MAX_ARQUIVO_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {_MAX_ARQUIVO_MB}MB.",
        )

    try:
        preview = processar_preview(conteudo)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Falha ao ler arquivo Excel: {exc}",
        )

    await dre_service.registrar_auditoria(
        usuario, "preview_importacao",
        {"arquivo": arquivo.filename, "total_linhas": preview.total, "revisar": preview.revisar},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )

    return preview


@router.post(
    "/balancete/confirmar",
    response_model=ResultadoImportacao,
    summary="Efetivar importação do balancete",
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
async def confirmar_balancete(
    request: Request,
    payload: list[LancamentoPreview],
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Recebe a lista de lançamentos do preview (com possíveis ajustes manuais)
    e os insere em batch no banco.

    Apenas lançamentos com `mapeado=True` e `tipo != 'revisar'` são gravados.
    """
    _exigir_importacao(usuario)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lista de lançamentos vazia.",
        )

    if len(payload) > 5000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Máximo de 5.000 lançamentos por importação.",
        )

    db_admin = get_supabase_admin()
    resultado = await efetivar_importacao(payload, usuario.user_id, db_admin)

    await dre_service.registrar_auditoria(
        usuario, "importacao_confirmada",
        {
            "total_importado": resultado.total_importado,
            "despesas": resultado.despesas,
            "receitas": resultado.receitas,
            "ignorados": resultado.ignorados,
            "erros": len(resultado.erros),
        },
        request.client.host if request.client else None,
        db_admin,
    )

    return resultado
