"""
MX Seguros — DRE-IA | Fase 2: ETL
Dicionário de categorização de lançamentos do balancete.

Regra: cada entrada é (palavra_chave_lower -> (categoria, subcategoria)).
O mapeamento é EXPLÍCITO — sem regex mágica, sem ML.
Para adicionar uma regra nova, basta inserir uma linha neste dicionário.
Revisável pelo PO a qualquer momento.
"""
from __future__ import annotations

import unicodedata
from typing import TypedDict


def _normalizar(texto: str) -> str:
    """Remove acentos e converte para minúsculas para comparação."""
    return unicodedata.normalize("NFD", texto.lower()) \
        .encode("ascii", "ignore").decode("ascii")

# ── Tipo de retorno ───────────────────────────────────────────

class Classificacao(TypedDict):
    categoria: str          # valor do enum despesa_categoria
    subcategoria: str
    tipo_lancamento: str    # 'despesa' | 'receita' | 'imposto' | 'investimento' | 'ignorar'
    centro_custo: str       # 'matriz' | 'aguas_lindoia'


# ── SEGURADORAS PARCEIRAS → receita (comissão) ────────────────

SEGURADORAS: set[str] = {
    "tokio marine", "tokio", "sura", "hdi", "allianz",
    "sul america", "sul américa", "bradesco seguros", "bradesco",
    "mapfre", "prudential", "zurich", "chubb", "sompo",
    "yelum", "suhai", "axa", "odonto prev", "darwin",
    "ezze", "fair fax", "fairfax", "kovr", "metropole life",
    "alfa seguros", "alfa", "akad", "porto seguro", "liberty",
    "itau seguros", "itaú seguros",
}

# ── IMPOSTOS ──────────────────────────────────────────────────

IMPOSTOS: dict[str, str] = {
    "simples nacional":  "simples_nacional",
    "imposto simples":   "simples_nacional",
    "inss":              "inss",
    "imposto inss":      "inss",
    "fgts":              "fgts",
    "imposto fgts":      "fgts",
    "iss":               "iss",
    "pis":               "pis",
    "cofins":            "cofins",
    "irpj":              "irpj",
    "csll":              "csll",
    "iof":               "iof",
}

# ── DESPESAS: mapeamento palavra-chave → (categoria, subcategoria) ─

