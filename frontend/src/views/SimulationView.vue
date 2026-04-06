<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import service from '../api'

const route  = useRoute()
const router = useRouter()

// ─── Fase da view ─────────────────────────────────────────────
// 'config'   → tela de configuração de agentes/rodadas
// 'pipeline' → pipeline em execução
const tela = ref('config')

// ─── Configuração escolhida pelo usuário ──────────────────────
const cfgAgentes = ref(50)
const cfgRodadas = ref(20)

const descricaoAgentes = computed(() => {
  if (cfgAgentes.value <= 20)  return 'Teste rápido — ideal para validar a hipótese'
  if (cfgAgentes.value <= 100) return 'Bom equilíbrio entre velocidade e precisão'
  if (cfgAgentes.value <= 250) return 'Alta fidelidade — captura nuances importantes'
  return 'Máxima riqueza — simulação de alta complexidade'
})
const descricaoRodadas = computed(() => {
  if (cfgRodadas.value <= 5)  return 'Reação imediata ao evento'
  if (cfgRodadas.value <= 25) return 'Captura tendências de curto prazo'
  if (cfgRodadas.value <= 60) return 'Evolução completa da opinião ao longo do tempo'
  return 'Análise profunda — evolução de longo prazo'
})
const estimativaMinutos = computed(() =>
  Math.round(Math.max(2, cfgAgentes.value * cfgRodadas.value * 0.04))
)
const estimativaCusto = computed(() =>
  (cfgAgentes.value * cfgRodadas.value * 0.0008).toFixed(2)
)

// ─── Estado do pipeline ───────────────────────────────────────
const phase      = ref('init')
const error      = ref('')
const progress   = ref(0)
const statusMsg  = ref('Iniciando...')
const detalhe    = ref('')
const projectData = ref(null)
const simulationId = ref(null)
const abortado   = ref(false)

let pollTimer = null

// ─── Fases visuais ────────────────────────────────────────────
const fases = [
  { key: 'building_graph', label: 'Construindo Grafo',    desc: 'Analisando documentos e criando rede de conhecimento' },
  { key: 'creating_sim',   label: 'Criando Simulação',    desc: 'Configurando o ambiente de simulação' },
  { key: 'preparing',      label: 'Gerando Agentes',      desc: 'Criando perfis únicos para cada agente com IA' },
  { key: 'starting',       label: 'Iniciando',            desc: 'Lançando a simulação multiagente' },
]
const faseAtual   = computed(() => fases.findIndex(f => f.key === phase.value))
const phaseLabel  = computed(() => {
  if (phase.value === 'running') return 'Simulação Iniciada! ✅'
  if (phase.value === 'error')   return 'Erro no pipeline'
  if (phase.value === 'aborted') return 'Simulação cancelada'
  return fases.find(f => f.key === phase.value)?.label || 'Inicializando...'
})

// ─── Tradução de mensagens ────────────────────────────────────
function traduzir(msg) {
  if (!msg) return ''
  if (/[\u4e00-\u9fff]/.test(msg)) return 'Processando...'
  const map = [
    ['building',    'Construindo grafo de conhecimento...'],
    ['entity',      'Extraindo entidades e relacionamentos...'],
    ['chunk',       'Processando blocos de texto...'],
    ['batch',       'Processando lote de dados...'],
    ['sending',     'Enviando dados para o grafo...'],
    ['graph',       'Atualizando grafo de conhecimento...'],
    ['completed',   'Concluído com sucesso!'],
    ['preparing',   'Preparando agentes de IA...'],
    ['generating',  'Gerando perfis dos agentes...'],
    ['profile',     'Criando perfil do agente...'],
    ['ready',       'Tudo pronto!'],
    ['starting',    'Iniciando simulação...'],
    ['processing',  'Processando...'],
    ['analyzing',   'Analisando documentos...'],
    ['extracting',  'Extraindo informações...'],
  ]
  const lower = msg.toLowerCase()
  for (const [k, v] of map) if (lower.includes(k)) return v
  return msg
}

// ─── Iniciar pipeline ─────────────────────────────────────────
function iniciarPipeline() {
  tela.value = 'pipeline'
  runPipeline().catch(handleError)
}

