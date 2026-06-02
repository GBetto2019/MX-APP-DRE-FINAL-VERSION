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
  metrica: string
  valor_alvo: number
  valor_atual: number
  percentual: number
  atingida: boolean
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
