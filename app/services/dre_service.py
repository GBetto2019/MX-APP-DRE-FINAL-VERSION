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
    DREResponse, EstornoItem, EstornosResponse,
    LinhasDRE, MetaItem, MetasResponse, MetaCreate, MetaUpdate, MetaCadastroItem,
    RepasseItem, RepassesResponse,
    ReceitaRamoItem, ReceitaRamoResponse,
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
                "SELECT id, apolice_id, valor, motivo, competencia_original, competencia_estorno "
                "FROM estornos "
                "WHERE competencia_estorno >= $1 AND competencia_estorno <= $2 "
                "ORDER BY competencia_estorno DESC",
                inicio, fim,
            )
            taxa_dados = await conn.fetchval(
                "SELECT taxa_estorno($1::date, $2::date)",
                inicio, fim,
            ) or {}
            items = [EstornoItem(**dict(r)) for r in rows]
    else:
        resp_estornos = db.table("estornos") \
            .select("*") \
            .gte("competencia_estorno", inicio.isoformat()) \
            .lte("competencia_estorno", fim.isoformat()) \
            .order("competencia_estorno", desc=True) \
            .execute()
        taxa_resp = db.rpc("taxa_estorno", {
            "p_inicio": inicio.isoformat(),
            "p_fim":    fim.isoformat(),
        }).execute()
        taxa_dados = taxa_resp.data or {}
        items = [EstornoItem(**row) for row in (resp_estornos.data or [])]

    soma = sum(i.valor for i in items)
    return EstornosResponse(
        total=len(items),
        items=items,
        soma_total=soma,
        taxa_estorno=Decimal(str(taxa_dados.get("taxa_estorno", 0))),
        alerta_5pct=bool(taxa_dados.get("alerta_5pct", False)),
    )


# ── METAS ─────────────────────────────────────────────────────

async def buscar_metas(
    competencia: date,
    usuario: UsuarioAtual,
    db: Client,
) -> MetasResponse:
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            result = await conn.fetchval(
                "SELECT atingimento_metas($1::date)",
                competencia,
            ) or []
            rows = result if isinstance(result, list) else [result]
    else:
        resp = db.rpc("atingimento_metas", {
            "p_competencia": competencia.isoformat(),
        }).execute()
        rows = resp.data or []

    items = []
    for row in rows:
        if row:
            items.append(MetaItem(
                meta_id=row["meta_id"],
                escopo=row["escopo"],
                escopo_id=row.get("escopo_id"),
                metrica=row["metrica"],
                valor_alvo=Decimal(str(row["valor_alvo"])),
                valor_atual=Decimal(str(row["valor_atual"])),
                percentual=Decimal(str(row["percentual"])),
                atingida=bool(row["atingida"]),
            ))

    return MetasResponse(competencia=competencia, items=items)


# ── METAS CRUD (admin) ─────────────────────────────────────────

async def listar_metas_cadastro(
    competencia: date,
    db: Client,
) -> list[MetaCadastroItem]:
    resp = (
        db.table("metas")
        .select("id, escopo, escopo_id, competencia, valor_alvo, metrica, criado_em")
        .eq("competencia", competencia.isoformat())
        .order("escopo")
        .order("escopo_id")
        .execute()
    )
    return [MetaCadastroItem(**row) for row in (resp.data or [])]


async def criar_meta(
    payload: MetaCreate,
    db: Client,
) -> MetaCadastroItem:
    dados: dict = {
        "escopo":      payload.escopo,
        "competencia": payload.competencia.isoformat(),
        "valor_alvo":  float(payload.valor_alvo),
        "metrica":     payload.metrica,
    }
    if payload.escopo_id:
        dados["escopo_id"] = str(payload.escopo_id)
    resp = db.table("metas").insert(dados).execute()
    return MetaCadastroItem(**resp.data[0])


async def atualizar_meta(
    meta_id: UUID,
    payload: MetaUpdate,
    db: Client,
) -> MetaCadastroItem:
    dados = payload.model_dump(exclude_none=True)
    if "valor_alvo" in dados:
        dados["valor_alvo"] = float(dados["valor_alvo"])
    resp = db.table("metas").update(dados).eq("id", str(meta_id)).execute()
    return MetaCadastroItem(**resp.data[0])


async def deletar_meta(meta_id: UUID, db: Client) -> None:
    db.table("metas").delete().eq("id", str(meta_id)).execute()


# ── REPASSES ──────────────────────────────────────────────────

async def buscar_repasses(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
    produtor_id: str | None = None,
) -> RepassesResponse:
    if _pool():
        async with conn_as_user(usuario.user_id) as conn:
            if produtor_id:
                rows = await conn.fetch(
                    "SELECT id, comissao_id, produtor_id, valor, percentual, "
                    "competencia, pago_em, status "
                    "FROM repasses "
                    "WHERE competencia >= $1 AND competencia <= $2 AND produtor_id = $3 "
                    "ORDER BY competencia DESC",
                    inicio, fim, produtor_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, comissao_id, produtor_id, valor, percentual, "
                    "competencia, pago_em, status "
                    "FROM repasses "
                    "WHERE competencia >= $1 AND competencia <= $2 "
                    "ORDER BY competencia DESC",
                    inicio, fim,
                )
            items = [RepasseItem(**dict(r)) for r in rows]
    else:
        query = db.table("repasses") \
            .select("*") \
            .gte("competencia", inicio.isoformat()) \
            .lte("competencia", fim.isoformat())
        if produtor_id:
            query = query.eq("produtor_id", produtor_id)
        resp = query.order("competencia", desc=True).execute()
        items = [RepasseItem(**row) for row in (resp.data or [])]

    soma_previsto = sum(i.valor for i in items if i.status == "previsto")
    soma_pago = sum(i.valor for i in items if i.status == "pago")
    return RepassesResponse(
        total=len(items),
        items=items,
        soma_previsto=soma_previsto,
        soma_pago=soma_pago,
    )


# ── RECEITA POR RAMO ──────────────────────────────────────────

async def buscar_receita_por_ramo(
    inicio: date,
    fim: date,
    db: Client,
) -> ReceitaRamoResponse:
    if _pool():
        async with conn_as_user("system") as conn:
            result = await conn.fetchval(
                "SELECT receita_por_ramo($1::date, $2::date)",
                inicio, fim,
            ) or {}
            rows = result.get("items", []) if isinstance(result, dict) else (result if isinstance(result, list) else [])
    else:
        resp = db.rpc("receita_por_ramo", {
            "p_inicio": inicio.isoformat(),
            "p_fim":    fim.isoformat(),
        }).execute()
        result = resp.data or {}
        rows = result.get("items", []) if isinstance(result, dict) else []

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
