"""
MX Seguros — DRE-IA | Serviço de Lançamentos e Configurações Financeiras.

Gerencia CRUD de despesas manuais, receitas_outras,
bancos, centros de custo e tipos de lançamento.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from supabase import Client

from app.auth import UsuarioAtual
from app.models.schemas import (
    BancoCreate, BancoItem, BancoUpdate,
    CentroCustoCreate, CentroCustoItem, CentroCustoUpdate,
    DespesaCreate, DespesaItem, DespesasResponse,
    ReceitaItem, ReceitaOutraCreate, ReceitasResponse,
    TipoLancamentoCreate, TipoLancamentoItem, TipoLancamentoUpdate,
)

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────

def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal(0)


# ══════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ══════════════════════════════════════════════════════════════

# ── Bancos ────────────────────────────────────────────────────

async def listar_bancos(db: Client) -> list[BancoItem]:
    resp = db.table("bancos").select("id, nome, ativo").order("nome").execute()
    return [BancoItem(**r) for r in (resp.data or [])]


async def criar_banco(payload: BancoCreate, db: Client) -> BancoItem:
    resp = db.table("bancos").insert({"nome": payload.nome}).execute()
    row = resp.data[0]
    return BancoItem(**row)


async def atualizar_banco(banco_id: UUID, payload: BancoUpdate, db: Client) -> BancoItem:
    dados = payload.model_dump(exclude_none=True)
    resp = db.table("bancos").update(dados).eq("id", str(banco_id)).execute()
    row = resp.data[0]
    return BancoItem(**row)


# ── Centros de Custo ──────────────────────────────────────────

async def listar_centros_custo(db: Client) -> list[CentroCustoItem]:
    resp = db.table("centros_custo").select("id, nome, codigo, ativo").order("nome").execute()
    return [CentroCustoItem(**r) for r in (resp.data or [])]


async def criar_centro_custo(payload: CentroCustoCreate, db: Client) -> CentroCustoItem:
    resp = db.table("centros_custo").insert({
        "nome":   payload.nome,
        "codigo": payload.codigo,
    }).execute()
    row = resp.data[0]
    return CentroCustoItem(**row)


async def atualizar_centro_custo(
    centro_id: UUID, payload: CentroCustoUpdate, db: Client
) -> CentroCustoItem:
    dados = payload.model_dump(exclude_none=True)
    resp = db.table("centros_custo").update(dados).eq("id", str(centro_id)).execute()
    row = resp.data[0]
    return CentroCustoItem(**row)


# ── Tipos de Lançamento ───────────────────────────────────────

async def listar_tipos_lancamento(
    db: Client, natureza: str | None = None
) -> list[TipoLancamentoItem]:
    query = db.table("tipos_lancamento").select(
        "id, nome, natureza, categoria, custo_tipo, ativo"
    ).order("natureza").order("nome")
    if natureza:
        query = query.eq("natureza", natureza)
    resp = query.execute()
    return [TipoLancamentoItem(**r) for r in (resp.data or [])]


async def criar_tipo_lancamento(
    payload: TipoLancamentoCreate, db: Client
) -> TipoLancamentoItem:
    resp = db.table("tipos_lancamento").insert({
        "nome":       payload.nome,
        "natureza":   payload.natureza,
        "categoria":  payload.categoria,
        "custo_tipo": payload.custo_tipo,
    }).execute()
    row = resp.data[0]
    return TipoLancamentoItem(**row)


async def atualizar_tipo_lancamento(
    tipo_id: UUID, payload: TipoLancamentoUpdate, db: Client
) -> TipoLancamentoItem:
    dados = payload.model_dump(exclude_none=True)
    resp = db.table("tipos_lancamento").update(dados).eq("id", str(tipo_id)).execute()
    row = resp.data[0]
    return TipoLancamentoItem(**row)


async def desativar_tipo_lancamento(tipo_id: UUID, db: Client) -> None:
    db.table("tipos_lancamento").update({"ativo": False}).eq("id", str(tipo_id)).execute()


# ══════════════════════════════════════════════════════════════
# LANÇAMENTOS
# ══════════════════════════════════════════════════════════════

# ── Despesas ──────────────────────────────────────────────────

async def buscar_despesas(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
    centro_custo: str | None = None,
    banco_id: str | None = None,
) -> DespesasResponse:
    query = (
        db.table("despesas")
        .select(
            "id, categoria, subcategoria, descricao, valor, competencia, "
            "paga_em, centro_custo, recorrente, parcela_atual, parcela_total, "
            "criado_em, tipo_lancamento_id, banco_id, "
            "status, criado_por, aprovado_por, aprovado_em, rejeitado_motivo, "
            "tipos_lancamento(nome), bancos(nome)"
        )
        .neq("status", "excluida")
        .gte("competencia", inicio.isoformat())
        .lte("competencia", fim.isoformat())
        .order("competencia", desc=True)
    )
    if centro_custo:
        query = query.eq("centro_custo", centro_custo)
    if banco_id:
        query = query.eq("banco_id", banco_id)

    resp = query.execute()
    items = []
    for row in (resp.data or []):
        tipo_nome  = (row.get("tipos_lancamento") or {}).get("nome")
        banco_nome = (row.get("bancos") or {}).get("nome")
        items.append(DespesaItem(
            id=row["id"],
            tipo_lancamento_id=row.get("tipo_lancamento_id"),
            tipo_nome=tipo_nome,
            banco_id=row.get("banco_id"),
            banco_nome=banco_nome,
            categoria=row.get("categoria"),
            subcategoria=row.get("subcategoria", ""),
            descricao=row["descricao"],
            valor=_dec(row["valor"]),
            competencia=row["competencia"],
            paga_em=row.get("paga_em"),
            centro_custo=row.get("centro_custo", "matriz"),
            recorrente=bool(row.get("recorrente", False)),
            parcela_atual=row.get("parcela_atual"),
            parcela_total=row.get("parcela_total"),
            criado_em=row.get("criado_em"),
            status=row.get("status", "aprovada"),
            criado_por=row.get("criado_por"),
            aprovado_por=row.get("aprovado_por"),
            aprovado_em=row.get("aprovado_em"),
            rejeitado_motivo=row.get("rejeitado_motivo"),
        ))

    soma = sum(i.valor for i in items)
    pendentes = sum(1 for i in items if i.status == "pendente")
    return DespesasResponse(total=len(items), items=items, soma_total=soma, total_pendentes=pendentes)


def _verificar_periodo_aberto(competencia: date, db: Client) -> None:
    """Lança 409 se o mês estiver fechado — impede lançamentos em período congelado."""
    from fastapi import HTTPException, status as http_status
    competencia_mes = date(competencia.year, competencia.month, 1)
    resp = db.table("fechamentos") \
        .select("id") \
        .eq("competencia", competencia_mes.isoformat()) \
        .is_("reaberto_em", "null") \
        .maybe_single() \
        .execute()
    if resp is not None and getattr(resp, "data", None):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"Período {competencia_mes.strftime('%m/%Y')} está fechado. "
                "Reabra o fechamento antes de lançar."
            ),
        )


async def criar_despesa(
    payload: DespesaCreate,
    usuario: UsuarioAtual,
    db: Client,
) -> DespesaItem:
    # Bloqueia escrita em período fechado (Task 3.1)
    _verificar_periodo_aberto(payload.competencia, db)

    # Se tipo_lancamento_id informado, busca categoria para backward compat com DRE
    categoria = payload.categoria
    if payload.tipo_lancamento_id and not categoria:
        resp_tipo = db.table("tipos_lancamento").select("categoria").eq(
            "id", str(payload.tipo_lancamento_id)
        ).single().execute()
        if resp_tipo.data:
            categoria = resp_tipo.data.get("categoria")

    # admin e contador entram com aprovação imediata; demais ficam pendentes
    status_inicial = "aprovada" if usuario.role in ("admin", "contador") else "pendente"

    dados = {
        "subcategoria":  payload.subcategoria,
        "descricao":     payload.descricao,
        "valor":         str(payload.valor),
        "competencia":   payload.competencia.isoformat(),
        "centro_custo":  payload.centro_custo,
        "recorrente":    payload.recorrente,
        "criado_por":    usuario.user_id,
        "status":        status_inicial,
    }
    # Sprint 4: incluir tenant_id quando disponível
    if getattr(usuario, "tenant_id", None):
        dados["tenant_id"] = usuario.tenant_id
    if categoria:
        dados["categoria"] = categoria
    if payload.tipo_lancamento_id:
        dados["tipo_lancamento_id"] = str(payload.tipo_lancamento_id)
    if payload.banco_id:
        dados["banco_id"] = str(payload.banco_id)
    if payload.paga_em:
        dados["paga_em"] = payload.paga_em.isoformat()
    if payload.parcela_atual:
        dados["parcela_atual"] = payload.parcela_atual
    if payload.parcela_total:
        dados["parcela_total"] = payload.parcela_total

    resp = db.table("despesas").insert(dados).execute()
    row = resp.data[0]

    tipo_nome  = None
    banco_nome = None
    if payload.tipo_lancamento_id:
        r = db.table("tipos_lancamento").select("nome").eq(
            "id", str(payload.tipo_lancamento_id)
        ).single().execute()
        tipo_nome = (r.data or {}).get("nome")
    if payload.banco_id:
        r = db.table("bancos").select("nome").eq(
            "id", str(payload.banco_id)
        ).single().execute()
        banco_nome = (r.data or {}).get("nome")

    return DespesaItem(
        id=row["id"],
        tipo_lancamento_id=row.get("tipo_lancamento_id"),
        tipo_nome=tipo_nome,
        banco_id=row.get("banco_id"),
        banco_nome=banco_nome,
        categoria=row.get("categoria"),
        subcategoria=row.get("subcategoria", ""),
        descricao=row["descricao"],
        valor=_dec(row["valor"]),
        competencia=row["competencia"],
        paga_em=row.get("paga_em"),
        centro_custo=row.get("centro_custo", "matriz"),
        recorrente=bool(row.get("recorrente", False)),
        parcela_atual=row.get("parcela_atual"),
        parcela_total=row.get("parcela_total"),
        criado_em=row.get("criado_em"),
        status=row.get("status", status_inicial),
        criado_por=row.get("criado_por"),
        aprovado_por=row.get("aprovado_por"),
        aprovado_em=row.get("aprovado_em"),
        rejeitado_motivo=row.get("rejeitado_motivo"),
    )


async def aprovar_despesa(despesa_id: UUID, usuario: UsuarioAtual, db: Client) -> DespesaItem:
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc).isoformat()
    resp = (
        db.table("despesas")
        .update({
            "status":       "aprovada",
            "aprovado_por": usuario.user_id,
            "aprovado_em":  agora,
        })
        .eq("id", str(despesa_id))
        .neq("status", "excluida")
        .execute()
    )
    if not resp.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    row = resp.data[0]
    return _row_para_despesa_item(row)


async def rejeitar_despesa(
    despesa_id: UUID,
    motivo: str,
    usuario: UsuarioAtual,
    db: Client,
) -> DespesaItem:
    resp = (
        db.table("despesas")
        .update({
            "status":            "rejeitada",
            "aprovado_por":      usuario.user_id,
            "rejeitado_motivo":  motivo,
        })
        .eq("id", str(despesa_id))
        .neq("status", "excluida")
        .execute()
    )
    if not resp.data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Despesa não encontrada.")
    row = resp.data[0]
    return _row_para_despesa_item(row)


def _row_para_despesa_item(row: dict) -> DespesaItem:
    return DespesaItem(
        id=row["id"],
        tipo_lancamento_id=row.get("tipo_lancamento_id"),
        tipo_nome=None,
        banco_id=row.get("banco_id"),
        banco_nome=None,
        categoria=row.get("categoria"),
        subcategoria=row.get("subcategoria", ""),
        descricao=row["descricao"],
        valor=_dec(row["valor"]),
        competencia=row["competencia"],
        paga_em=row.get("paga_em"),
        centro_custo=row.get("centro_custo", "matriz"),
        recorrente=bool(row.get("recorrente", False)),
        parcela_atual=row.get("parcela_atual"),
        parcela_total=row.get("parcela_total"),
        criado_em=row.get("criado_em"),
        status=row.get("status", "pendente"),
        criado_por=row.get("criado_por"),
        aprovado_por=row.get("aprovado_por"),
        aprovado_em=row.get("aprovado_em"),
        rejeitado_motivo=row.get("rejeitado_motivo"),
    )


async def deletar_despesa(despesa_id: UUID, db: Client) -> None:
    db.table("despesas").update({"status": "excluida"}).eq("id", str(despesa_id)).execute()


# ── Receitas (comissões + manuais) ────────────────────────────

async def buscar_receitas(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
    centro_custo: str | None = None,
    banco_id: str | None = None,
) -> ReceitasResponse:
    items: list[ReceitaItem] = []
    soma_comissoes = Decimal(0)
    soma_manuais   = Decimal(0)

    # 1. Comissões (ETL / automáticas) — sem filtro de banco/centro pois comissoes não tem esses campos
    q_com = (
        db.table("comissoes")
        .select("id, valor, competencia, recebida_em, tipo, apolice_id")
        .gte("competencia", inicio.isoformat())
        .lte("competencia", fim.isoformat())
        .order("competencia", desc=True)
    )
    if not banco_id and not centro_custo:  # só exibe comissões quando não há filtro específico
        resp_com = q_com.execute()
        for row in (resp_com.data or []):
            v = _dec(row["valor"])
            soma_comissoes += v
            items.append(ReceitaItem(
                id=row["id"],
                origem="comissao",
                tipo_nome=row.get("tipo"),
                descricao=f"Comissão — {row.get('tipo', 'padrão')}",
                valor=v,
                competencia=row["competencia"],
                recebido_em=row.get("recebida_em"),
                centro_custo="matriz",
            ))

    # 2. Receitas manuais
    q_rec = (
        db.table("receitas_outras")
        .select(
            "id, descricao, valor, competencia, recebido_em, centro_custo, "
            "observacao, tipo_lancamento_id, banco_id, "
            "tipos_lancamento(nome), bancos(nome)"
        )
        .gte("competencia", inicio.isoformat())
        .lte("competencia", fim.isoformat())
        .order("competencia", desc=True)
    )
    if centro_custo:
        q_rec = q_rec.eq("centro_custo", centro_custo)
    if banco_id:
        q_rec = q_rec.eq("banco_id", banco_id)

    resp_rec = q_rec.execute()
    for row in (resp_rec.data or []):
        v = _dec(row["valor"])
        soma_manuais += v
        tipo_nome  = (row.get("tipos_lancamento") or {}).get("nome")
        banco_nome = (row.get("bancos") or {}).get("nome")
        items.append(ReceitaItem(
            id=row["id"],
            origem="manual",
            tipo_lancamento_id=row.get("tipo_lancamento_id"),
            tipo_nome=tipo_nome,
            banco_id=row.get("banco_id"),
            banco_nome=banco_nome,
            descricao=row["descricao"],
            valor=v,
            competencia=row["competencia"],
            recebido_em=row.get("recebido_em"),
            centro_custo=row.get("centro_custo", "matriz"),
            observacao=row.get("observacao"),
        ))

    # Ordena por competência desc
    items.sort(key=lambda x: x.competencia, reverse=True)

    return ReceitasResponse(
        total=len(items),
        items=items,
        soma_comissoes=soma_comissoes,
        soma_manuais=soma_manuais,
        soma_total=soma_comissoes + soma_manuais,
    )


async def criar_receita_outra(
    payload: ReceitaOutraCreate,
    usuario: UsuarioAtual,
    db: Client,
) -> ReceitaItem:
    _verificar_periodo_aberto(payload.competencia, db)

    dados: dict = {
        "descricao":    payload.descricao,
        "valor":        str(payload.valor),
        "competencia":  payload.competencia.isoformat(),
        "centro_custo": payload.centro_custo,
    }
    if getattr(usuario, "tenant_id", None):
        dados["tenant_id"] = usuario.tenant_id
    if payload.tipo_lancamento_id:
        dados["tipo_lancamento_id"] = str(payload.tipo_lancamento_id)
    if payload.banco_id:
        dados["banco_id"] = str(payload.banco_id)
    if payload.recebido_em:
        dados["recebido_em"] = payload.recebido_em.isoformat()
    if payload.observacao:
        dados["observacao"] = payload.observacao

    resp = db.table("receitas_outras").insert(dados).execute()
    row = resp.data[0]

    tipo_nome  = None
    banco_nome = None
    if payload.tipo_lancamento_id:
        r = db.table("tipos_lancamento").select("nome").eq(
            "id", str(payload.tipo_lancamento_id)
        ).single().execute()
        tipo_nome = (r.data or {}).get("nome")
    if payload.banco_id:
        r = db.table("bancos").select("nome").eq(
            "id", str(payload.banco_id)
        ).single().execute()
        banco_nome = (r.data or {}).get("nome")

    return ReceitaItem(
        id=row["id"],
        origem="manual",
        tipo_lancamento_id=row.get("tipo_lancamento_id"),
        tipo_nome=tipo_nome,
        banco_id=row.get("banco_id"),
        banco_nome=banco_nome,
        descricao=row["descricao"],
        valor=_dec(row["valor"]),
        competencia=row["competencia"],
        recebido_em=row.get("recebido_em"),
        centro_custo=row.get("centro_custo", "matriz"),
        observacao=row.get("observacao"),
    )


async def deletar_receita_outra(receita_id: UUID, db: Client) -> None:
    db.table("receitas_outras").delete().eq("id", str(receita_id)).execute()
