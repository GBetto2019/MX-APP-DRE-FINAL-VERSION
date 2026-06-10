"""
MX Seguros — DRE-IA | Serviço de DRE e consultas financeiras.

REGRA FUNDAMENTAL: LLM nunca calcula DRE.
Todo cálculo é determinístico via funções SQL (dre_por_periodo etc.).
Este serviço chama essas funções via asyncpg (direto ao Postgres) quando
DATABASE_URL está configurada, ou via PostgREST (supabase-py) como fallback.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from supabase import Client

from app.auth import UsuarioAtual
from app.database import conn_as_user, get_asyncpg_pool, get_supabase_admin
from app.logging_config import get_logger
from app.models.schemas import (
    ComissaoItem, ComissoesResponse,
    DREResponse, LinhasDRE,
    EstornoItem, EstornosResponse,
    MetaItem, MetasResponse,
    ReceitaRamoItem, ReceitaRamoResponse,
    ReceitaTipoItem, ReceitaTipoResponse,
    RepasseItem, RepassesResponse,
)

logger = get_logger(__name__)


def _pool():
    return get_asyncpg_pool()


def _montar_dre_response(dados: dict, usuario: UsuarioAtual) -> DREResponse:
    """Constrói DREResponse a partir do dict retornado pelo SQL, aplicando filtros de perfil."""
    periodo = dados.get("periodo", {})

    def _decimal(chave: str) -> Decimal | None:
        val = dados.get(chave)
        return Decimal(str(val)) if val is not None else None

    dre = LinhasDRE(
        receita_bruta             = _decimal("receita_bruta")    or Decimal(0),
        estornos                  = _decimal("estornos")         or Decimal(0),
        impostos                  = _decimal("impostos")         or Decimal(0),
        receita_liquida           = None if usuario.role == "comercial"              else _decimal("receita_liquida"),
        repasses_produtores       = _decimal("repasses_produtores"),
        margem_contribuicao       = None if usuario.role == "comercial"              else _decimal("margem_contribuicao"),
        despesas_fixas            = None if usuario.role in ("gestor", "comercial")  else _decimal("despesas_fixas"),
        ebitda                    = None if usuario.role in ("gestor", "comercial")  else _decimal("ebitda"),
        despesas_nao_operacionais = None if usuario.role in ("gestor", "comercial")  else _decimal("despesas_nao_operacionais"),
        resultado_liquido         = None if usuario.role in ("gestor", "comercial")  else _decimal("resultado_liquido"),
    )
    return DREResponse(periodo=periodo, dre=dre, perfil=usuario.role)


async def _buscar_snapshot_fechamento(inicio: date) -> dict | None:
    """
    Retorna o snapshot do DRE se o período estiver fechado (não reaberto).
    Usa db_admin para acessar fechamentos (tabela restrita).
    """
    db_admin = get_supabase_admin()
    competencia = date(inicio.year, inicio.month, 1).isoformat()
    resp = db_admin.table("fechamentos") \
        .select("snapshot_dre") \
        .eq("competencia", competencia) \
        .is_("reaberto_em", "null") \
        .maybe_single() \
        .execute()

    if resp is not None and getattr(resp, "data", None):
        return resp.data.get("snapshot_dre")
    return None


# ── DRE ───────────────────────────────────────────────────────

async def buscar_dre(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> DREResponse:
    """
    DRE Híbrido (Task 3.2):
    - Período fechado → retorna snapshot imutável (< 10ms, sem query no banco).
    - Período aberto  → calcula em tempo real via SQL.
    """
    # Verifica se o mês está fechado (apenas para períodos de 1 mês)
    mesmo_mes = (inicio.year == fim.year and inicio.month == fim.month)
    if mesmo_mes:
        snapshot = await _buscar_snapshot_fechamento(inicio)
        if snapshot:
            logger.info("dre_snapshot_usado", competencia=inicio.isoformat(), usuario_id=usuario.user_id)
            return _montar_dre_response(snapshot, usuario)

    # Real-time
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            dados = await conn.fetchval(
                "SELECT dre_por_periodo($1::date, $2::date)",
                inicio, fim,
            ) or {}
    else:
        resp = db.rpc("dre_por_periodo", {
            "p_inicio": inicio.isoformat(),
            "p_fim":    fim.isoformat(),
        }).execute()
        dados = resp.data or {}

    return _montar_dre_response(dados, usuario)


# ── COMISSÕES ─────────────────────────────────────────────────

async def buscar_comissoes(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> ComissoesResponse:
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            rows = await conn.fetch(
                "SELECT id, apolice_id, tipo, valor, percentual, competencia, recebida_em "
                "FROM comissoes "
                "WHERE competencia >= $1 AND competencia <= $2 "
                "ORDER BY competencia DESC",
                inicio, fim,
            )
            items = [ComissaoItem(**dict(r)) for r in rows]
    else:
        resp = db.table("comissoes") \
            .select("*") \
            .gte("competencia", inicio.isoformat()) \
            .lte("competencia", fim.isoformat()) \
            .order("competencia", desc=True) \
            .execute()
        items = [ComissaoItem(**row) for row in (resp.data or [])]

    soma = sum(i.valor for i in items)
    return ComissoesResponse(total=len(items), items=items, soma_total=soma)


# ── ESTORNOS ──────────────────────────────────────────────────

async def buscar_estornos(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> EstornosResponse:
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            rows = await conn.fetch(
                "SELECT id, apolice_id, valor, competencia_estorno AS competencia, motivo "
                "FROM estornos "
                "WHERE competencia_estorno >= $1 AND competencia_estorno <= $2 "
                "ORDER BY competencia_estorno DESC",
                inicio, fim,
            )
            items = [EstornoItem(
                id=str(r["id"]),
                apolice_id=str(r["apolice_id"]) if r.get("apolice_id") else None,
                valor=Decimal(str(r["valor"])),
                competencia=r["competencia"],
                motivo=r.get("motivo"),
            ) for r in rows]
    else:
        resp = (
            db.table("estornos")
            .select("id, apolice_id, valor, competencia_estorno, motivo")
            .gte("competencia_estorno", inicio.isoformat())
            .lte("competencia_estorno", fim.isoformat())
            .order("competencia_estorno", desc=True)
            .execute()
        )
        items = [EstornoItem(
            id=row["id"],
            apolice_id=row.get("apolice_id"),
            valor=Decimal(str(row["valor"])),
            competencia=row["competencia_estorno"],
            motivo=row.get("motivo"),
        ) for row in (resp.data or [])]

    total = sum(i.valor for i in items)
    return EstornosResponse(items=items, total=total, taxa_estorno=0.0, alerta_5pct=False)


# ── METAS ─────────────────────────────────────────────────────

async def buscar_metas(
    competencia: date,
    usuario: UsuarioAtual,
    db: Client,
) -> MetasResponse:
    comp = date(competencia.year, competencia.month, 1)
    items: list[MetaItem] = []
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            rows = await conn.fetch(
                "SELECT * FROM atingimento_metas($1::date)", comp,
            )
            for r in rows:
                d = dict(r)
                items.append(MetaItem(**{k: str(v) if v is not None else None for k, v in d.items()}))
    else:
        try:
            resp = db.rpc("atingimento_metas", {"p_competencia": comp.isoformat()}).execute()
            for row in (resp.data or []):
                items.append(MetaItem(**row))
        except Exception as e:
            logger.warning("buscar_metas_falhou", erro=str(e))

    return MetasResponse(competencia=comp, items=items)


# ── REPASSES ──────────────────────────────────────────────────

async def buscar_repasses(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> RepassesResponse:
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            rows = await conn.fetch(
                "SELECT id, comissao_id, produtor_id, valor, percentual, competencia, pago_em, status "
                "FROM repasses "
                "WHERE competencia >= $1 AND competencia <= $2 "
                "ORDER BY competencia DESC",
                inicio, fim,
            )
            items = [RepasseItem(
                id=str(r["id"]),
                comissao_id=str(r["comissao_id"]) if r.get("comissao_id") else None,
                produtor_id=str(r["produtor_id"]) if r.get("produtor_id") else None,
                valor=Decimal(str(r["valor"])),
                percentual=Decimal(str(r["percentual"])) if r.get("percentual") else None,
                competencia=r["competencia"],
                pago_em=r.get("pago_em"),
                status=r.get("status", "previsto"),
            ) for r in rows]
    else:
        resp = (
            db.table("repasses")
            .select("id, comissao_id, produtor_id, valor, percentual, competencia, pago_em, status")
            .gte("competencia", inicio.isoformat())
            .lte("competencia", fim.isoformat())
            .order("competencia", desc=True)
            .execute()
        )
        items = [RepasseItem(
            id=row["id"],
            comissao_id=row.get("comissao_id"),
            produtor_id=row.get("produtor_id"),
            valor=Decimal(str(row["valor"])),
            percentual=Decimal(str(row["percentual"])) if row.get("percentual") else None,
            competencia=row["competencia"],
            pago_em=row.get("pago_em"),
            status=row.get("status", "previsto"),
        ) for row in (resp.data or [])]

    soma_previsto = sum(i.valor for i in items if i.status == "previsto")
    soma_pago = sum(i.valor for i in items if i.status == "pago")
    return RepassesResponse(items=items, soma_previsto=soma_previsto, soma_pago=soma_pago)


# ── RECEITA POR RAMO ──────────────────────────────────────────

async def buscar_receita_por_ramo(
    inicio: date,
    fim: date,
    db: Client,
    usuario_id: str = "system",
) -> ReceitaRamoResponse:
    try:
        resp = db.rpc("receita_por_ramo", {
            "p_inicio": inicio.isoformat(),
            "p_fim":    fim.isoformat(),
        }).execute()
        rows: list = resp.data if isinstance(resp.data, list) else []
    except Exception as exc:
        logger.error("erro_receita_por_ramo", exc=str(exc), exc_info=True)
        rows = []

    items = []
    total = Decimal(0)
    for row in rows:
        if row:
            item = ReceitaRamoItem(
                ramo_codigo=row["ramo_codigo"],
                ramo_nome=row["ramo_nome"],
                receita_total=Decimal(str(row["receita_total"])),
                num_apolices=int(row["num_apolices"]),
            )
            items.append(item)
            total += item.receita_total

    return ReceitaRamoResponse(
        periodo={"inicio": inicio, "fim": fim},
        items=items,
        total=total,
    )


# ── RECEITA POR TIPO DE LANÇAMENTO ───────────────────────────

async def buscar_receita_por_tipo(
    inicio: date,
    fim: date,
    db: Client,
) -> ReceitaTipoResponse:
    try:
        resp = (
            db.table("despesas")
            .select("valor, tipos_lancamento(nome)")
            .gte("competencia", inicio.isoformat())
            .lte("competencia", fim.isoformat())
            .neq("status", "excluida")
            .neq("status", "rejeitada")
            .execute()
        )
        rows: list = resp.data if isinstance(resp.data, list) else []
    except Exception as exc:
        logger.error("erro_lancamentos_por_tipo", exc=str(exc), exc_info=True)
        rows = []

    agregado: dict[str, dict] = {}
    for row in rows:
        nome = ((row.get("tipos_lancamento") or {}).get("nome") or row.get("categoria") or "Outros")
        valor = Decimal(str(row.get("valor", 0)))
        if nome not in agregado:
            agregado[nome] = {"receita_total": Decimal(0), "num_lancamentos": 0}
        agregado[nome]["receita_total"] += valor
        agregado[nome]["num_lancamentos"] += 1

    items = [
        ReceitaTipoItem(tipo_nome=nome, **dados)
        for nome, dados in sorted(agregado.items(), key=lambda x: x[1]["receita_total"], reverse=True)
    ]
    total = sum(i.receita_total for i in items)
    return ReceitaTipoResponse(periodo={"inicio": inicio, "fim": fim}, items=items, total=total)


# ── AUDIT LOG ─────────────────────────────────────────────────

async def registrar_auditoria(
    usuario: UsuarioAtual,
    acao: str,
    detalhes: dict,
    ip: str | None,
    db_admin: Client,
) -> None:
    """Registra toda interação no audit_log (append-only), incluindo tenant_id."""
    try:
        entrada: dict = {
            "usuario_id": usuario.user_id,
            "acao":       acao,
            "detalhes":   detalhes,
            "ip":         ip,
        }
        # Sprint 4: incluir tenant_id se disponível (graceful se coluna não existir)
        if getattr(usuario, "tenant_id", None):
            entrada["tenant_id"] = usuario.tenant_id
        db_admin.table("audit_log").insert(entrada).execute()
    except Exception as e:
        err = str(e)
        if "tenant_id" in err or "schema cache" in err:
            # Fallback: inserir sem tenant_id (migration pendente)
            try:
                db_admin.table("audit_log").insert({
                    "usuario_id": usuario.user_id,
                    "acao":       acao,
                    "detalhes":   detalhes,
                    "ip":         ip,
                }).execute()
            except Exception as e2:
                logger.error("Falha ao registrar audit_log: %s", e2)
        else:
            logger.error("Falha ao registrar audit_log: %s", e)
