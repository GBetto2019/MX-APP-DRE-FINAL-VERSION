'use client'
import { useState, useMemo } from 'react'
import Link from 'next/link'

interface FaqItem {
  id: string
  categoria: string
  pergunta: string
  resposta: string
}

const FAQ: FaqItem[] = [
  // ── Perfis e Permissões ────────────────────────────────────────
  {
    id: 'p1',
    categoria: 'Perfis e Permissões',
    pergunta: 'Quais são os perfis do sistema?',
    resposta: 'Admin: acesso total, incluindo aprovar despesas, gerenciar usuários e reabrir fechamentos. Gestor: aprova despesas, visualiza dados da equipe. Contador: lança despesas e receitas, acessa DRE completo. Comercial: lança despesas, visualiza suas próprias comissões.',
  },
  {
    id: 'p2',
    categoria: 'Perfis e Permissões',
    pergunta: 'Quem pode aprovar ou rejeitar despesas?',
    resposta: 'Apenas Admin e Gestor. Despesas lançadas por Contador e Comercial ficam com status Pendente até serem analisadas no Kanban de Aprovações.',
  },
  {
    id: 'p3',
    categoria: 'Perfis e Permissões',
    pergunta: 'Quem pode criar e gerenciar usuários?',
    resposta: 'Admin e Gestor podem criar novos usuários e alterar perfis. Apenas Admin pode desativar um usuário. Gestor não pode atribuir o perfil Admin.',
  },
  {
    id: 'p4',
    categoria: 'Perfis e Permissões',
    pergunta: 'Por que não vejo alguns itens no menu?',
    resposta: 'O menu exibe apenas o que seu perfil pode usar. Aprovações e Configurações são visíveis só para Admin e Gestor.',
  },
  {
    id: 'p5',
    categoria: 'Perfis e Permissões',
    pergunta: 'Admin e Gestor precisam de aprovação nas próprias despesas?',
    resposta: 'Não. Despesas lançadas por Admin ou Gestor são aprovadas automaticamente. Apenas os lançamentos de Contador e Comercial passam pelo fluxo de aprovação.',
  },

  // ── Lançamentos ────────────────────────────────────────────────
  {
    id: 'l1',
    categoria: 'Lançamentos',
    pergunta: 'Como lançar uma nova despesa?',
    resposta: 'Vá em Lançamentos → aba Despesas → clique "+ Nova Despesa". Preencha tipo, descrição, valor, competência e centro de custo. O lançamento entra como Pendente se você for Contador ou Comercial.',
  },
  {
    id: 'l2',
    categoria: 'Lançamentos',
    pergunta: 'Como lançar uma nova receita manual?',
    resposta: 'Vá em Lançamentos → aba Receitas → clique "+ Nova Receita". Preencha tipo, descrição, valor e competência. Comissões automáticas (ETL) não são editadas aqui.',
  },
  {
    id: 'l3',
    categoria: 'Lançamentos',
    pergunta: 'O que é competência?',
    resposta: 'É o mês ao qual o lançamento pertence financeiramente — não necessariamente quando foi pago. Ex.: aluguel de janeiro pago em fevereiro tem competência janeiro.',
  },
  {
    id: 'l4',
    categoria: 'Lançamentos',
    pergunta: 'O que é centro de custo?',
    resposta: 'Identifica a unidade responsável pelo lançamento: Matriz ou Águas Lindoia. Permite separar os resultados por filial.',
  },
  {
    id: 'l5',
    categoria: 'Lançamentos',
    pergunta: 'Posso editar um lançamento depois de salvar?',
    resposta: 'Sim. Clique no ícone de lápis na linha. Ao salvar, a despesa volta para status Pendente e precisará de nova aprovação. Receitas manuais podem ser editadas sem fluxo de aprovação.',
  },
  {
    id: 'l6',
    categoria: 'Lançamentos',
    pergunta: 'O que acontece ao excluir um lançamento?',
    resposta: 'O registro é desativado (exclusão lógica) e deixa de aparecer na lista e no DRE. Não é apagado permanentemente do banco de dados.',
  },
  {
    id: 'l7',
    categoria: 'Lançamentos',
    pergunta: 'Por que não consigo lançar em um mês já fechado?',
    resposta: 'Períodos fechados são congelados para garantir a integridade do DRE. Apenas Admin pode reabrir o período. Verifique a tela de Fechamentos.',
  },

  // ── Aprovação de Despesas ──────────────────────────────────────
  {
    id: 'a1',
    categoria: 'Aprovação de Despesas',
    pergunta: 'Por que minha despesa está como Pendente?',
    resposta: 'Despesas de Contador e Comercial precisam de aprovação de um Admin ou Gestor antes de serem contabilizadas no DRE. Aguarde a análise na tela de Aprovações.',
  },
  {
    id: 'a2',
    categoria: 'Aprovação de Despesas',
    pergunta: 'Como funciona o Kanban de Aprovações?',
    resposta: 'Tela exclusiva para Admin e Gestor. Exibe 4 colunas: Lançadas (todas), Pendente Aprovação (aguardando), Aprovadas e Rejeitadas. Na coluna Pendente, cada card tem botões Aprovar e Rejeitar.',
  },
  {
    id: 'a3',
    categoria: 'Aprovação de Despesas',
    pergunta: 'O que acontece ao rejeitar uma despesa?',
    resposta: 'A despesa vai para a coluna Rejeitadas com o motivo informado. O lançador pode ver o motivo na lista de Lançamentos pelo badge vermelho "Rejeitada".',
  },
  {
    id: 'a4',
    categoria: 'Aprovação de Despesas',
    pergunta: 'Despesas pendentes entram no DRE?',
    resposta: 'Não. Apenas despesas com status Aprovada são somadas no DRE. Isso garante que só o que foi validado impacta o resultado financeiro.',
  },
  {
    id: 'a5',
    categoria: 'Aprovação de Despesas',
    pergunta: 'Posso editar uma despesa rejeitada para corrigir e reenviar?',
    resposta: 'Sim. Clique no lápis na linha da despesa rejeitada, corrija os campos e salve. Ela voltará para Pendente automaticamente para uma nova análise.',
  },

  // ── DRE ───────────────────────────────────────────────────────
  {
    id: 'd1',
    categoria: 'DRE',
    pergunta: 'O que é o DRE?',
    resposta: 'Demonstração do Resultado do Exercício — resumo financeiro do período mostrando receitas, deduções, despesas e o resultado final. Calcula quanto a corretora ganhou ou perdeu.',
  },
  {
    id: 'd2',
    categoria: 'DRE',
    pergunta: 'O que é Receita Bruta?',
    resposta: 'Total das comissões recebidas das seguradoras no período selecionado, antes de qualquer dedução.',
  },
  {
    id: 'd3',
    categoria: 'DRE',
    pergunta: 'O que são Estornos no DRE?',
    resposta: 'Comissões devolvidas à seguradora por cancelamentos ou inadimplência. São deduzidos da Receita Bruta para chegar à Receita Líquida.',
  },
  {
    id: 'd4',
    categoria: 'DRE',
    pergunta: 'O que é Receita Líquida?',
    resposta: 'Receita Bruta menos Estornos e Impostos. Representa o que a corretora efetivamente reteve das seguradoras.',
  },
  {
    id: 'd5',
    categoria: 'DRE',
    pergunta: 'O que é Margem de Contribuição?',
    resposta: 'Receita Líquida menos Repasses a Produtores. Indica quanto sobra para cobrir os custos fixos da operação.',
  },
  {
    id: 'd6',
    categoria: 'DRE',
    pergunta: 'O que é EBITDA?',
    resposta: 'Margem de Contribuição menos Despesas Fixas. Mede a eficiência operacional antes de despesas não operacionais (juros, depreciação etc.).',
  },
  {
    id: 'd7',
    categoria: 'DRE',
    pergunta: 'O que é Resultado Líquido?',
    resposta: 'EBITDA menos Despesas Não Operacionais. É o lucro ou prejuízo final do período.',
  },
  {
    id: 'd8',
    categoria: 'DRE',
    pergunta: 'Por que alguns campos aparecem como "—"?',
    resposta: 'Seu perfil não tem permissão para visualizar essa informação. Comercial não vê Receita Líquida nem EBITDA. Gestor não vê Despesas Fixas nem EBITDA.',
  },

  // ── Fechamentos ───────────────────────────────────────────────
  {
    id: 'f1',
    categoria: 'Fechamentos',
    pergunta: 'O que é fechar um período?',
    resposta: 'Congela o mês impedindo novos lançamentos, e salva um snapshot do DRE para auditoria. Garante que o resultado histórico não seja alterado.',
  },
  {
    id: 'f2',
    categoria: 'Fechamentos',
    pergunta: 'Como reabrir um período fechado?',
    resposta: 'Apenas Admin pode reabrir, informando um motivo. Após a reabertura, novos lançamentos são permitidos até o próximo fechamento.',
  },

  // ── Exportações ───────────────────────────────────────────────
  {
    id: 'x1',
    categoria: 'Exportações',
    pergunta: 'Quais formatos posso exportar?',
    resposta: 'Excel (.xlsx) e PDF. Ambos exportam o DRE do período selecionado, com os dados visíveis para o seu perfil.',
  },

  // ── Assistente IA ─────────────────────────────────────────────
  {
    id: 'i1',
    categoria: 'Assistente IA',
    pergunta: 'O que o Assistente IA pode responder?',
    resposta: 'Perguntas sobre o DRE, interpretação de números, análise de tendências, receita por ramo e qualquer dúvida sobre os dados financeiros da corretora.',
  },
  {
    id: 'i2',
    categoria: 'Assistente IA',
    pergunta: 'O Assistente tem acesso aos meus dados?',
    resposta: 'Sim. Ele acessa os dados financeiros em tempo real, respeitando o seu perfil de acesso — vê apenas o que você tem permissão de ver.',
  },
  {
    id: 'i3',
    categoria: 'Assistente IA',
    pergunta: 'Posso pedir análises e comparativos ao Assistente?',
    resposta: 'Sim. Exemplos: "Compare o EBITDA dos últimos 3 meses", "Qual ramo gerou mais receita?", "Como estão minhas comissões neste período?".',
  },
]