// ─── Abortar ──────────────────────────────────────────────────
async function abortar() {
  abortado.value = true
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }

  // Se já criou simulação, tentar parar
  if (simulationId.value) {
    try { await service.post('/api/simulation/stop', { simulation_id: simulationId.value }) } catch { /* ignorar */ }
  }

  phase.value = 'aborted'
  progress.value = 0
  statusMsg.value = 'Simulação cancelada pelo usuário.'
  detalhe.value = ''
}

function voltar() {
  const projectId = route.params.projectId
  if (projectId) router.push(`/projeto/${projectId}`)
  else router.push('/')
}

// ─── Pipeline principal ───────────────────────────────────────
async function runPipeline() {
  const projectId = route.params.projectId

  phase.value    = 'building_graph'
  statusMsg.value = 'Verificando construção do grafo...'
  detalhe.value  = 'Isso pode levar alguns minutos dependendo do tamanho dos documentos.'
  progress.value = 5

  const project = await getProject(projectId)
  projectData.value = project

  if (abortado.value) return

  if (project.status === 'graph_building' && project.graph_build_task_id) {
    statusMsg.value = 'Construindo rede de conhecimento...'
    await waitForGraphBuild(project.graph_build_task_id, projectId)
  } else if (project.status === 'ontology_generated') {
    phase.value = 'error'
    error.value = 'O build do grafo não foi iniciado. Volte e crie o projeto novamente.'
    return
  }

  if (abortado.value) return

  const updated = await getProject(projectId)
  projectData.value = updated
  if (!updated.graph_id) {
    phase.value = 'error'
    error.value = 'Grafo construído mas ID não encontrado. Tente novamente.'
    return
  }

  if (abortado.value) return

  // Criar simulação
  phase.value     = 'creating_sim'
  statusMsg.value = 'Criando registro da simulação...'
  detalhe.value   = ''
  progress.value  = 45

  const simData = await createSimulation(projectId, updated.graph_id)
  simulationId.value = simData.simulation_id

  if (abortado.value) return

  // Preparar agentes
  phase.value     = 'preparing'
  statusMsg.value = 'Gerando perfis dos agentes com IA...'
  detalhe.value   = 'Cada agente recebe uma personalidade, histórico e comportamento únicos.'
  progress.value  = 50

  const prepResult = await prepareSimulation(simData.simulation_id)
  if (prepResult.already_prepared) {
    statusMsg.value = 'Agentes já estavam prontos!'
    progress.value  = 85
  } else if (prepResult.task_id) {
    await waitForPrepare(prepResult.task_id, simData.simulation_id)
  }

  if (abortado.value) return

  // Iniciar
  phase.value     = 'starting'
  statusMsg.value = 'Lançando simulação...'
  detalhe.value   = 'Os agentes estão sendo ativados.'
  progress.value  = 90

  await startSimulation(simData.simulation_id)

  if (abortado.value) return

  // Pronto!
  phase.value     = 'running'
  statusMsg.value = 'Simulação iniciada com sucesso!'
  detalhe.value   = 'Redirecionando para o monitoramento ao vivo...'
  progress.value  = 100

  setTimeout(() => {
    if (!abortado.value) router.push(`/simulacao/${simData.simulation_id}/executar`)
  }, 1800)
}

// ─── API helpers ──────────────────────────────────────────────
async function getProject(id) {
  const res = await service.get(`/api/graph/project/${id}`)
  return res.data || res
}
async function createSimulation(projectId, graphId) {
  const res = await service.post('/api/simulation/create', { project_id: projectId, graph_id: graphId })
  return res.data || res
}
async function prepareSimulation(simId) {
  const res = await service.post('/api/simulation/prepare', { simulation_id: simId })
  return res.data || res
}
async function startSimulation(simId) {
  const res = await service.post('/api/simulation/start', {
    simulation_id: simId,
    platform:   'parallel',
    max_rounds: cfgRodadas.value
  })
  return res.data || res
}