MAPA_DESPESAS: dict[str, tuple[str, str]] = {

    # ── PESSOAL ──────────────────────────────────────────────
    "salario":          ("pessoal", "salario"),
    "salário":          ("pessoal", "salario"),
    "ferias":           ("pessoal", "ferias"),
    "férias":           ("pessoal", "ferias"),
    "antecipacao salario": ("pessoal", "antecipacao_salario"),
    "antecipação salario": ("pessoal", "antecipacao_salario"),
    "vale alimentacao": ("pessoal", "vale_alimentacao"),
    "vale alimentação": ("pessoal", "vale_alimentacao"),
    "plano saude":      ("pessoal", "plano_saude"),
    "plano de saude":   ("pessoal", "plano_saude"),
    "plano de saúde":   ("pessoal", "plano_saude"),
    "seguro vida colaboradores": ("pessoal", "seguro_vida_colaboradores"),
    "reserva para funcionarios": ("pessoal", "reserva_funcionarios"),
    "pro-labore":       ("pessoal", "pro_labore"),
    "pró-labore":       ("pessoal", "pro_labore"),
    "prolabore":        ("pessoal", "pro_labore"),
    "distribuicao":     ("pessoal", "distribuicao_lucros"),
    "distribuição":     ("pessoal", "distribuicao_lucros"),

    # ── COMERCIAL ────────────────────────────────────────────
    "premiacao":        ("comercial", "premiacao"),
    "premiação":        ("comercial", "premiacao"),
    "blue play":        ("comercial", "premiacao"),
    "patrocinio":       ("comercial", "patrocinio"),
    "patrocínio":       ("comercial", "patrocinio"),
    "evento":           ("comercial", "evento"),
    "bni":              ("comercial", "associacao"),
    "associacao comercial": ("comercial", "associacao"),
    "associação comercial": ("comercial", "associacao"),
    "gasto com marketing": ("comercial", "marketing"),
    "facebk":           ("comercial", "marketing_digital"),
    "facebook":         ("comercial", "marketing_digital"),
    "google":           ("comercial", "marketing_digital"),
    "restaurante":      ("comercial", "alimentacao_negocios"),
    "almoco":           ("comercial", "alimentacao_negocios"),
    "almoço":           ("comercial", "alimentacao_negocios"),
    "janta":            ("comercial", "alimentacao_negocios"),
    "viagem":           ("comercial", "viagem"),
    "summit":           ("comercial", "evento"),
    "grupo exalt":      ("comercial", "evento"),
    "exalt":            ("comercial", "evento"),

    # ── ADMINISTRATIVA / OPERACIONAL ─────────────────────────
    "aluguel predio":   ("administrativa_operacional", "aluguel"),
    "aluguel":          ("administrativa_operacional", "aluguel"),
    "internet":         ("administrativa_operacional", "internet"),
    "bs conect":        ("administrativa_operacional", "internet"),
    "telefone":         ("administrativa_operacional", "telefone"),
    "celular":          ("administrativa_operacional", "celular"),
    "slmit":            ("administrativa_operacional", "sistema_office"),
    "office 365":       ("administrativa_operacional", "sistema_office"),
    "crm helena":       ("administrativa_operacional", "sistema_crm"),
    "sistema gest":     ("administrativa_operacional", "sistema_agger"),
    "agger":            ("administrativa_operacional", "sistema_agger"),
    "iconenseg":        ("administrativa_operacional", "sistema_iconenseg"),
    "aplicativo":       ("administrativa_operacional", "sistema_iconenseg"),
    "zoho":             ("administrativa_operacional", "sistema_crm"),
    "bign":             ("administrativa_operacional", "sistema_crm"),
    "escritorio itacont": ("administrativa_operacional", "contabilidade"),
    "itacont":          ("administrativa_operacional", "contabilidade"),
    "consultoria":      ("administrativa_operacional", "consultoria"),
    "nucci engenharia": ("administrativa_operacional", "manutencao"),
    "advogado":         ("administrativa_operacional", "juridico"),
    "lucas sigolo":     ("administrativa_operacional", "juridico"),
    "cartorio":         ("administrativa_operacional", "juridico"),
    "registro de imoveis": ("administrativa_operacional", "juridico"),
    "detetizacao":      ("administrativa_operacional", "limpeza"),
    "faxineira":        ("administrativa_operacional", "limpeza"),
    "monitoramento":    ("administrativa_operacional", "seguranca"),
    "vigilant":         ("administrativa_operacional", "seguranca"),
    "papelaria":        ("administrativa_operacional", "material_escritorio"),
    "correios":         ("administrativa_operacional", "correios"),
    "cpfl":             ("administrativa_operacional", "energia_agua"),
    "energia":          ("administrativa_operacional", "energia_agua"),
    "agua":             ("administrativa_operacional", "energia_agua"),
    "tarifa bancaria":  ("administrativa_operacional", "tarifa_bancaria"),
    "sinicor":          ("administrativa_operacional", "associacao_sindical"),
    "guerra comunicacao": ("administrativa_operacional", "dominio_hosting"),
    "dominio":          ("administrativa_operacional", "dominio_hosting"),
    "mercado livre":    ("administrativa_operacional", "equipamentos"),
    "applecombill":     ("administrativa_operacional", "software"),
    "google one":       ("administrativa_operacional", "armazenamento_cloud"),
    "dubraz":           ("administrativa_operacional", "manutencao"),

    # ── VEÍCULOS ─────────────────────────────────────────────
    "ipva":             ("veiculos", "ipva"),
    "kwid":             ("veiculos", "financiamento_veiculo"),
    "kwilds":           ("veiculos", "financiamento_veiculo"),
    "rampage":          ("veiculos", "financiamento_veiculo"),
    "strada":           ("veiculos", "financiamento_veiculo"),
    "iveco":            ("veiculos", "financiamento_veiculo"),
    "combustivel":      ("veiculos", "combustivel"),
    "posto":            ("veiculos", "combustivel"),
    "tanque":           ("veiculos", "combustivel"),
    "pedagio":          ("veiculos", "pedagio"),
    "aluguel carro":    ("veiculos", "aluguel_veiculo"),
    "ativa":            ("veiculos", "aluguel_veiculo"),
    "seguro kwid":      ("veiculos", "seguro_veiculo"),
    "seguro caminhonete": ("veiculos", "seguro_veiculo"),
    "seguro frota":     ("veiculos", "seguro_veiculo"),
    "seguro onix":      ("veiculos", "seguro_veiculo"),

    # ── TERCEIROS / REPASSES ─────────────────────────────────
    "rodrigo robles":   ("terceiros", "repasse_produtor"),
    "pronamp":          ("financeira", "financiamento"),
    "transferencia sicred": ("financeira", "financiamento"),
    "financiamento":    ("financeira", "financiamento"),
    "porshe bogus":     ("nao_operacional", "outros"),
    "hering":           ("nao_operacional", "outros"),
    "sm cubatao":       ("nao_operacional", "outros"),

    # ── INVESTIMENTOS / IMOBILIZADO ───────────────────────────
    "consorcio":        ("investimento_imobilizado", "consorcio"),
    "lys moveis":       ("investimento_imobilizado", "moveis"),
    "talita nucci":     ("investimento_imobilizado", "outros"),

    # ── AGRONEGÓCIO ───────────────────────────────────────────
    "alimentacao rodrigo": ("comercial", "despesa_agro"),
    "auto posto jaguar":   ("veiculos", "combustivel"),

    # ── GASTOS NÃO MAPEADOS — adicionados após primeira execução ──
    "pix qr code":         ("administrativa_operacional", "pagamento_diverso"),
    "pix qr":              ("administrativa_operacional", "pagamento_diverso"),
    "comercial rio branco":("comercial", "patrocinio"),
    "doacao":              ("comercial", "patrocinio"),
    "camisetas":           ("comercial", "marketing"),
    "funenseg":            ("pessoal", "treinamento"),
    "escola nacional de seguros": ("pessoal", "treinamento"),
    "relogio ponto":       ("administrativa_operacional", "sistema_ponto"),
    "ovos de pascoa":      ("pessoal", "beneficio_colaboradores"),
    "ovos de paschoa":     ("pessoal", "beneficio_colaboradores"),
    "donati":              ("administrativa_operacional", "manutencao"),
    "funilaria":           ("veiculos", "manutencao_veiculo"),
    "saae":                ("administrativa_operacional", "energia_agua"),
    "exame":               ("pessoal", "saude"),
    "influenza":           ("pessoal", "saude"),
    "padaria":             ("comercial", "alimentacao_negocios"),
}

