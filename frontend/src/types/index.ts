export type Role = 'admin' | 'gestor' | 'comercial' | 'contador'

export interface Usuario {
  id: string
  nome: string
  email: string
  role: Role
  equipe_id: string | null
  produtor_id: string | null
  ativo: boolean
}

export interface LinhasDRE {
  receita_bruta: number
  estornos: number
  impostos: number
  receita_liquida: number | null
  repasses_produtores: number | null
  margem_contribuicao: number | null
  despesas_fixas: number | null
  ebitda: number | null
  despesas_nao_operacionais: number | null
  resultado_liquido: number | null
}

export interface DREResponse {
  periodo: { inicio: string; fim: string }
  dre: LinhasDRE
  perfil: string
}

export interface MetaItem {
  meta_id: string
  escopo: string
  escopo_id: string | null
  metrica: string
  valor_alvo: number
  valor_atual: number
  percentual: number
  atingida: boolean
}

export interface MetaCadastroItem {
  id: string
  escopo: string
  escopo_id: string | null
  competencia: string
  valor_alvo: number
  metrica: string
  criado_em: string | null
}

export interface MetasResponse {
  competencia: string
  items: MetaItem[]
}

export interface AlertaDashboard {
  tipo: string
  mensagem: string
  severidade: 'info' | 'aviso' | 'critico'
}

export interface DashboardResponse {
  periodo: { inicio: string; fim: string }
  dre: LinhasDRE
  perfil: string
  metas: MetasResponse
  alertas: AlertaDashboard[]
  latencia_ms: number
}

export interface ChatMensagem {
  role: 'user' | 'assistant'
  content: string
}

export interface UsuarioItem {
  id: string
  nome: string
  email: string
  role: Role
  equipe_id: string | null
  produtor_id: string | null
  ativo: boolean
}

export type StatusDespesa = 'pendente' | 'aprovada' | 'rejeitada'

export interface Despesa {
  id: string
  tipo_lancamento_id: string | null
  tipo_nome: string | null
  banco_id: string | null
  banco_nome: string | null
  categoria: string | null
  subcategoria: string
  descricao: string
  valor: number
  competencia: string
  paga_em: string | null
  centro_custo: string
  recorrente: boolean
  parcela_atual: number | null
  parcela_total: number | null
  criado_em: string | null
  status: StatusDespesa
  criado_por: string | null
  aprovado_por: string | null
  aprovado_em: string | null
  rejeitado_motivo: string | null
}

export interface DespesasResponse {
  total: number
  items: Despesa[]
  soma_total: number
  total_pendentes: number
}