// ─── Polling do grafo ─────────────────────────────────────────
function waitForGraphBuild(taskId, projectId) {
  return new Promise((resolve, reject) => {
    let elapsed = 0
    const maxWait = 900000
    const interval = 5000
    pollTimer = setInterval(async () => {
      if (abortado.value) { clearInterval(pollTimer); resolve(); return }
      elapsed += interval
      if (elapsed > maxWait) { clearInterval(pollTimer); reject(new Error('Timeout: construção do grafo demorou mais de 15 minutos.')); return }
      try {
        const res  = await service.get(`/api/graph/task/${taskId}`)
        const task = res.data || res
        if (task.progress) progress.value = 5 + Math.round((task.progress / 100) * 35)
        if (task.message)  { statusMsg.value = traduzir(task.message); detalhe.value = '' }
        if (task.status === 'completed') { clearInterval(pollTimer); resolve() }
        else if (task.status === 'failed') {
          clearInterval(pollTimer)
          reject(new Error(traduzir(task.error || task.message) || 'Falha na construção do grafo.'))
        }
      } catch {
        try {
          const proj = await getProject(projectId)
          if (proj.status === 'graph_completed') { clearInterval(pollTimer); resolve() }
        } catch { /* ignorar */ }
      }
    }, interval)
  })
}

// ─── Polling da preparação ───────────────────────────────────
function waitForPrepare(taskId, simId) {
  return new Promise((resolve, reject) => {
    let elapsed = 0
    const maxWait = 900000
    const interval = 5000
    pollTimer = setInterval(async () => {
      if (abortado.value) { clearInterval(pollTimer); resolve(); return }
      elapsed += interval
      if (elapsed > maxWait) { clearInterval(pollTimer); reject(new Error('Timeout: preparação demorou mais de 15 minutos.')); return }
      try {
        const res  = await service.post('/api/simulation/prepare/status', { task_id: taskId, simulation_id: simId })
        const data = res.data || res
        if (data.progress) progress.value = 50 + Math.round((data.progress / 100) * 35)
        if (data.message)  { statusMsg.value = traduzir(data.message); detalhe.value = '' }
        if (data.status === 'ready' || data.status === 'completed' || data.already_prepared) {
          clearInterval(pollTimer); progress.value = 85; resolve()
        } else if (data.status === 'failed') {
          clearInterval(pollTimer)
          reject(new Error(traduzir(data.message) || 'Falha na preparação dos agentes.'))
        }
      } catch (e) { console.warn('prepare status error:', e) }
    }, interval)
  })
}

function handleError(e) {
  if (abortado.value) return
  phase.value = 'error'
  error.value = e?.response?.data?.error || e?.message || 'Erro inesperado. Tente novamente.'
}

