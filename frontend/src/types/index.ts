export type Role = 'admin' | 'gestor' | 'comercial' | 'contador'

export interface Permissions {
  visao_geral:   { visualizar: boolean }
  dre:           { visualizar: boolean }
  lancamentos:   { visualizar: boolean; criar: boolean; editar: boolean; deletar: boolean }
  aprovacoes:    { visualizar: boolean; aprovar: boolean }
  assistente:    { visualizar: boolean }
  configuracoes: { visualizar: boolean; criar: boolean; editar: boolean }
}

export const DEFAULT_PERMISSIONS: Record<Role, Permissions> = {
  admin: {
    visao_geral:   { visualizar: true },
    dre:           { visualizar: true },
    lancamentos:   { visualizar: true, criar: true, editar: true, deletar: true },
    aprovacoes:    { visualizar: true, aprovar: true },
    assistente:    { visualizar: true },
    configuracoes: { visualizar: true, criar: true, editar: true },
  },
  gestor: {
    visao_geral:   { visualizar: true },
    dre:           { visualizar: true },
    lancamentos:   { visualizar: true, criar: true, editar: true, deletar: false },
    aprovacoes:    { visualizar: true, aprovar: true },
    assistente:    { visualizar: true },
    configuracoes: { visualizar: true, criar: true, editar: true },
  },
  comercial: {
    visao_geral:   { visualizar: true },
    dre:           { visualizar: true },
    lancamentos:   { visualizar: true, criar: true, editar: false, deletar: false },
    aprovacoes:    { visualizar: false, aprovar: false },
    assistente:    { visualizar: true },
    configuracoes: { visualizar: true, criar: false, editar: false },
  },
  contador: {
    visao_geral:   { visualizar: true },
    dre:           { visualizar: true },
    lancamentos:   { visualizar: true, criar: true, editar: false, deletar: false },
    aprovacoes:    { visualizar: false, aprovar: false },
    assistente:    { visualizar: true },
    configuracoes: { visualizar: true, criar: false, editar: false },
  },
}

export function getDefaultPermissions(role: Role): Permissions {
  return DEFAULT_PERMISSIONS[role]
}

export interface Usuario {
  id: string
  nome: string
  email: string
  role: Role
  equipe_id: string | null
  produtor_id: string | null
  ativo: boolean
  permissions?: Permissions | null
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

export interface AlertaDashboard {
  tipo: string
  mensagem: string
  severidade: 'info' | 'aviso' | 'critico'
}

export interface DashboardResponse {
  periodo: { inicio: string; fim: string }
  dre: LinhasDRE
  perfil: string
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
  permissions?: Permissions | null
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