# ── TERMOS DE ÁGUAS DE LINDOIA ────────────────────────────────

TERMOS_AGUAS_LINDOIA: list[str] = [
    "aguas de lindoia",
    "águas de lindoia",
    "filial",
    "itacont - filial",
    "funcionaria fernanda",   # funcionária da filial
    "aluguel ponto aguas",
    "internet - aguas",
    "cpfl",                   # energia da filial
]

# ── TERMOS DO AGRONEGÓCIO ─────────────────────────────────────

TERMOS_AGRO: list[str] = [
    "rodrigo robles",
    "alimentacao rodrigo",
    "pedagio pix rodrigo",
    "seguro onix",
    "auto posto jaguar",
]


# ── FUNÇÃO PRINCIPAL ──────────────────────────────────────────

def classificar(descricao: str, secao_atual: str = "") -> Classificacao:
    """
    Classifica um lançamento pelo texto da descrição.

    Args:
        descricao:     Texto da coluna de descrição do balancete.
        secao_atual:   Seção do balancete em que o lançamento está
                       ('gastos_fixos', 'gastos_variaveis', 'aguas_lindoia',
                        'agro', 'investimentos', 'recebimentos').

    Returns:
        Classificacao com categoria, subcategoria, tipo e centro_custo.
    """
    desc_lower = _normalizar(descricao.strip())

    # Seção de recebimentos → receita de comissão
    if secao_atual == "recebimentos":
        for seg in SEGURADORAS:
            if seg in desc_lower:
                return Classificacao(
                    categoria="",
                    subcategoria="comissao_padrao",
                    tipo_lancamento="receita",
                    centro_custo="matriz",
                )
        # Recebimento não identificado como seguradora
        return Classificacao(
            categoria="",
            subcategoria="outro_recebimento",
            tipo_lancamento="receita",
            centro_custo="matriz",
        )

    # Impostos
    for chave, tipo_imposto in IMPOSTOS.items():
        if chave in desc_lower:
            return Classificacao(
                categoria="",
                subcategoria=tipo_imposto,
                tipo_lancamento="imposto",
                centro_custo="aguas_lindoia" if _e_aguas_lindoia(desc_lower, secao_atual) else "matriz",
            )

    # Centro de custo
    centro = "aguas_lindoia" if _e_aguas_lindoia(desc_lower, secao_atual) else "matriz"

    # Investimentos
    if secao_atual == "investimentos":
        for chave, (cat, subcat) in MAPA_DESPESAS.items():
            if chave in desc_lower:
                return Classificacao(
                    categoria=cat,
                    subcategoria=subcat,
                    tipo_lancamento="investimento",
                    centro_custo=centro,
                )
        return Classificacao(
            categoria="investimento_imobilizado",
            subcategoria="outros",
            tipo_lancamento="investimento",
            centro_custo=centro,
        )

    # Mapa principal de despesas (mais longo primeiro para evitar sobreposição)
    chaves_ordenadas = sorted(MAPA_DESPESAS.keys(), key=len, reverse=True)
    for chave in chaves_ordenadas:
        if _normalizar(chave) in desc_lower:
            cat, subcat = MAPA_DESPESAS[chave]
            return Classificacao(
                categoria=cat,
                subcategoria=subcat,
                tipo_lancamento="despesa",
                centro_custo=centro,
            )

    # Não classificado
    return Classificacao(
        categoria="",
        subcategoria="nao_classificado",
        tipo_lancamento="revisar",
        centro_custo=centro,
    )


def _e_aguas_lindoia(desc_lower: str, secao: str) -> bool:
    """Retorna True se o lançamento pertence ao centro de custo Águas de Lindoia."""
    if secao == "aguas_lindoia":
        return True
    desc_norm = _normalizar(desc_lower)
    return any(_normalizar(termo) in desc_norm for termo in TERMOS_AGUAS_LINDOIA)
