"""
MX Seguros — DRE-IA | Schemas Pydantic (request/response).
Valores monetários: sempre Decimal, nunca float.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr


# ── BASE ──────────────────────────────────────────────────────

class RespostaBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ── DRE ───────────────────────────────────────────────────────

class DRERequest(BaseModel):
    inicio: date
    fim: date

    @field_validator("fim")
    @classmethod
    def fim_apos_inicio(cls, fim: date, info) -> date:
        inicio = info.data.get("inicio")
        if inicio and fim < inicio:
            raise ValueError("'fim' deve ser igual ou posterior a 'inicio'")
        return fim


class LinhasDRE(RespostaBase):
    receita_bruta:             Decimal
    estornos:                  Decimal
    impostos:                  Decimal
    receita_liquida:           Decimal | None = None  # None para perfis sem permissão
    repasses_produtores:       Decimal | None = None
    margem_contribuicao:       Decimal | None = None
    despesas_fixas:            Decimal | None = None  # bloqueado para gestor/comercial
    ebitda:                    Decimal | None = None  # bloqueado para gestor/comercial
    despesas_nao_operacionais: Decimal | None = None
    resultado_liquido:         Decimal | None = None


class DREResponse(RespostaBase):
    periodo: dict[str, date]
    dre:     LinhasDRE
    perfil:  str   # qual perfil gerou (campos podem ser None se sem permissão)


# ── COMISSÕES ─────────────────────────────────────────────────

class ComissaoItem(RespostaBase):
    id:           UUID
    apolice_id:   UUID
    tipo:         str
    valor:        Decimal
    percentual:   Decimal | None
    competencia:  date
    recebida_em:  date | None


class ComissoesResponse(RespostaBase):
    total:      int
    items:      list[ComissaoItem]
    soma_total: Decimal


# ── RECEITA POR RAMO ──────────────────────────────────────────

class ReceitaRamoItem(RespostaBase):
    ramo_codigo:   str
    ramo_nome:     str
    receita_total: Decimal
    num_apolices:  int


class ReceitaRamoResponse(RespostaBase):
    periodo:  dict[str, date]
    items:    list[ReceitaRamoItem]
    total:    Decimal


# ── RECEITA POR TIPO DE LANÇAMENTO ───────────────────────────

class ReceitaTipoItem(RespostaBase):
    tipo_nome:       str
    receita_total:   Decimal
    num_lancamentos: int


class ReceitaTipoResponse(RespostaBase):
    periodo: dict[str, date]
    items:   list[ReceitaTipoItem]
    total:   Decimal


# ── CONFIGURAÇÕES: BANCOS ─────────────────────────────────────

class BancoItem(RespostaBase):
    id:        UUID
    nome:      str
    ativo:     bool


class BancoCreate(RespostaBase):
    nome: str


class BancoUpdate(RespostaBase):
    nome:  str | None = None
    ativo: bool | None = None


# ── CONFIGURAÇÕES: CENTROS DE CUSTO ───────────────────────────

class CentroCustoItem(RespostaBase):
    id:     UUID
    nome:   str
    codigo: str
    ativo:  bool


class CentroCustoCreate(RespostaBase):
    nome:   str
    codigo: str


class CentroCustoUpdate(RespostaBase):
    nome:  str | None = None
    ativo: bool | None = None


# ── CONFIGURAÇÕES: TIPOS DE LANÇAMENTO ────────────────────────

class TipoLancamentoItem(RespostaBase):
    id:         UUID
    nome:       str
    natureza:   str   # 'despesa' | 'receita'
    categoria:  str | None
    custo_tipo: str | None
    ativo:      bool


class TipoLancamentoCreate(RespostaBase):
    nome:       str
    natureza:   str
    categoria:  str | None = None
    custo_tipo: str | None = None


class TipoLancamentoUpdate(RespostaBase):
    nome:       str | None = None
    categoria:  str | None = None
    custo_tipo: str | None = None
    ativo:      bool | None = None


# ── CONFIGURAÇÕES: USUÁRIOS ───────────────────────────────────

class UsuarioItem(RespostaBase):
    id:          UUID
    nome:        str
    email:       str
    role:        str
    equipe_id:   UUID | None
    produtor_id: UUID | None
    ativo:       bool
    criado_em:   Any | None = None
    permissions: Any | None = None


class UsuarioCreate(RespostaBase):
    nome:        str
    email:       str
    senha:       str
    role:        str = "comercial"
    equipe_id:   UUID | None = None
    produtor_id: UUID | None = None
    permissions: Any | None = None

    @field_validator("role")
    @classmethod
    def role_valido(cls, v: str) -> str:
        validos = {"admin", "gestor", "comercial", "contador"}
        if v not in validos:
            raise ValueError(f"role deve ser um de: {validos}")
        return v


class UsuarioUpdate(RespostaBase):
    nome:        str | None = None
    role:        str | None = None
    equipe_id:   UUID | None = None
    produtor_id: UUID | None = None
    ativo:       bool | None = None
    permissions: Any | None = None

    @field_validator("role")
    @classmethod
    def role_valido(cls, v: str | None) -> str | None:
        if v is not None:
            validos = {"admin", "gestor", "comercial", "contador"}
            if v not in validos:
                raise ValueError(f"role deve ser um de: {validos}")
        return v


# ── LANÇAMENTOS: DESPESAS ─────────────────────────────────────

class DespesaCreate(RespostaBase):
    tipo_lancamento_id: UUID | None = None
    banco_id:           UUID | None = None
    categoria:          str | None = None   # ENUM legado — obrigatório se tipo_lancamento_id for None
    subcategoria:       str = Field(min_length=1, max_length=100)
    descricao:          str = Field(min_length=3, max_length=500)
    valor:              Decimal = Field(ge=0, le=99_999_999.99)
    competencia:        date
    paga_em:            date | None = None
    centro_custo:       str = "matriz"
    recorrente:         bool = False
    parcela_atual:      int | None = Field(default=None, ge=1)
    parcela_total:      int | None = Field(default=None, ge=1)

    @field_validator("competencia")
    @classmethod
    def competencia_nao_futuro_distante(cls, v: date) -> date:
        from datetime import date as d
        hoje = d.today()
        limite = d(hoje.year + (1 if hoje.month > 10 else 0), (hoje.month + 2 - 1) % 12 + 1, 1)
        if v > limite:
            raise ValueError("Competência não pode ser mais de 2 meses no futuro.")
        return v

    @field_validator("centro_custo")
    @classmethod
    def centro_custo_valido(cls, v: str) -> str:
        if v not in ("matriz", "aguas_lindoia"):
            raise ValueError("centro_custo deve ser 'matriz' ou 'aguas_lindoia'.")
        return v


class DespesaItem(RespostaBase):
    id:                 UUID
    tipo_lancamento_id: UUID | None
    tipo_nome:          str | None          # nome do tipo (join)
    banco_id:           UUID | None
    banco_nome:         str | None          # nome do banco (join)
    categoria:          str | None
    subcategoria:       str
    descricao:          str
    valor:              Decimal
    competencia:        date
    paga_em:            date | None
    centro_custo:       str
    recorrente:         bool
    parcela_atual:      int | None
    parcela_total:      int | None
    criado_em:          Any | None = None
    # Campos do fluxo de aprovação
    status:             str = "aprovada"    # 'pendente' | 'aprovada' | 'rejeitada'
    criado_por:         UUID | None = None
    aprovado_por:       UUID | None = None
    aprovado_em:        Any | None = None
    rejeitado_motivo:   str | None = None


class DespesasResponse(RespostaBase):
    total:              int
    items:              list[DespesaItem]
    soma_total:         Decimal
    total_pendentes:    int = 0


class DespesaUpdate(RespostaBase):
    tipo_lancamento_id: UUID | None = None
    banco_id:           UUID | None = None
    descricao:          str | None = Field(default=None, min_length=3, max_length=500)
    subcategoria:       str | None = Field(default=None, min_length=1, max_length=100)
    valor:              Decimal | None = Field(default=None, ge=0, le=99_999_999.99)
    competencia:        date | None = None
    paga_em:            date | None = None
    centro_custo:       str | None = None

    @field_validator("centro_custo")
    @classmethod
    def centro_custo_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in ("matriz", "aguas_lindoia"):
            raise ValueError("centro_custo deve ser 'matriz' ou 'aguas_lindoia'.")
        return v


class DespesaAprovacaoRejeicao(RespostaBase):
    motivo: str | None = None   # obrigatório para rejeição


# ── LANÇAMENTOS: RECEITAS ─────────────────────────────────────

class ReceitaOutraUpdate(RespostaBase):
    tipo_lancamento_id: UUID | None = None
    banco_id:           UUID | None = None
    centro_custo:       str | None = None
    descricao:          str | None = Field(default=None, min_length=3, max_length=500)
    valor:              Decimal | None = Field(default=None, ge=0, le=99_999_999.99)
    competencia:        date | None = None
    recebido_em:        date | None = None
    observacao:         str | None = Field(default=None, max_length=1000)

    @field_validator("centro_custo")
    @classmethod
    def centro_custo_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in ("matriz", "aguas_lindoia"):
            raise ValueError("centro_custo deve ser 'matriz' ou 'aguas_lindoia'.")
        return v


class ReceitaOutraCreate(RespostaBase):
    tipo_lancamento_id: UUID | None = None
    banco_id:           UUID | None = None
    centro_custo:       str = "matriz"
    descricao:          str = Field(min_length=3, max_length=500)
    valor:              Decimal = Field(ge=0, le=99_999_999.99)
    competencia:        date
    recebido_em:        date | None = None
    observacao:         str | None = Field(default=None, max_length=1000)

    @field_validator("centro_custo")
    @classmethod
    def centro_custo_valido(cls, v: str) -> str:
        if v not in ("matriz", "aguas_lindoia"):
            raise ValueError("centro_custo deve ser 'matriz' ou 'aguas_lindoia'.")
        return v


class ReceitaItem(RespostaBase):
    """Representa tanto comissão (origem=comissao) quanto receita manual (origem=manual)."""
    id:                 UUID
    origem:             str             # 'comissao' | 'manual'
    tipo_lancamento_id: UUID | None = None
    tipo_nome:          str | None = None
    banco_id:           UUID | None = None
    banco_nome:         str | None = None
    descricao:          str
    valor:              Decimal
    competencia:        date
    recebido_em:        date | None = None
    centro_custo:       str | None = None
    observacao:         str | None = None


class ReceitasResponse(RespostaBase):
    total:               int
    items:               list[ReceitaItem]
    soma_comissoes:      Decimal
    soma_manuais:        Decimal
    soma_total:          Decimal


# ── FECHAMENTOS MENSAIS ───────────────────────────────────────

class FechamentoCreate(RespostaBase):
    competencia: date

    @field_validator("competencia")
    @classmethod
    def normalizar_para_primeiro_dia(cls, v: date) -> date:
        return date(v.year, v.month, 1)


class ReabrirFechamento(RespostaBase):
    motivo: str


class FechamentoItem(RespostaBase):
    id:              UUID
    competencia:     date
    fechado_por:     UUID | None
    fechado_em:      datetime
    snapshot_dre:    dict[str, Any]
    reaberto_por:    UUID | None = None
    reaberto_em:     datetime | None = None
    reaberto_motivo: str | None = None


class FechamentosResponse(RespostaBase):
    total: int
    items: list[FechamentoItem]


# ── METAS ─────────────────────────────────────────────────────

class MetaCreate(RespostaBase):
    escopo:     str
    competencia: date
    valor_alvo: Decimal
    metrica:    str

    @field_validator("escopo")
    @classmethod
    def escopo_valido(cls, v: str) -> str:
        validos = {"global", "produtor", "equipe", "ramo"}
        if v not in validos:
            raise ValueError(f"escopo deve ser um de: {validos}")
        return v

    @field_validator("valor_alvo")
    @classmethod
    def valor_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("valor_alvo deve ser um valor positivo")
        return v


class MetaItem(RespostaBase):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Any = None
    escopo: str | None = None
    metrica: str | None = None
    valor_alvo: Decimal | None = None
    valor_realizado: Decimal | None = None
    percentual_atingido: float | None = None


class MetasResponse(RespostaBase):
    competencia: date
    items:       list[MetaItem]


# ── ESTORNOS ──────────────────────────────────────────────────

class EstornoItem(RespostaBase):
    id:         Any
    apolice_id: Any = None
    valor:      Decimal
    competencia: date
    motivo:     str | None = None


class EstornosResponse(RespostaBase):
    items:        list[EstornoItem]
    total:        Decimal
    taxa_estorno: float
    alerta_5pct:  bool


# ── REPASSES ──────────────────────────────────────────────────

class RepasseItem(RespostaBase):
    id:          Any = None
    comissao_id: Any = None
    produtor_id: Any = None
    valor:       Decimal
    percentual:  Decimal | None = None
    competencia: date
    pago_em:     date | None = None
    status:      str = "previsto"


class RepassesResponse(RespostaBase):
    items:         list[RepasseItem]
    soma_previsto: Decimal
    soma_pago:     Decimal


# ── DASHBOARD AGREGADO ────────────────────────────────────────

class AlertaDashboard(RespostaBase):
    tipo:      str
    mensagem:  str
    severidade: str  # 'info' | 'aviso' | 'critico'


class DashboardResponse(RespostaBase):
    periodo:     dict[str, date]
    dre:         LinhasDRE
    perfil:      str
    metas:       Any = None
    alertas:     list[AlertaDashboard]
    latencia_ms: int


# ── ERROS ─────────────────────────────────────────────────────

class ErroResponse(RespostaBase):
    erro:    str
    detalhe: str | None = None