function retry() {
  abortado.value  = false
  error.value     = ''
  phase.value     = 'init'
  progress.value  = 0
  statusMsg.value = 'Reiniciando...'
  runPipeline().catch(handleError)
}

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <AppShell title="Nova Simulação">

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- TELA DE CONFIGURAÇÃO                                       -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div v-if="tela === 'config'" class="config-wrap">

      <div class="config-header">
        <div>
          <h1 class="config-titulo">Configurar Simulação</h1>
          <p class="config-sub">Defina o número de agentes e rodadas antes de iniciar.</p>
        </div>
        <button class="btn-ghost" @click="voltar()">← Voltar ao projeto</button>
      </div>

      <div class="config-card">

        <!-- Info do projeto -->
        <div v-if="projectData" class="proj-info">
          <span class="proj-info-label">Projeto:</span>
          <span class="proj-info-nome">{{ projectData.name }}</span>
        </div>

        <!-- Agentes -->
        <div class="param-block">
          <div class="param-header">
            <label class="param-label">Número de Agentes</label>
            <span class="param-val">{{ cfgAgentes }}</span>
          </div>
          <input type="range" min="5" max="500" step="5" v-model.number="cfgAgentes" class="slider"/>
          <div class="param-bounds">
            <span>5 — teste rápido</span>
            <span>500 — máxima riqueza</span>
          </div>
          <div class="param-desc">{{ descricaoAgentes }}</div>
        </div>

        <!-- Rodadas -->
        <div class="param-block">
          <div class="param-header">
            <label class="param-label">Número de Rodadas</label>
            <span class="param-val">{{ cfgRodadas }}</span>
          </div>
          <input type="range" min="1" max="100" step="1" v-model.number="cfgRodadas" class="slider"/>
          <div class="param-bounds">
            <span>1 — instantâneo</span>
            <span>100 — evolução completa</span>
          </div>
          <div class="param-desc">{{ descricaoRodadas }}</div>
        </div>

        <!-- Estimativas -->
        <div class="estimativas">
          <div class="est-item">
            <div class="est-label">⏱ Tempo estimado</div>
            <div class="est-val">~{{ estimativaMinutos }} min</div>
          </div>
          <div class="est-sep"></div>
          <div class="est-item">
            <div class="est-label">💳 Custo estimado</div>
            <div class="est-val">~${{ estimativaCusto }}</div>
          </div>
          <div class="est-sep"></div>
          <div class="est-item">
            <div class="est-label">🤖 Agentes</div>
            <div class="est-val accent">{{ cfgAgentes }}</div>
          </div>
          <div class="est-sep"></div>
          <div class="est-item">
            <div class="est-label">🔄 Rodadas</div>
            <div class="est-val accent2">{{ cfgRodadas }}</div>
          </div>
        </div>

        <!-- Botão iniciar -->
        <button class="btn-iniciar" @click="iniciarPipeline">
          ✦ Iniciar Simulação
        </button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- TELA DE PIPELINE                                           -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <div v-else class="pipeline">

      <!-- Barra de progresso global -->
      <div class="prog-global">
        <div class="prog-bar">
          <div
            class="prog-fill"
            :class="{ 'prog-error': phase === 'error' || phase === 'aborted', 'prog-done': phase === 'running' }"
            :style="{ width: progress + '%' }"
          ></div>
        </div>
        <span class="prog-pct">{{ progress }}%</span>
      </div>

      <!-- Card central de status -->
      <div class="status-card"
        :class="{ 'card-error': phase === 'error', 'card-done': phase === 'running', 'card-aborted': phase === 'aborted' }">

        <div class="status-icon" :class="phase">
          <svg v-if="phase === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="30" height="30">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <svg v-else-if="phase === 'aborted'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="30" height="30">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <svg v-else-if="phase === 'running'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="30" height="30">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          <div v-else class="spinner-icon"></div>
        </div>

        <h2 class="status-titulo">{{ phaseLabel }}</h2>
        <p class="status-msg">{{ statusMsg }}</p>
        <p v-if="detalhe" class="status-detalhe">{{ detalhe }}</p>

        <div v-if="phase === 'building_graph'" class="aviso-tempo">
          ⏱ Este processo pode levar entre 2 e 15 minutos. Não feche esta aba.
        </div>
        <div v-if="phase === 'preparing'" class="aviso-tempo">
          ⏱ Geração dos perfis pode levar alguns minutos. Aguarde.
        </div>

        <!-- Botão ABORTAR — visível enquanto pipeline roda -->
        <button
          v-if="phase !== 'running' && phase !== 'error' && phase !== 'aborted'"
          class="btn-abortar"
          @click="abortar"
        >
          ✕ Cancelar simulação
        </button>
      </div>

      <!-- Timeline de fases -->
      <div class="timeline">
        <div v-for="(fase, idx) in fases" :key="fase.key" class="tl-item">
          <div class="tl-left">
            <div class="tl-dot"
              :class="{
                'tl-active': phase === fase.key,
                'tl-done':   faseAtual > idx || phase === 'running',
                'tl-error':  (phase === 'error' || phase === 'aborted') && faseAtual === idx
              }"
            >
              <svg v-if="faseAtual > idx || phase === 'running'" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
                <polyline points="2,6 5,9 10,3"/>
              </svg>
              <div v-else-if="phase === fase.key && phase !== 'error' && phase !== 'aborted'" class="dot-spin"></div>
            </div>
            <div v-if="idx < fases.length - 1" class="tl-line" :class="{ 'tl-line-done': faseAtual > idx || phase === 'running' }"></div>
          </div>
          <div class="tl-content"
            :class="{ 'tl-content-active': phase === fase.key, 'tl-content-done': faseAtual > idx || phase === 'running' }">
            <div class="tl-label">{{ fase.label }}</div>
            <div class="tl-desc">{{ fase.desc }}</div>
          </div>
        </div>
      </div>

      <!-- Erro -->
      <div v-if="phase === 'error'" class="error-card">
        <div class="error-icon">⚠️</div>
        <div class="error-msg">{{ error }}</div>
        <div class="error-actions">
          <button class="btn-ghost" @click="voltar()">← Voltar ao projeto</button>
          <button class="btn-retry" @click="retry">↺ Tentar novamente</button>
        </div>
      </div>

      <!-- Cancelado -->
      <div v-if="phase === 'aborted'" class="error-card card-aborted-box">
        <div class="error-icon">🚫</div>
        <div class="error-msg">Simulação cancelada. Nenhum dado foi perdido.</div>
        <div class="error-actions">
          <button class="btn-ghost" @click="voltar()">← Voltar ao projeto</button>
          <button class="btn-retry" @click="tela = 'config'; abortado = false; phase = 'init'; progress = 0">
            ↺ Configurar novamente
          </button>
        </div>
      </div>

      <!-- Info do projeto -->
      <div v-if="projectData && phase !== 'error' && phase !== 'aborted'" class="info-card">
        <div class="info-title">Simulação em andamento</div>
        <div class="info-row">
          <span class="info-key">Projeto</span>
          <span class="info-val">{{ projectData.name }}</span>
        </div>
        <div class="info-row">
          <span class="info-key">Agentes</span>
          <span class="info-val accent">{{ cfgAgentes }}</span>
        </div>
        <div class="info-row">
          <span class="info-key">Rodadas</span>
          <span class="info-val accent2">{{ cfgRodadas }}</span>
        </div>
        <div class="info-row">
          <span class="info-key">Materiais</span>
          <span class="info-val">{{ (projectData.files || []).length }} arquivo(s)</span>
        </div>
      </div>

    </div>
  </AppShell>