const CATEGORIAS = Array.from(new Set(FAQ.map(f => f.categoria)))

function highlight(text: string, termo: string) {
  if (!termo.trim()) return <>{text}</>
  const regex = new RegExp(`(${termo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  const partes = text.split(regex)
  return (
    <>
      {partes.map((p, i) =>
        regex.test(p)
          ? <mark key={i} className="bg-amber-100 text-amber-900 rounded px-0.5">{p}</mark>
          : <span key={i}>{p}</span>
      )}
    </>
  )
}

function ItemFaq({ item, busca, aberto, onToggle }: {
  item: FaqItem
  busca: string
  aberto: boolean
  onToggle: () => void
}) {
  const perguntaIA = encodeURIComponent(item.pergunta)

  return (
    <div className={`rounded-xl border transition-colors ${aberto ? 'border-[#071934]/20 bg-white shadow-sm' : 'border-gray-100 bg-white hover:border-gray-200'}`}>
      <button
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
      >
        <span className="text-sm font-medium text-gray-800">
          {highlight(item.pergunta, busca)}
        </span>
        <svg
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
          className={`mt-0.5 h-4 w-4 shrink-0 text-gray-400 transition-transform ${aberto ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      {aberto && (
        <div className="border-t border-gray-100 px-5 py-4">
          <p className="text-sm leading-relaxed text-gray-600">
            {highlight(item.resposta, busca)}
          </p>
          <Link
            href={`/dashboard/assistente`}
            className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[#071934] hover:underline"
          >
            Perguntar ao Assistente sobre isso
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3 w-3">
              <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
            </svg>
          </Link>
        </div>
      )}
    </div>
  )
}

export default function AjudaPage() {
  const [busca, setBusca] = useState('')
  const [abertos, setAbertos] = useState<Set<string>>(new Set())

  const termo = busca.trim().toLowerCase()

  const resultados = useMemo(() => {
    if (!termo) return FAQ
    return FAQ.filter(f =>
      f.pergunta.toLowerCase().includes(termo) ||
      f.resposta.toLowerCase().includes(termo) ||
      f.categoria.toLowerCase().includes(termo)
    )
  }, [termo])

  function toggle(id: string) {
    setAbertos(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const buscando = termo.length > 0

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Cabeçalho */}
      <div>
        <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Central de Ajuda</h1>
        <p className="mt-0.5 text-sm text-gray-500">Respostas rápidas sobre o sistema. Para dúvidas mais detalhadas, use o Assistente IA.</p>
      </div>

      {/* Busca */}
      <div className="relative">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
          className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          type="text"
          value={busca}
          onChange={e => setBusca(e.target.value)}
          placeholder="Buscar por palavra-chave… ex: aprovação, DRE, lançamento"
          className="w-full rounded-xl border border-gray-200 bg-white py-3 pl-10 pr-4 text-sm text-gray-700 placeholder-gray-400 shadow-sm focus:border-[#071934] focus:outline-none focus:ring-1 focus:ring-[#071934]/20"
        />
        {busca && (
          <button onClick={() => setBusca('')}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        )}
      </div>

      {/* Resultado da busca */}
      {buscando && (
        <p className="text-xs text-gray-400">
          {resultados.length === 0
            ? 'Nenhum resultado. Tente outra palavra ou pergunte ao Assistente IA.'
            : `${resultados.length} resultado${resultados.length > 1 ? 's' : ''} para "${busca}"`}
        </p>
      )}

      {/* Lista — com busca: flat / sem busca: por categoria */}
      {buscando ? (
        <div className="space-y-2">
          {resultados.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-200 py-10 text-center">
              <p className="text-sm text-gray-400">Nenhuma resposta encontrada.</p>
              <Link href="/dashboard/assistente"
                className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-[#071934] hover:underline">
                Perguntar ao Assistente IA
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-3.5 w-3.5">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </Link>
            </div>
          ) : (
            resultados.map(item => (
              <ItemFaq
                key={item.id}
                item={item}
                busca={busca}
                aberto={abertos.has(item.id)}
                onToggle={() => toggle(item.id)}
              />
            ))
          )}
        </div>
      ) : (
        <div className="space-y-8">
          {CATEGORIAS.map(cat => (
            <div key={cat}>
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
                <span className="h-px flex-1 bg-gray-100" />
                {cat}
                <span className="h-px flex-1 bg-gray-100" />
              </h2>
              <div className="space-y-2">
                {FAQ.filter(f => f.categoria === cat).map(item => (
                  <ItemFaq
                    key={item.id}
                    item={item}
                    busca=""
                    aberto={abertos.has(item.id)}
                    onToggle={() => toggle(item.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rodapé */}
      <div className="rounded-xl bg-[#071934] px-6 py-5 text-center">
        <p className="text-sm font-medium text-white">Não encontrou o que precisava?</p>
        <p className="mt-1 text-xs text-white/60">O Assistente IA responde com exemplos, números reais e análises personalizadas.</p>
        <Link href="/dashboard/assistente"
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-[#071934] hover:bg-gray-100 transition-colors">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          Abrir Assistente IA
        </Link>
      </div>
    </div>
  )
}
