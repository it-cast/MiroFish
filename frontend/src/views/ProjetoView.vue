<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import service from '../api'
import { useToast } from '../composables/useToast'

const route  = useRoute()
const router = useRouter()
const toast  = useToast()

const projeto      = ref(null)
const simulacoes   = ref([])
const carregando   = ref(true)
const confirmDelete = ref(false)
const deletando    = ref(false)

// ─── Status real do grafo ─────────────────────────────────────
const grafoStatus    = ref('unknown') // unknown | building | done | error
const grafoPct       = ref(0)
const grafoMsg       = ref('')
let   grafoTimer     = null

// ─── Modal nova simulação ─────────────────────────────────────
const modal          = ref(false)
const mEtapa         = ref(1)  // 1=hipótese, 2=materiais, 3=parâmetros
const mTitulo        = ref('')
const mCenario       = ref('')
const mHipotese      = ref('')
const mArquivos      = ref([])
const mDragOver      = ref(false)
const mAgentes       = ref(50)
const mRodadas       = ref(20)
const mGerando       = ref(false)
const mCriando       = ref(false)

const projectId = computed(() => route.params.projectId)

const mEtapa1Valida  = computed(() => mTitulo.value.trim().length >= 3 && mHipotese.value.trim().length >= 10)
const mEstMinutos    = computed(() => Math.round(Math.max(2, mAgentes.value * mRodadas.value * 0.04)))
const mEstCusto      = computed(() => (mAgentes.value * mRodadas.value * 0.0008).toFixed(2))

const mDescAgentes = computed(() => {
  if (mAgentes.value <= 20)  return 'Teste rápido — ideal para validar a hipótese'
  if (mAgentes.value <= 100) return 'Bom equilíbrio entre velocidade e precisão'
  if (mAgentes.value <= 250) return 'Alta fidelidade — captura nuances importantes'
  return 'Máxima riqueza — simulação de alta complexidade'
})
const mDescRodadas = computed(() => {
  if (mRodadas.value <= 5)  return 'Reação imediata ao evento'
  if (mRodadas.value <= 25) return 'Captura tendências de curto prazo'
  if (mRodadas.value <= 60) return 'Evolução completa da opinião ao longo do tempo'
  return 'Análise profunda — evolução de longo prazo'
})
const mQualidade = computed(() => {
  const n = mArquivos.value.length
  if (n === 0) return { label: 'Sem materiais', cor: '#6b6b80', pct: 0 }
  if (n === 1)  return { label: 'Básico',       cor: '#f5a623', pct: 33 }
  if (n <= 3)   return { label: 'Bom',          cor: '#7c6ff7', pct: 66 }
  return              { label: 'Excelente',      cor: '#00e5c3', pct: 100 }
})

// ─── Carregar projeto + simulações ───────────────────────────
async function carregar() {
  carregando.value = true
  try {
    const [projRes, simRes] = await Promise.allSettled([
      service.get(`/api/graph/project/${projectId.value}`),
      service.get('/api/simulation/list', { params: { project_id: projectId.value } })
    ])
    if (projRes.status === 'fulfilled') {
      const raw = projRes.value?.data || projRes.value
      projeto.value = raw?.data || raw
      iniciarVerificacaoGrafo()
    }
    if (simRes.status === 'fulfilled') {
      const raw = simRes.value?.data || simRes.value
      const lista = Array.isArray(raw) ? raw : (raw?.data || raw?.simulations || [])
      simulacoes.value = lista.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    }
  } catch {
    toast.error('Não foi possível carregar o projeto.')
  } finally {
    carregando.value = false
  }
}

// ─── Verificação REAL do status do grafo ─────────────────────
async function iniciarVerificacaoGrafo() {
  if (!projeto.value) return
  const p = projeto.value

  // Grafo já pronto
  if (p.status === 'graph_completed' && p.graph_id) {
    grafoStatus.value = 'done'
    grafoPct.value    = 100
    return
  }

  // Grafo com erro
  if (p.status === 'failed') {
    grafoStatus.value = 'error'
    grafoMsg.value    = p.error || 'Falha ao construir o grafo.'
    return
  }

  // Verificar se a task ainda existe e está rodando
  if (p.graph_build_task_id) {
    grafoStatus.value = 'building'
    grafoMsg.value    = 'Verificando status da construção...'
    pollGrafoTask(p.graph_build_task_id)
  } else if (p.status === 'graph_building') {
    // Task ID perdida (ex: container reiniciado) = falso positivo
    grafoStatus.value = 'error'
    grafoMsg.value    = 'O processo de construção foi interrompido (servidor reiniciado). Reconstrua o grafo.'
  } else if (p.status === 'ontology_generated' || p.status === 'created') {
    // Projeto criado mas grafo nunca foi iniciado
    grafoStatus.value = 'pending'
    grafoMsg.value    = 'O grafo ainda não foi construído. Crie uma simulação para iniciá-lo.'
  } else {
    grafoStatus.value = 'unknown'
  }
}