</template>

<style scoped>
/* ─── TELA CONFIG ─── */
.config-wrap { max-width: 600px; margin: 0 auto; padding: 8px 0 60px; display: flex; flex-direction: column; gap: 20px; }
.config-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.config-titulo { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; letter-spacing: -0.5px; }
.config-sub { font-size: 13px; color: var(--text-secondary); margin: 0; }

.config-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 14px; padding: 28px; display: flex; flex-direction: column; gap: 24px; }

.proj-info { background: var(--bg-raised); border-radius: 8px; padding: 10px 14px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.proj-info-label { color: var(--text-muted); }
.proj-info-nome  { color: var(--text-primary); font-weight: 500; }

.param-block { display: flex; flex-direction: column; gap: 8px; }
.param-header { display: flex; justify-content: space-between; align-items: center; }
.param-label { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.param-val { font-size: 22px; font-weight: 700; color: var(--accent2); font-family: var(--font-mono); }
.param-bounds { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }
.param-desc { font-size: 12px; color: var(--text-secondary); background: var(--bg-raised); border-radius: 6px; padding: 8px 12px; }
.slider { width: 100%; accent-color: var(--accent2); cursor: pointer; }

.estimativas { display: flex; background: var(--bg-raised); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.est-item { flex: 1; padding: 12px 14px; }
.est-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.est-val { font-size: 16px; font-weight: 700; color: var(--text-primary); font-family: var(--font-mono); }
.est-sep { width: 1px; background: var(--border); margin: 8px 0; }
.accent  { color: var(--accent); }
.accent2 { color: var(--accent2); }

.btn-iniciar {
  background: var(--accent); color: #000; border: none; border-radius: 12px;
  padding: 15px 32px; font-size: 16px; font-weight: 700; cursor: pointer;
  transition: all 0.2s; letter-spacing: -0.3px;
}
.btn-iniciar:hover { opacity: 0.85; transform: translateY(-2px); }

/* ─── PIPELINE ─── */
.pipeline { max-width: 580px; margin: 0 auto; padding: 8px 0 60px; display: flex; flex-direction: column; gap: 20px; }

.prog-global { display: flex; align-items: center; gap: 12px; }
.prog-bar { flex: 1; height: 8px; background: var(--bg-overlay); border-radius: 999px; overflow: hidden; }
.prog-fill { height: 100%; border-radius: 999px; background: var(--accent); transition: width 0.6s ease; }
.prog-fill.prog-error   { background: var(--danger); }
.prog-fill.prog-done    { background: var(--accent); }
.prog-pct { font-size: 13px; color: var(--text-secondary); min-width: 38px; text-align: right; font-family: var(--font-mono); }

.status-card {
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: 16px; padding: 32px 28px; text-align: center;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  transition: border-color 0.4s;
}
.status-card.card-error   { border-color: rgba(255,90,90,0.3); }
.status-card.card-done    { border-color: rgba(0,229,195,0.3); }
.status-card.card-aborted { border-color: rgba(255,90,90,0.2); }

.status-icon { width: 64px; height: 64px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--accent-dim); color: var(--accent); margin-bottom: 4px; }
.status-icon.error, .status-icon.aborted { background: rgba(255,90,90,0.12); color: var(--danger); }
.status-icon.running { background: var(--accent-dim); color: var(--accent); }

.spinner-icon { width: 32px; height: 32px; border: 3px solid var(--accent-dim); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.status-titulo { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0; }
.status-msg    { font-size: 14px; color: var(--text-secondary); margin: 0; }
.status-detalhe{ font-size: 12px; color: var(--text-muted); margin: 0; font-style: italic; }

.aviso-tempo {
  font-size: 12px; color: #f5a623;
  background: rgba(245,166,35,0.08); border: 1px solid rgba(245,166,35,0.2);
  border-radius: 8px; padding: 8px 14px; margin-top: 4px;
}

/* Botão abortar */
.btn-abortar {
  background: none; border: 1px solid rgba(255,90,90,0.4); color: var(--danger);
  border-radius: 8px; padding: 7px 18px; font-size: 12px; cursor: pointer;
  margin-top: 6px; transition: all 0.2s;
}
.btn-abortar:hover { background: rgba(255,90,90,0.08); border-color: var(--danger); }

/* Timeline */
.timeline { display: flex; flex-direction: column; gap: 0; }
.tl-item { display: flex; gap: 14px; }
.tl-left { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.tl-dot { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: var(--bg-overlay); border: 2px solid var(--border-md); color: var(--text-muted); transition: all 0.3s; flex-shrink: 0; }
.tl-dot.tl-active { border-color: var(--accent2); background: var(--accent2); color: #fff; }
.tl-dot.tl-done   { border-color: var(--accent);  background: var(--accent);  color: #000; }
.tl-dot.tl-error  { border-color: var(--danger);  background: rgba(255,90,90,0.1); color: var(--danger); }
.dot-spin { width: 12px; height: 12px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; }
.tl-line { width: 2px; flex: 1; background: var(--border-md); margin: 4px 0; min-height: 20px; transition: background 0.4s; }
.tl-line.tl-line-done { background: var(--accent); }
.tl-content { padding: 4px 0 16px; }
.tl-label { font-size: 13px; font-weight: 600; color: var(--text-muted); transition: color 0.3s; }
.tl-desc  { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.tl-content.tl-content-active .tl-label { color: var(--accent2); }
.tl-content.tl-content-done   .tl-label { color: var(--text-secondary); }

/* Erro / cancelado */
.error-card { background: rgba(255,90,90,0.07); border: 1px solid rgba(255,90,90,0.25); border-radius: 12px; padding: 20px 24px; display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center; }
.card-aborted-box { background: rgba(107,107,128,0.07); border-color: rgba(107,107,128,0.2); }
.error-icon { font-size: 32px; }
.error-msg  { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }
.error-actions { display: flex; gap: 12px; }

.btn-ghost { background: none; border: 1px solid var(--border); color: var(--text-secondary); border-radius: 8px; padding: 8px 16px; font-size: 13px; cursor: pointer; transition: all 0.15s; }
.btn-ghost:hover { color: var(--text-primary); border-color: var(--border-md); }
.btn-retry { background: var(--accent2); color: #fff; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s; }
.btn-retry:hover { opacity: 0.85; }

/* Info card */
.info-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.info-title { font-size: 11px; font-weight: 600; color: var(--text-muted); padding: 10px 16px 6px; text-transform: uppercase; letter-spacing: 0.6px; }
.info-row { display: flex; justify-content: space-between; padding: 8px 16px; border-top: 1px solid var(--border); font-size: 13px; }
.info-key { color: var(--text-muted); }
.info-val { color: var(--text-primary); font-weight: 500; }
</style>
