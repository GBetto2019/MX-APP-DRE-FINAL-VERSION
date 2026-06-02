"""MX Seguros — DRE-IA | Router: /exports (PDF e Excel)"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.services import dre_service, export_service

router = APIRouter(prefix="/exports", tags=["Exportações"])


@router.get("/dre/xlsx", summary="Exportar DRE como Excel")
@limiter.limit("10/minute")
async def export_dre_excel(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    dre_data = await dre_service.buscar_dre(inicio, fim, usuario, db)
    xlsx_bytes = export_service.gerar_dre_excel(dre_data)

    nome = f"DRE_MX_{inicio}_{fim}.xlsx"
    await dre_service.registrar_auditoria(
        usuario, "export_dre_xlsx",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return StreamingResponse(
        xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/dre/pdf", summary="Exportar DRE como PDF")
@limiter.limit("10/minute")
async def export_dre_pdf(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    dre_data = await dre_service.buscar_dre(inicio, fim, usuario, db)
    pdf_bytes = export_service.gerar_dre_pdf(dre_data)

    nome = f"DRE_MX_{inicio}_{fim}.pdf"
    await dre_service.registrar_auditoria(
        usuario, "export_dre_pdf",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