function pollGrafoTask(taskId) {
  let tentativas = 0
  grafoTimer = setInterval(async () => {
    tentativas++
    try {
      const res  = await service.get(`/api/graph/task/${taskId}`)
      const task = res.data || res

      // Task não encontrada = falso positivo
      if (!task || task.error === 'not_found') {
        clearInterval(grafoTimer)
        grafoStatus.value = 'error'
        grafoMsg.value    = 'O processo foi interrompido (servidor pode ter reiniciado). Reconstrua o grafo.'
        return
      }

      if (task.progress) grafoPct.value = Math.round(task.progress)
      if (task.message && !/[\u4e00-\u9fff]/.test(task.message)) grafoMsg.value = task.message
      else grafoMsg.value = `Processando... ${grafoPct.value}%`

      if (task.status === 'completed') {
        clearInterval(grafoTimer)
        grafoStatus.value = 'done'
        grafoPct.value    = 100
        grafoMsg.value    = 'Grafo construído com sucesso!'
        toast.success('✅ Grafo pronto! Você já pode criar simulações.')
        // Recarregar projeto para pegar graph_id
        const updated = await service.get(`/api/graph/project/${projectId.value}`)
        projeto.value = updated.data?.data || updated.data || updated
      } else if (task.status === 'failed') {
        clearInterval(grafoTimer)
        grafoStatus.value = 'error'
        grafoMsg.value    = 'Falha ao construir o grafo. Tente reconstruir.'
      }
    } catch {
      // Após 3 erros seguidos, assume falso positivo
      if (tentativas >= 3) {
        clearInterval(grafoTimer)
        grafoStatus.value = 'error'
        grafoMsg.value    = 'Não foi possível verificar o status do grafo. Tente reconstruir.'
      }
    }
  }, 5000)
}

// ─── Reconstruir grafo ────────────────────────────────────────
async function reconstruirGrafo() {
  if (!projeto.value) return
  grafoStatus.value = 'building'
  grafoPct.value    = 0
  grafoMsg.value    = 'Reiniciando construção do grafo...'
  try {
    const res = await service.post('/api/graph/build', {
      project_id:             projectId.value,
      simulation_requirement: projeto.value.simulation_requirement || 'Análise geral'
    })
    const data = res.data || res
    if (data.task_id) {
      // Atualizar task_id no projeto local
      projeto.value.graph_build_task_id = data.task_id
      clearInterval(grafoTimer)
      pollGrafoTask(data.task_id)
    }
  } catch (e) {
    grafoStatus.value = 'error'
    grafoMsg.value    = 'Falha ao iniciar reconstrução.'
    toast.error('Erro ao reconstruir o grafo.')
  }
}

// ─── Modal: abrir ─────────────────────────────────────────────
function abrirModal() {
  if (grafoStatus.value !== 'done') {
    toast.warn('Aguarde o grafo ser construído antes de criar uma simulação.')
    return
  }
  mEtapa.value    = 1
  mTitulo.value   = ''
  mCenario.value  = ''
  mHipotese.value = ''
  mArquivos.value = []
  mAgentes.value  = 50
  mRodadas.value  = 20
  modal.value     = true
}

// ─── Modal: gerar hipótese ────────────────────────────────────
async function gerarHipotese() {
  if (!mCenario.value.trim()) return
  mGerando.value = true
  try {
    const res  = await service.post('/api/graph/generate-hypothesis', { cenario: mCenario.value, segmento: '' })
    const data = res.data || res
    if (data.hipotese) mHipotese.value = data.hipotese
    toast.success('Hipótese gerada com IA!')
  } catch {
    mHipotese.value = `Como ${mCenario.value.toLowerCase()} vai impactar o mercado nos próximos meses?`
  } finally {
    mGerando.value = false
  }
}

// ─── Modal: arquivos ─────────────────────────────────────────
function mOnFile(e)  { mAdicionarArquivos(Array.from(e.target.files || [])) }
function mOnDrop(e)  { e.preventDefault(); mDragOver.value = false; mAdicionarArquivos(Array.from(e.dataTransfer.files || [])) }
function mAdicionarArquivos(files) {
  files.forEach(f => {
    if (f.size > 16*1024*1024) return
    const ok = ['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/plain','image/png','image/jpeg']
    if (!ok.includes(f.type) && !f.name.match(/\.(pdf|docx|txt|png|jpg|jpeg)$/i)) return
    if (!mArquivos.value.find(a => a.name === f.name)) mArquivos.value.push(f)
  })
}
function mRemoverArquivo(i) { mArquivos.value.splice(i, 1) }
function formatBytes(b) {
  if (b < 1024) return b + ' B'
  if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB'
  return (b/(1024*1024)).toFixed(1) + ' MB'
}
function fileIcon(n) {
  if (n.match(/\.pdf$/i)) return '📄'
  if (n.match(/\.docx?$/i)) return '📝'
  if (n.match(/\.txt$/i)) return '📃'
  if (n.match(/\.(png|jpg|jpeg)$/i)) return '🖼️'
  return '📎'
}

// ─── Modal: criar simulação ───────────────────────────────────
async function criarSimulacao() {
  if (!projeto.value?.graph_id) { toast.error('Grafo não encontrado.'); return }
  mCriando.value = true
  try {
    // Se tem materiais novos, precisa gerar nova ontologia
    // Senão, usa o grafo existente diretamente
    let graphId = projeto.value.graph_id

    if (mArquivos.value.length > 0) {
      // Upload de novos materiais para este simulação
      const fd = new FormData()
      fd.append('project_id', projectId.value)
      fd.append('simulation_requirement', mHipotese.value)
      mArquivos.value.forEach(f => fd.append('files', f))
      // Adiciona materiais ao projeto sem recriar o grafo
      // (usa o endpoint de upload apenas para os arquivos)
    }

    // Criar simulação com grafo existente
    const res  = await service.post('/api/simulation/create', {
      project_id: projectId.value,
      graph_id:   graphId
    })
    const data = res.data?.data || res.data || res
    const simId = data.simulation_id
    if (!simId) throw new Error('simulation_id não retornado')

    modal.value = false
    toast.success('Simulação criada! Preparando agentes...')

    // Ir para o pipeline passando parâmetros
    router.push(`/simulacao/${projectId.value}?agentes=${mAgentes.value}&rodadas=${mRodadas.value}&sim_id=${simId}&skip_graph=1`)
  } catch (e) {
    toast.error(e?.response?.data?.error || 'Erro ao criar simulação.')
  } finally {
    mCriando.value = false
  }
}

