"""Dependência compartilhada para validar intervalos de período nos endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Query, status


MAX_PERIODO_DIAS = 365


def validar_periodo(
    inicio: date = Query(..., description="Data início (YYYY-MM-DD)"),
    fim: date = Query(..., description="Data fim (YYYY-MM-DD)"),
) -> tuple[date, date]:
    if fim < inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'fim' deve ser igual ou posterior a 'inicio'.",
        )
    if (fim - inicio).days > MAX_PERIODO_DIAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Período máximo permitido: 12 meses (365 dias).",
        )
    return inicio, fim