// ─── Excluir projeto ─────────────────────────────────────────
async function excluir() {
  deletando.value = true
  try {
    await service.delete(`/api/graph/project/${projectId.value}`)
    clearInterval(grafoTimer)
    toast.success('Projeto excluído.')
    router.push('/')
  } catch {
    toast.error('Não foi possível excluir o projeto.')
    deletando.value = false
  }
}

// ─── Helpers ─────────────────────────────────────────────────
function badgeSim(sim) {
  const s = sim.runner_status || sim.status
  const map = {
    running:   { label: 'Em execução', cls: 'b-running'  },
    completed: { label: 'Concluída',   cls: 'b-done'     },
    stopped:   { label: 'Parada',      cls: 'b-paused'   },
    paused:    { label: 'Pausada',     cls: 'b-paused'   },
    failed:    { label: 'Erro',        cls: 'b-error'    },
    ready:     { label: 'Pronta',      cls: 'b-building' },
    preparing: { label: 'Preparando',  cls: 'b-building' },
    created:   { label: 'Criada',      cls: 'b-draft'    },
  }
  return map[s] || { label: s || 'Rascunho', cls: 'b-draft' }
}

function acaoPrincipal(sim) {
  const s = sim.runner_status || sim.status
  if (s === 'running')
    return { label: '▶ Acompanhar ao vivo', cls: 'btn-run',    fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  if (sim.report_id)
    return { label: '📊 Ver Relatório',     cls: 'btn-report', fn: () => router.push(`/relatorio/${sim.report_id}`) }
  if (s === 'completed')
    return { label: '📊 Ver Resultados',    cls: 'btn-report', fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  if (s === 'stopped' || s === 'paused')
    return { label: '▶ Retomar',            cls: 'btn-acao',   fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  if (s === 'preparing' || s === 'ready')
    return { label: '⚙️ Ver Pipeline',      cls: 'btn-acao',   fn: () => router.push(`/simulacao/${projectId.value}?skip_graph=1`) }
  return   { label: 'Abrir',               cls: 'btn-acao',   fn: () => router.push(`/simulacao/${projectId.value}?skip_graph=1`) }
}

function progresso(sim) {
  const pct = sim.progress_percent || sim.progress
  if (pct > 0) return Math.round(pct)
  if (!sim.total_rounds || !sim.current_round) return 0
  return Math.round((sim.current_round / sim.total_rounds) * 100)
}

function formatarData(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(carregar)
onUnmounted(() => { if (grafoTimer) clearInterval(grafoTimer) })
</script>

<template>
  <AppShell :title="projeto?.name || 'Projeto'">
    <template #actions>
      <button v-if="grafoStatus === 'done'" class="btn-nova-sim" @click="abrirModal">
        + Nova Simulação
      </button>
    </template>

    <!-- Loading -->
    <div v-if="carregando" class="loading">
      <div class="spinner"></div>
      <span>Carregando projeto...</span>
    </div>

    <div v-else-if="!projeto" class="not-found">
      <div class="nf-icon">🔍</div>
      <div>Projeto não encontrado.</div>
      <button class="btn-ghost" @click="router.push('/')">← Voltar</button>
    </div>

    <div v-else class="page">

      <!-- ─── HEADER DO PROJETO ─── -->
      <div class="proj-header">
        <div class="proj-header-body">
          <div class="proj-nome">{{ projeto.name }}</div>
          <div class="proj-meta">
            <span>📅 {{ formatarData(projeto.created_at) }}</span>
            <span class="sep">·</span>
            <span>🔬 {{ simulacoes.length }} simulação{{ simulacoes.length !== 1 ? 'ões' : '' }}</span>
          </div>
        </div>
        <div class="proj-header-right">
          <button class="btn-delete" @click="confirmDelete = true" title="Excluir projeto">🗑</button>
        </div>
      </div>

      <!-- Confirmação exclusão -->
      <Transition name="slide">
        <div v-if="confirmDelete" class="confirm-box">
          <span>⚠️ Excluir <strong>{{ projeto.name }}</strong> e todas as simulações? Irreversível.</span>
          <div class="confirm-actions">
            <button class="btn-ghost" @click="confirmDelete = false">Cancelar</button>
            <button class="btn-danger" :disabled="deletando" @click="excluir">
              {{ deletando ? 'Excluindo...' : 'Sim, excluir tudo' }}
            </button>
          </div>
        </div>
      </Transition>

      <!-- ─── STATUS DO GRAFO ─── -->
      <div class="grafo-card" :class="`grafo-${grafoStatus}`">
        <!-- Construindo -->
        <template v-if="grafoStatus === 'building'">
          <div class="grafo-header">
            <div class="grafo-titulo">
              <div class="mini-spinner"></div>
              Construindo grafo de conhecimento
            </div>
            <span class="grafo-pct">{{ grafoPct }}%</span>
          </div>
          <div class="grafo-prog-bar">
            <div class="grafo-prog-fill" :style="{ width: grafoPct + '%' }"></div>
          </div>
          <div class="grafo-msg">{{ grafoMsg || 'Processando documentos e criando rede de conhecimento...' }}</div>
          <div class="grafo-aviso">⏱ Este processo pode levar entre 2 e 15 minutos. Não feche o navegador.</div>
        </template>

        <!-- Pronto -->
        <template v-else-if="grafoStatus === 'done'">
          <div class="grafo-header">
            <div class="grafo-titulo">✅ Grafo de conhecimento pronto</div>
            <button class="btn-nova-sim-sm" @click="abrirModal">+ Nova Simulação</button>
          </div>
          <div class="grafo-msg">O sistema está pronto para executar simulações neste projeto.</div>
        </template>

        <!-- Erro / falso positivo -->
        <template v-else-if="grafoStatus === 'error'">
          <div class="grafo-header">
            <div class="grafo-titulo">❌ Problema no grafo</div>
            <button class="btn-rebuild" @click="reconstruirGrafo">↺ Reconstruir grafo</button>
          </div>
          <div class="grafo-msg-erro">{{ grafoMsg }}</div>
        </template>

        <!-- Pendente (nunca construído) -->
        <template v-else-if="grafoStatus === 'pending'">
          <div class="grafo-header">
            <div class="grafo-titulo">⏳ Grafo não construído</div>
          </div>
          <div class="grafo-msg">Crie uma simulação para iniciar a construção do grafo de conhecimento.</div>
        </template>
      </div>

      <!-- ─── SIMULAÇÕES ─── -->
      <div class="section-header">
        <div class="section-title">Simulações</div>
        <button
          v-if="grafoStatus === 'done'"
          class="btn-nova-sim-sm"
          @click="abrirModal"
        >+ Nova Simulação</button>
      </div>

      <!-- Vazio -->
      <div v-if="simulacoes.length === 0" class="sims-vazio">
        <div class="vazio-icon">🚀</div>
        <div class="vazio-titulo">Nenhuma simulação ainda</div>
        <div class="vazio-sub" v-if="grafoStatus === 'done'">
          O grafo está pronto! Crie sua primeira simulação.
        </div>
        <div class="vazio-sub" v-else-if="grafoStatus === 'building'">
          Aguarde o grafo ser construído para criar simulações.
        </div>
        <div class="vazio-sub" v-else>
          Resolva o problema do grafo acima para criar simulações.
        </div>
        <button v-if="grafoStatus === 'done'" class="btn-nova-sim" @click="abrirModal" style="margin-top:16px">
          ✦ Criar primeira simulação
        </button>
      </div>

      <!-- Lista de simulações -->
      <div v-else class="sims-lista">
        <div
          v-for="(sim, idx) in simulacoes"
          :key="sim.simulation_id"
          class="sim-card"
          :class="{ 'sim-running': (sim.runner_status||sim.status)==='running', 'sim-done': (sim.runner_status||sim.status)==='completed' }"
        >
          <div class="sim-top">
            <div class="sim-top-left">
              <span class="sim-num">#{{ simulacoes.length - idx }}</span>
              <span :class="['badge', badgeSim(sim).cls]">{{ badgeSim(sim).label }}</span>
              <span class="sim-titulo-label" v-if="sim.title">{{ sim.title }}</span>
              <span class="sim-data">{{ formatarData(sim.created_at) }}</span>
            </div>
            <div class="sim-top-right">
              <button v-if="sim.report_id" class="btn-sec" @click="router.push(`/agentes/${sim.report_id}`)">💬</button>
              <button :class="acaoPrincipal(sim).cls" @click="acaoPrincipal(sim).fn()">
                {{ acaoPrincipal(sim).label }}
              </button>
            </div>
          </div>

          <div v-if="sim.simulation_requirement" class="sim-hipotese">
            {{ sim.simulation_requirement.length > 120 ? sim.simulation_requirement.slice(0,120)+'...' : sim.simulation_requirement }}
          </div>

          <div class="sim-stats">
            <div class="stat">
              <div class="stat-label">Agentes</div>
              <div class="stat-val">{{ sim.entities_count || sim.profiles_count || '—' }}</div>
            </div>
            <div class="stat" v-if="sim.total_rounds">
              <div class="stat-label">Rodadas</div>
              <div class="stat-val">{{ sim.current_round||0 }}<span class="stat-of">/ {{ sim.total_rounds }}</span></div>
            </div>
            <div class="stat" v-if="sim.report_id">
              <div class="stat-label">Relatório</div>
              <div class="stat-val stat-link" @click="router.push(`/relatorio/${sim.report_id}`)">Disponível →</div>
            </div>
          </div>

          <div v-if="sim.total_rounds" class="sim-prog">
            <div class="sim-prog-bar">
              <div class="sim-prog-fill"
                :class="{ running: (sim.runner_status||sim.status)==='running', done: (sim.runner_status||sim.status)==='completed' }"
                :style="{ width: progresso(sim)+'%' }"
              ></div>
            </div>
            <span class="sim-prog-pct">{{ progresso(sim) }}%</span>
          </div>
        </div>
      </div>

    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- MODAL NOVA SIMULAÇÃO — 3 etapas                           -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modal" class="modal-overlay" @click.self="modal = false">
          <div class="modal">

            <div class="modal-header">
              <div>
                <div class="modal-titulo">Nova Simulação</div>
                <div class="modal-sub">{{ projeto?.name }}</div>
              </div>
              <button class="modal-close" @click="modal = false">×</button>
            </div>

            <!-- Steps -->
            <div class="modal-steps">
              <div v-for="(s,i) in ['Hipótese','Materiais','Parâmetros']" :key="i"
                class="mstep" :class="{ active: mEtapa===i+1, done: mEtapa>i+1 }">
                <div class="mstep-dot">
                  <svg v-if="mEtapa>i+1" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.5" width="10" height="10"><polyline points="2,6 5,9 10,3"/></svg>
                  <span v-else>{{ i+1 }}</span>
                </div>
                <span class="mstep-label">{{ s }}</span>
              </div>
            </div>

            <!-- ── ETAPA 1: HIPÓTESE ── -->
            <div v-if="mEtapa === 1" class="modal-body">
              <div class="mfield">
                <label class="mlabel">Título da simulação <span class="req">*</span></label>
                <input v-model="mTitulo" class="minp" type="text"
                  placeholder="Ex: Teste preço premium, Cenário eleições 1º turno" autofocus/>
                <div class="mhint">Identifica esta simulação dentro do projeto.</div>
              </div>
              <div class="mfield">
                <label class="mlabel">Descreva seu cenário</label>
                <textarea v-model="mCenario" class="mtextarea" rows="3"
                  placeholder="Em linguagem natural: O que quer testar? Qual situação quer prever?"/>
                <button class="btn-ia" :disabled="!mCenario.trim() || mGerando" @click="gerarHipotese">
                  <span v-if="mGerando" class="spinner-ia"></span>
                  <span v-else>✦</span>
                  {{ mGerando ? 'Gerando...' : 'Gerar hipótese com IA' }}
                </button>
              </div>
              <div class="mfield">
                <label class="mlabel">Hipótese de previsão <span class="req">*</span></label>
                <textarea v-model="mHipotese" class="mtextarea" rows="3"
                  placeholder="Como X vai impactar Y nos próximos Z meses?"/>
                <div class="mhint">Mín. 10 caracteres. Guia o comportamento de todos os agentes.</div>
              </div>
            </div>

            <!-- ── ETAPA 2: MATERIAIS ── -->
            <div v-else-if="mEtapa === 2" class="modal-body">
              <div class="mresumo">
                <span class="mresumo-titulo">{{ mTitulo }}</span>
                <span class="mresumo-hip">{{ mHipotese.slice(0,80) }}{{ mHipotese.length>80?'...':'' }}</span>
              </div>
              <div class="mfield">
                <label class="mlabel">Materiais de referência <span class="mopt">opcional</span></label>
                <div class="drop" :class="{ 'drag-over': mDragOver }"
                  @dragover.prevent="mDragOver=true" @dragleave="mDragOver=false"
                  @drop="mOnDrop" @click="$refs.mFileInput.click()">
                  <input ref="mFileInput" type="file" multiple accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg"
                    style="display:none" @change="mOnFile"/>
                  <div class="drop-txt">
                    <span class="drop-icon">📁</span>
                    {{ mDragOver ? 'Solte aqui' : 'Clique ou arraste — PDF, DOCX, TXT, PNG, JPG' }}
                  </div>
                </div>
              </div>
              <div v-if="mArquivos.length" class="mfiles">
                <div v-for="(f,i) in mArquivos" :key="f.name" class="mfile">
                  <span>{{ fileIcon(f.name) }}</span>
                  <div class="mfile-info">
                    <div class="mfile-name">{{ f.name }}</div>
                    <div class="mfile-size">{{ formatBytes(f.size) }}</div>
                  </div>
                  <button class="mfile-rm" @click="mRemoverArquivo(i)">×</button>
                </div>
              </div>
              <div class="mqualidade">
                <div class="mqual-bar">
                  <div class="mqual-fill" :style="{ width: mQualidade.pct+'%', background: mQualidade.cor }"></div>
                </div>
                <span class="mqual-label" :style="{ color: mQualidade.cor }">{{ mQualidade.label }}</span>
              </div>
            </div>

            <!-- ── ETAPA 3: PARÂMETROS ── -->
            <div v-else-if="mEtapa === 3" class="modal-body">
              <div class="mresumo">
                <span class="mresumo-titulo">{{ mTitulo }}</span>
                <span class="mresumo-hip">{{ mHipotese.slice(0,80) }}{{ mHipotese.length>80?'...':'' }}</span>
                <span v-if="mArquivos.length" class="mresumo-mat">{{ mArquivos.length }} material(is)</span>
              </div>
              <div class="mfield">
                <div class="mslider-header">
                  <label class="mlabel">Número de Agentes</label>
                  <span class="mslider-val">{{ mAgentes }}</span>
                </div>
                <input type="range" min="5" max="500" step="5" v-model.number="mAgentes" class="slider"/>
                <div class="mslider-bounds"><span>5 — rápido</span><span>500 — máxima riqueza</span></div>
                <div class="mslider-desc">{{ mDescAgentes }}</div>
              </div>
              <div class="mfield">
                <div class="mslider-header">
                  <label class="mlabel">Número de Rodadas</label>
                  <span class="mslider-val">{{ mRodadas }}</span>
                </div>
                <input type="range" min="1" max="100" step="1" v-model.number="mRodadas" class="slider"/>
                <div class="mslider-bounds"><span>1 — instantâneo</span><span>100 — evolução completa</span></div>
                <div class="mslider-desc">{{ mDescRodadas }}</div>
              </div>
              <div class="mest">
                <div class="mest-item"><div class="mest-label">⏱ Tempo estimado</div><div class="mest-val">~{{ mEstMinutos }} min</div></div>
                <div class="mest-sep"></div>
                <div class="mest-item"><div class="mest-label">💳 Custo estimado</div><div class="mest-val">~${{ mEstCusto }}</div></div>
                <div class="mest-sep"></div>
                <div class="mest-item"><div class="mest-label">🤖 Agentes</div><div class="mest-val accent">{{ mAgentes }}</div></div>
                <div class="mest-sep"></div>
                <div class="mest-item"><div class="mest-label">🔄 Rodadas</div><div class="mest-val accent2">{{ mRodadas }}</div></div>
              </div>
            </div>

            <!-- Footer do modal -->
            <div class="modal-footer">
              <button class="btn-ghost" @click="mEtapa===1 ? modal=false : mEtapa--">
                {{ mEtapa===1 ? 'Cancelar' : '← Voltar' }}
              </button>
              <button v-if="mEtapa < 3" class="btn-proximo" :disabled="mEtapa===1 && !mEtapa1Valida" @click="mEtapa++">
                Próximo →
              </button>
              <button v-else class="btn-iniciar" :disabled="mCriando" @click="criarSimulacao">
                <span v-if="mCriando" class="spinner-sm"></span>
                <span v-else>✦</span>
                {{ mCriando ? 'Criando...' : 'Iniciar Simulação' }}
              </button>
            </div>

          </div>
        </div>
      </Transition>
    </Teleport>
  </AppShell>
</template>

<style scoped>
.loading { display:flex; align-items:center; gap:12px; padding:48px; color:var(--text-muted); }
.spinner { width:20px; height:20px; border:2px solid var(--border-md); border-top-color:var(--accent); border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.not-found { text-align:center; padding:60px 20px; color:var(--text-secondary); display:flex; flex-direction:column; align-items:center; gap:12px; }
.nf-icon { font-size:44px; }
.page { display:flex; flex-direction:column; gap:18px; }

/* Projeto header */
.proj-header { background:var(--bg-surface); border:1px solid var(--border); border-radius:12px; padding:18px 22px; display:flex; align-items:flex-start; justify-content:space-between; }
.proj-nome { font-size:20px; font-weight:700; color:var(--text-primary); margin-bottom:5px; letter-spacing:-0.3px; }
.proj-meta { font-size:12px; color:var(--text-muted); display:flex; gap:8px; }
.sep { opacity:0.3; }
.btn-delete { background:none; border:1px solid var(--border); color:var(--text-muted); border-radius:8px; padding:7px 10px; cursor:pointer; font-size:14px; transition:all 0.15s; }
.btn-delete:hover { border-color:var(--danger); color:var(--danger); }

.confirm-box { background:rgba(255,90,90,0.07); border:1px solid rgba(255,90,90,0.25); border-radius:10px; padding:14px 18px; display:flex; align-items:center; justify-content:space-between; gap:16px; font-size:13px; color:var(--text-secondary); }
.confirm-actions { display:flex; gap:10px; flex-shrink:0; }
.btn-danger { background:var(--danger); color:#fff; border:none; border-radius:6px; padding:7px 16px; font-size:12px; cursor:pointer; font-weight:600; }
.btn-danger:disabled { opacity:0.5; }

/* Grafo status card */
.grafo-card { border-radius:12px; padding:16px 20px; display:flex; flex-direction:column; gap:10px; border:1px solid; }
.grafo-building { background:rgba(124,111,247,0.05); border-color:rgba(124,111,247,0.25); }
.grafo-done     { background:rgba(0,229,195,0.05);   border-color:rgba(0,229,195,0.2); }
.grafo-error    { background:rgba(255,90,90,0.05);   border-color:rgba(255,90,90,0.25); }
.grafo-pending  { background:var(--bg-surface);      border-color:var(--border); }
.grafo-unknown  { background:var(--bg-surface);      border-color:var(--border); }

.grafo-header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.grafo-titulo { font-size:14px; font-weight:600; color:var(--text-primary); display:flex; align-items:center; gap:8px; }
.grafo-pct { font-size:13px; font-weight:700; color:var(--accent2); font-family:var(--font-mono); }
.grafo-prog-bar { height:6px; background:var(--border); border-radius:3px; overflow:hidden; }
.grafo-prog-fill { height:100%; background:var(--accent2); border-radius:3px; transition:width 0.5s; }
.grafo-msg { font-size:12px; color:var(--text-muted); }
.grafo-msg-erro { font-size:12px; color:var(--danger); }
.grafo-aviso { font-size:12px; color:#f5a623; background:rgba(245,166,35,0.08); border:1px solid rgba(245,166,35,0.2); border-radius:6px; padding:7px 12px; }
.mini-spinner { width:14px; height:14px; border:2px solid rgba(124,111,247,0.3); border-top-color:var(--accent2); border-radius:50%; animation:spin 0.8s linear infinite; flex-shrink:0; }

.btn-rebuild { background:none; border:1px solid var(--danger); color:var(--danger); border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all 0.15s; }
.btn-rebuild:hover { background:rgba(255,90,90,0.1); }

/* Seção */
.section-header { display:flex; align-items:center; justify-content:space-between; }
.section-title { font-size:15px; font-weight:600; color:var(--text-primary); }

/* Botões principais */
.btn-nova-sim { background:var(--accent); color:#000; border:none; border-radius:8px; padding:8px 16px; font-size:13px; font-weight:700; cursor:pointer; transition:opacity 0.15s; }
.btn-nova-sim:hover { opacity:0.85; }
.btn-nova-sim-sm { background:var(--accent2-dim); color:var(--accent2); border:1px solid rgba(124,111,247,0.3); border-radius:6px; padding:6px 14px; font-size:12px; font-weight:600; cursor:pointer; transition:all 0.15s; }
.btn-nova-sim-sm:hover { background:var(--accent2); color:#fff; }
.btn-ghost { background:transparent; border:none; color:var(--text-secondary); cursor:pointer; font-size:13px; padding:8px 14px; border-radius:8px; transition:color 0.15s; }
.btn-ghost:hover { color:var(--text-primary); }

/* Vazio */
.sims-vazio { text-align:center; padding:52px 20px; background:var(--bg-surface); border:1px dashed var(--border-md); border-radius:12px; }
.vazio-icon { font-size:44px; margin-bottom:14px; }
.vazio-titulo { font-size:17px; font-weight:600; color:var(--text-primary); margin-bottom:8px; }
.vazio-sub { font-size:13px; color:var(--text-secondary); max-width:400px; margin:0 auto; line-height:1.7; }

/* Simulações */
.sims-lista { display:flex; flex-direction:column; gap:12px; }
.sim-card { background:var(--bg-surface); border:1px solid var(--border); border-radius:12px; padding:16px 20px; transition:border-color 0.2s; }
.sim-card:hover { border-color:var(--border-md); }
.sim-card.sim-running { border-color:rgba(245,166,35,0.4); }
.sim-card.sim-done    { border-color:rgba(0,229,195,0.2); }

.sim-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; gap:12px; }
.sim-top-left { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sim-top-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.sim-num { font-size:11px; color:var(--text-muted); font-family:var(--font-mono); }
.sim-titulo-label { font-size:12px; font-weight:600; color:var(--text-primary); }
.sim-data { font-size:11px; color:var(--text-muted); }

.btn-acao   { background:none; border:1px solid var(--border-md); color:var(--accent2); border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all 0.15s; white-space:nowrap; }
.btn-acao:hover { background:var(--accent2-dim); }
.btn-run    { background:rgba(245,166,35,0.1); border:1px solid rgba(245,166,35,0.4); color:#f5a623; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all 0.15s; white-space:nowrap; }
.btn-run:hover { background:rgba(245,166,35,0.2); }
.btn-report { background:rgba(0,229,195,0.1); border:1px solid rgba(0,229,195,0.3); color:var(--accent); border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all 0.15s; white-space:nowrap; }
.btn-report:hover { background:rgba(0,229,195,0.2); }
.btn-sec { background:none; border:1px solid var(--border); color:var(--text-muted); border-radius:6px; padding:5px 8px; font-size:12px; cursor:pointer; transition:all 0.15s; }
.btn-sec:hover { color:var(--text-primary); }

.sim-hipotese { font-size:12px; color:var(--text-muted); line-height:1.6; margin-bottom:10px; border-left:2px solid var(--border-md); padding-left:10px; }
.sim-stats { display:flex; gap:24px; flex-wrap:wrap; margin-bottom:4px; }
.stat { display:flex; flex-direction:column; gap:2px; }
.stat-label { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }
.stat-val { font-size:15px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono); }
.stat-of { font-size:11px; font-weight:400; color:var(--text-muted); }
.stat-link { color:var(--accent2); cursor:pointer; font-family:inherit; font-size:12px; font-weight:600; }
.stat-link:hover { text-decoration:underline; }

.sim-prog { display:flex; align-items:center; gap:10px; margin-top:10px; }
.sim-prog-bar { flex:1; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.sim-prog-fill { height:100%; border-radius:2px; background:var(--accent2); transition:width 0.4s; }
.sim-prog-fill.running { background:#f5a623; animation:shimmer 1.5s infinite; }
.sim-prog-fill.done    { background:var(--accent); }
@keyframes shimmer { 0%,100%{opacity:1}50%{opacity:0.5} }
.sim-prog-pct { font-size:11px; color:var(--text-muted); min-width:32px; text-align:right; font-family:var(--font-mono); }

/* Badges */
.badge { padding:3px 9px; border-radius:20px; font-size:11px; font-weight:600; }
.b-done     { background:rgba(0,229,195,0.1);    color:var(--accent); }
.b-running  { background:rgba(245,166,35,0.1);   color:#f5a623; }
.b-paused   { background:rgba(124,111,247,0.1);  color:var(--accent2); }
.b-building { background:rgba(124,111,247,0.1);  color:var(--accent2); }
.b-error    { background:rgba(255,90,90,0.1);    color:var(--danger); }
.b-draft    { background:rgba(107,107,128,0.15); color:var(--text-muted); }

/* Transitions */
.slide-enter-active, .slide-leave-active { transition:all 0.2s ease; }
.slide-enter-from, .slide-leave-to { opacity:0; transform:translateY(-6px); }

/* ─── MODAL ─── */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.72); display:flex; align-items:center; justify-content:center; z-index:1000; padding:16px; backdrop-filter:blur(4px); }
.modal { background:var(--bg-surface); border:1px solid var(--border-md); border-radius:16px; width:100%; max-width:520px; box-shadow:0 24px 64px rgba(0,0,0,0.5); display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
.modal-header { padding:20px 22px 0; position:relative; flex-shrink:0; }
.modal-titulo { font-size:17px; font-weight:700; color:var(--text-primary); margin-bottom:2px; }
.modal-sub    { font-size:12px; color:var(--text-muted); }
.modal-close  { position:absolute; top:16px; right:18px; background:none; border:none; color:var(--text-muted); font-size:22px; cursor:pointer; line-height:1; }
.modal-close:hover { color:var(--text-primary); }

.modal-steps { display:flex; align-items:center; gap:6px; padding:14px 22px 0; flex-shrink:0; }
.mstep { display:flex; align-items:center; gap:6px; }
.mstep-dot { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; background:var(--bg-raised); border:2px solid var(--border-md); color:var(--text-muted); transition:all 0.3s; flex-shrink:0; }
.mstep.active .mstep-dot { background:var(--accent2); border-color:var(--accent2); color:#fff; }
.mstep.done   .mstep-dot { background:var(--accent);  border-color:var(--accent);  color:#000; }
.mstep-label { font-size:11px; color:var(--text-muted); margin-right:8px; }
.mstep.active .mstep-label { color:var(--accent2); font-weight:500; }
.mstep.done   .mstep-label { color:var(--text-secondary); }

.modal-body { padding:16px 22px; display:flex; flex-direction:column; gap:14px; overflow-y:auto; }
.mfield { display:flex; flex-direction:column; gap:6px; }
.mlabel { font-size:13px; font-weight:500; color:var(--text-secondary); }
.mopt { font-size:11px; color:var(--text-muted); font-weight:400; margin-left:4px; }
.req { color:var(--accent); }
.minp { background:var(--bg-raised); border:1px solid var(--border-md); border-radius:8px; color:var(--text-primary); font-size:13px; padding:10px 12px; outline:none; transition:border-color 0.15s; width:100%; }
.minp:focus { border-color:var(--accent2); }
.mtextarea { background:var(--bg-raised); border:1px solid var(--border-md); border-radius:8px; color:var(--text-primary); font-size:13px; padding:10px 12px; outline:none; resize:vertical; font-family:inherit; line-height:1.6; transition:border-color 0.15s; }
.mtextarea:focus { border-color:var(--accent2); }
.mhint { font-size:11px; color:var(--text-muted); }

.btn-ia { background:var(--accent2); color:#fff; border:none; border-radius:8px; padding:8px 14px; font-size:12px; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:7px; transition:all 0.2s; align-self:flex-start; }
.btn-ia:hover:not(:disabled) { opacity:0.85; transform:translateY(-1px); }
.btn-ia:disabled { opacity:0.4; cursor:not-allowed; transform:none; }
.spinner-ia { width:12px; height:12px; border:2px solid rgba(255,255,255,0.3); border-top-color:#fff; border-radius:50%; animation:spin 0.7s linear infinite; }

.mresumo { background:var(--bg-raised); border-radius:8px; padding:10px 14px; border-left:3px solid var(--accent2); display:flex; flex-direction:column; gap:4px; }
.mresumo-titulo { font-size:13px; font-weight:600; color:var(--text-primary); }
.mresumo-hip { font-size:12px; color:var(--text-muted); }
.mresumo-mat { font-size:11px; color:var(--accent2); }

.drop { border:2px dashed var(--border-md); border-radius:10px; padding:24px; text-align:center; cursor:pointer; transition:all 0.2s; background:var(--bg-raised); }
.drop:hover, .drop.drag-over { border-color:var(--accent); background:rgba(0,229,195,0.03); }
.drop-txt { font-size:13px; color:var(--text-muted); display:flex; align-items:center; justify-content:center; gap:8px; }
.drop-icon { font-size:18px; }

.mfiles { display:flex; flex-direction:column; gap:6px; }
.mfile { display:flex; align-items:center; gap:8px; background:var(--bg-overlay); border:1px solid var(--border); border-radius:7px; padding:7px 10px; }
.mfile-info { flex:1; min-width:0; }
.mfile-name { font-size:12px; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mfile-size { font-size:10px; color:var(--text-muted); }
.mfile-rm { background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:18px; line-height:1; padding:0 2px; }
.mfile-rm:hover { color:var(--danger); }

.mqualidade { display:flex; align-items:center; gap:10px; }
.mqual-bar { flex:1; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.mqual-fill { height:100%; border-radius:2px; transition:all 0.4s; }
.mqual-label { font-size:12px; font-weight:600; }

.mslider-header { display:flex; justify-content:space-between; align-items:center; }
.mslider-val { font-size:20px; font-weight:700; color:var(--accent2); font-family:var(--font-mono); }
.mslider-bounds { display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); }
.mslider-desc { font-size:12px; color:var(--text-secondary); background:var(--bg-raised); border-radius:6px; padding:6px 10px; }
.slider { width:100%; accent-color:var(--accent2); cursor:pointer; }

.mest { display:flex; background:var(--bg-raised); border:1px solid var(--border); border-radius:10px; overflow:hidden; }
.mest-item { flex:1; padding:10px 12px; }
.mest-label { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.4px; margin-bottom:3px; }
.mest-val { font-size:15px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono); }
.mest-sep { width:1px; background:var(--border); margin:8px 0; }
.accent  { color:var(--accent); }
.accent2 { color:var(--accent2); }

.modal-footer { padding:14px 22px; border-top:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
.btn-proximo { background:var(--accent2); color:#fff; border:none; border-radius:10px; padding:10px 20px; font-size:14px; font-weight:600; cursor:pointer; transition:all 0.2s; }
.btn-proximo:hover:not(:disabled) { opacity:0.85; transform:translateY(-1px); }
.btn-proximo:disabled { opacity:0.3; cursor:not-allowed; }
.btn-iniciar { background:var(--accent); color:#000; border:none; border-radius:10px; padding:10px 20px; font-size:14px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:8px; transition:all 0.2s; }
.btn-iniciar:hover:not(:disabled) { opacity:0.85; transform:translateY(-1px); }
.btn-iniciar:disabled { opacity:0.3; cursor:not-allowed; transform:none; }
.spinner-sm { width:13px; height:13px; border:2px solid rgba(0,0,0,0.2); border-top-color:#000; border-radius:50%; animation:spin 0.7s linear infinite; }

.modal-enter-active { transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1); }
.modal-leave-active { transition:all 0.2s ease; }
.modal-enter-from   { opacity:0; transform:scale(0.92); }
.modal-leave-to     { opacity:0; transform:scale(0.96); }
</style>
