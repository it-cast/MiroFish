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

// ─── Status do grafo (interno, não domina a UI) ───────────────
const grafoOk      = ref(false)  // true = pode criar simulação
const grafoBuilding = ref(false) // true = está construindo
const grafoPct     = ref(0)
const grafoErro    = ref('')
let   grafoTimer   = null

// ─── Modal nova simulação ─────────────────────────────────────
const modal    = ref(false)
const mEtapa   = ref(1)  // 1=hipótese, 2=parâmetros
const mTitulo  = ref('')
const mCenario = ref('')
const mHipotese = ref('')
const mAgentes = ref(50)
const mRodadas = ref(20)
const mGerando = ref(false)
const mCriando = ref(false)

const pid = computed(() => route.params.projectId)

const mE1ok = computed(() => mTitulo.value.trim().length >= 3 && mHipotese.value.trim().length >= 10)
const mEstMin = computed(() => Math.round(Math.max(2, mAgentes.value * mRodadas.value * 0.04)))
const mEstCusto = computed(() => (mAgentes.value * mRodadas.value * 0.0008).toFixed(2))
const mDescAg = computed(() => {
  if (mAgentes.value <= 20)  return 'Teste rápido'
  if (mAgentes.value <= 100) return 'Bom equilíbrio entre velocidade e precisão'
  if (mAgentes.value <= 250) return 'Alta fidelidade — captura nuances importantes'
  return 'Máxima riqueza — simulação de alta complexidade'
})
const mDescRd = computed(() => {
  if (mRodadas.value <= 5)  return 'Reação imediata ao evento'
  if (mRodadas.value <= 25) return 'Captura tendências de curto prazo'
  if (mRodadas.value <= 60) return 'Evolução completa ao longo do tempo'
  return 'Análise profunda de longo prazo'
})

// ─── Carregar ─────────────────────────────────────────────────
async function carregar() {
  carregando.value = true
  try {
    const [pr, sr] = await Promise.allSettled([
      service.get(`/api/graph/project/${pid.value}`),
      service.get('/api/simulation/list', { params: { project_id: pid.value } })
    ])
    if (pr.status === 'fulfilled') {
      const raw = pr.value?.data || pr.value
      projeto.value = raw?.data || raw
      verificarGrafo()
    }
    if (sr.status === 'fulfilled') {
      const raw = sr.value?.data || sr.value
      const lista = Array.isArray(raw) ? raw : (raw?.data || raw?.simulations || [])
      simulacoes.value = lista.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    }
  } catch {
    toast.error('Erro ao carregar projeto.')
  } finally {
    carregando.value = false
  }
}

// ─── Verificar grafo REAL no backend ─────────────────────────
async function verificarGrafo() {
  const p = projeto.value
  if (!p) return

  if (p.status === 'graph_completed' && p.graph_id) {
    grafoOk.value = true
    return
  }

  if (p.status === 'failed') {
    grafoErro.value = p.error || 'Falha ao construir o grafo.'
    return
  }

  if (!p.graph_build_task_id) {
    // Nunca foi iniciado — grafo pendente. Não é erro, primeira simulação vai construir.
    grafoOk.value = false
    grafoBuilding.value = false
    return
  }

  // Verificar task real
  grafoBuilding.value = true
  pollTask(p.graph_build_task_id)
}

function pollTask(taskId) {
  let fails = 0
  grafoTimer = setInterval(async () => {
    try {
      const res  = await service.get(`/api/graph/task/${taskId}`)
      const task = res.data || res

      if (!task || task.status === 'not_found') {
        clearInterval(grafoTimer)
        grafoBuilding.value = false
        grafoErro.value     = 'Construção interrompida (servidor foi reiniciado). Crie uma nova simulação para reconstruir.'
        return
      }

      if (task.progress) grafoPct.value = Math.round(task.progress)

      if (task.status === 'completed') {
        clearInterval(grafoTimer)
        grafoBuilding.value = false
        grafoOk.value       = true
        grafoPct.value      = 100
        toast.success('✅ Grafo pronto! Crie uma simulação.')
        const up = await service.get(`/api/graph/project/${pid.value}`)
        projeto.value = up.data?.data || up.data || up
      } else if (task.status === 'failed') {
        clearInterval(grafoTimer)
        grafoBuilding.value = false
        grafoErro.value     = 'Falha ao construir o grafo. Crie uma nova simulação para tentar novamente.'
      }
      fails = 0
    } catch {
      fails++
      if (fails >= 3) {
        clearInterval(grafoTimer)
        grafoBuilding.value = false
        grafoErro.value     = 'Não foi possível verificar o status. Tente criar uma nova simulação.'
      }
    }
  }, 5000)
}

// ─── Modal ────────────────────────────────────────────────────
function abrirModal() {
  mEtapa.value   = 1
  mTitulo.value  = ''
  mCenario.value = ''
  mHipotese.value = ''
  mAgentes.value = 50
  mRodadas.value = 20
  modal.value    = true
}

async function gerarHipotese() {
  if (!mCenario.value.trim()) return
  mGerando.value = true
  try {
    const res = await service.post('/api/graph/generate-hypothesis', { cenario: mCenario.value, segmento: '' })
    const d   = res.data || res
    if (d.hipotese) mHipotese.value = d.hipotese
    toast.success('Hipótese gerada!')
  } catch {
    mHipotese.value = `Como ${mCenario.value.toLowerCase()} vai impactar o mercado nos próximos meses?`
  } finally {
    mGerando.value = false
  }
}

async function criarSimulacao() {
  mCriando.value = true
  try {
    // Se grafo pronto, criar simulação diretamente
    if (grafoOk.value && projeto.value?.graph_id) {
      const res = await service.post('/api/simulation/create', {
        project_id: pid.value,
        graph_id:   projeto.value.graph_id
      })
      const d   = res.data?.data || res.data || res
      const simId = d.simulation_id
      if (!simId) throw new Error('simulation_id não retornado')
      modal.value = false
      toast.success('Simulação criada! Preparando agentes...')
      router.push(`/simulacao/${pid.value}?agentes=${mAgentes.value}&rodadas=${mRodadas.value}&sim_id=${simId}&skip_graph=1`)
    } else {
      // Grafo não existe → reconstruir e criar
      modal.value = false
      toast.info('Construindo grafo e iniciando simulação...')
      router.push(`/simulacao/${pid.value}?agentes=${mAgentes.value}&rodadas=${mRodadas.value}`)
    }
  } catch (e) {
    toast.error(e?.response?.data?.error || 'Erro ao criar simulação.')
  } finally {
    mCriando.value = false
  }
}

// ─── Excluir ─────────────────────────────────────────────────
async function excluir() {
  deletando.value = true
  try {
    await service.delete(`/api/graph/project/${pid.value}`)
    clearInterval(grafoTimer)
    toast.success('Projeto excluído.')
    router.push('/')
  } catch {
    toast.error('Não foi possível excluir.')
    deletando.value = false
  }
}

// ─── Helpers visuais simulação ────────────────────────────────
function statusSim(sim) {
  const s = sim.runner_status || sim.status
  const map = {
    running:   { label: 'Em execução', cls: 's-running',  dot: 'dot-yellow' },
    completed: { label: 'Concluída',   cls: 's-done',     dot: 'dot-green'  },
    stopped:   { label: 'Parada',      cls: 's-paused',   dot: 'dot-gray'   },
    paused:    { label: 'Pausada',     cls: 's-paused',   dot: 'dot-gray'   },
    failed:    { label: 'Erro',        cls: 's-error',    dot: 'dot-red'    },
    ready:     { label: 'Pronta',      cls: 's-ready',    dot: 'dot-purple' },
    preparing: { label: 'Preparando',  cls: 's-ready',    dot: 'dot-purple' },
    created:   { label: 'Criada',      cls: 's-draft',    dot: 'dot-gray'   },
  }
  return map[s] || { label: s || '—', cls: 's-draft', dot: 'dot-gray' }
}

function acaoSim(sim) {
  const s = sim.runner_status || sim.status
  if (s === 'running')  return { label: '▶ Acompanhar ao vivo', cls: 'a-run',    fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  if (sim.report_id)    return { label: '📊 Ver Relatório',     cls: 'a-report', fn: () => router.push(`/relatorio/${sim.report_id}`) }
  if (s === 'completed') return { label: '📊 Ver Resultados',   cls: 'a-report', fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  if (s === 'stopped' || s === 'paused') return { label: '▶ Retomar', cls: 'a-btn', fn: () => router.push(`/simulacao/${sim.simulation_id}/executar`) }
  return { label: 'Ver Pipeline', cls: 'a-btn', fn: () => router.push(`/simulacao/${pid.value}?skip_graph=1`) }
}

function progresso(sim) {
  const pct = sim.progress_percent
  if (pct > 0) return Math.round(pct)
  if (sim.total_rounds && sim.current_round)
    return Math.round((sim.current_round / sim.total_rounds) * 100)
  return 0
}

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(carregar)
onUnmounted(() => { if (grafoTimer) clearInterval(grafoTimer) })
</script>

<template>
  <AppShell :title="projeto?.name || 'Projeto'">
    <template #actions>
      <button class="btn-nova" @click="abrirModal">+ Nova Simulação</button>
    </template>

    <!-- Loading -->
    <div v-if="carregando" class="loading">
      <div class="spinner"></div> Carregando...
    </div>

    <div v-else-if="!projeto" class="empty-full">
      <div>Projeto não encontrado.</div>
      <button class="btn-ghost" @click="router.push('/')">← Início</button>
    </div>

    <div v-else class="page">

      <!-- ─── HEADER ─── -->
      <div class="proj-card">
        <div class="proj-body">
          <div class="proj-nome">{{ projeto.name }}</div>
          <div class="proj-meta">
            <span>📅 {{ fmt(projeto.created_at) }}</span>
            <span class="sep">·</span>
            <span>{{ simulacoes.length }} simulação{{ simulacoes.length !== 1 ? 'ões' : '' }}</span>
            <!-- Status do grafo: discreto, só quando relevante -->
            <span v-if="grafoBuilding" class="grafo-badge grafo-building">
              <span class="mini-spin"></span> Construindo grafo {{ grafoPct > 0 ? grafoPct+'%' : '' }}
            </span>
            <span v-else-if="grafoOk" class="grafo-badge grafo-ok">✅ Grafo pronto</span>
            <span v-else-if="grafoErro" class="grafo-badge grafo-err">⚠️ Problema no grafo</span>
          </div>
          <!-- Aviso de erro do grafo (expansível) -->
          <div v-if="grafoErro" class="grafo-erro-msg">{{ grafoErro }}</div>
          <!-- Barra de progresso do grafo (quando construindo) -->
          <div v-if="grafoBuilding" class="grafo-prog">
            <div class="grafo-prog-fill" :style="{ width: grafoPct+'%' }"></div>
          </div>
        </div>
        <div class="proj-actions">
          <button class="btn-nova-secondary" @click="abrirModal">+ Nova Simulação</button>
          <button class="btn-del" @click="confirmDelete = true" title="Excluir projeto">🗑</button>
        </div>
      </div>

      <!-- Confirmação de exclusão -->
      <Transition name="slide">
        <div v-if="confirmDelete" class="confirm">
          <span>⚠️ Excluir <strong>{{ projeto.name }}</strong> e todas as simulações? Irreversível.</span>
          <div class="confirm-actions">
            <button class="btn-ghost" @click="confirmDelete = false">Cancelar</button>
            <button class="btn-danger" :disabled="deletando" @click="excluir">
              {{ deletando ? 'Excluindo...' : 'Sim, excluir' }}
            </button>
          </div>
        </div>
      </Transition>

      <!-- ─── SIMULAÇÕES ─── -->
      <div class="section-header">
        <h2 class="section-titulo">Simulações</h2>
        <button class="btn-nova-sm" @click="abrirModal">+ Nova</button>
      </div>

      <!-- Vazio -->
      <div v-if="simulacoes.length === 0" class="vazio">
        <div class="vazio-emoji">🚀</div>
        <div class="vazio-titulo">Nenhuma simulação ainda</div>
        <div class="vazio-sub">
          <template v-if="grafoBuilding">
            O grafo está sendo construído. Você já pode criar uma simulação — ela aguardará o grafo ficar pronto.
          </template>
          <template v-else>
            Crie a primeira simulação para começar a prever o mercado.
          </template>
        </div>
        <button class="btn-nova" @click="abrirModal" style="margin-top: 20px">
          ✦ Criar primeira simulação
        </button>
      </div>

      <!-- Lista -->
      <div v-else class="sims">
        <div
          v-for="(sim, idx) in simulacoes"
          :key="sim.simulation_id"
          class="sim"
          :class="statusSim(sim).cls"
        >
          <!-- Linha do topo -->
          <div class="sim-top">
            <div class="sim-top-left">
              <div :class="['dot', statusSim(sim).dot]"></div>
              <span class="sim-idx">#{{ simulacoes.length - idx }}</span>
              <span class="sim-status-label">{{ statusSim(sim).label }}</span>
              <span class="sim-data">{{ fmt(sim.created_at) }}</span>
            </div>
            <div class="sim-top-right">
              <button
                v-if="sim.report_id"
                class="a-sec"
                @click="router.push(`/agentes/${sim.report_id}`)"
                title="Entrevistar agentes"
              >💬</button>
              <button :class="['a-btn', acaoSim(sim).cls]" @click="acaoSim(sim).fn()">
                {{ acaoSim(sim).label }}
              </button>
            </div>
          </div>

          <!-- Hipótese -->
          <div v-if="sim.simulation_requirement" class="sim-hipotese">
            {{ sim.simulation_requirement.length > 120
              ? sim.simulation_requirement.slice(0, 120) + '...'
              : sim.simulation_requirement }}
          </div>

          <!-- Stats -->
          <div class="sim-stats">
            <div class="stat" v-if="sim.entities_count || sim.profiles_count || sim.agent_count">
              <span class="stat-l">Agentes</span>
              <span class="stat-v">{{ sim.entities_count || sim.profiles_count || sim.agent_count }}</span>
            </div>
            <div class="stat" v-if="sim.total_rounds">
              <span class="stat-l">Rodadas</span>
              <span class="stat-v">{{ sim.current_round || 0 }}<span class="stat-of">/ {{ sim.total_rounds }}</span></span>
            </div>
            <div class="stat" v-if="sim.posts_created">
              <span class="stat-l">Posts</span>
              <span class="stat-v">{{ sim.posts_created }}</span>
            </div>
            <div class="stat" v-if="sim.report_id">
              <span class="stat-l">Relatório</span>
              <span class="stat-link" @click="router.push(`/relatorio/${sim.report_id}`)">Ver →</span>
            </div>
          </div>

          <!-- Barra de progresso -->
          <div v-if="sim.total_rounds" class="sim-prog">
            <div class="sim-prog-bar">
              <div
                class="sim-prog-fill"
                :class="{
                  'pf-running': (sim.runner_status||sim.status)==='running',
                  'pf-done':    (sim.runner_status||sim.status)==='completed'
                }"
                :style="{ width: progresso(sim)+'%' }"
              ></div>
            </div>
            <span class="sim-prog-pct">{{ progresso(sim) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════ -->
    <!-- MODAL NOVA SIMULAÇÃO                                       -->
    <!-- ══════════════════════════════════════════════════════════ -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="modal" class="overlay" @click.self="modal = false">
          <div class="modal">

            <div class="modal-head">
              <div>
                <div class="modal-titulo">Nova Simulação</div>
                <div class="modal-sub">{{ projeto?.name }}</div>
              </div>
              <button class="modal-close" @click="modal = false">×</button>
            </div>

            <!-- Steps do modal -->
            <div class="modal-steps">
              <div v-for="(s,i) in ['Hipótese','Parâmetros']" :key="i"
                class="mstep" :class="{ active: mEtapa===i+1, done: mEtapa>i+1 }">
                <div class="mstep-dot">
                  <svg v-if="mEtapa>i+1" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.5" width="10" height="10"><polyline points="2,6 5,9 10,3"/></svg>
                  <span v-else>{{ i+1 }}</span>
                </div>
                <span class="mstep-label">{{ s }}</span>
              </div>
            </div>

            <!-- Etapa 1: Hipótese -->
            <div v-if="mEtapa === 1" class="modal-body">
              <div class="mf">
                <label class="ml">Título da simulação <span class="req">*</span></label>
                <input v-model="mTitulo" class="mi" type="text"
                  placeholder="Ex: Teste preço premium, Cenário 1º turno" autofocus/>
                <span class="mh">Identifica esta simulação dentro do projeto.</span>
              </div>
              <div class="mf">
                <label class="ml">Descreva seu cenário</label>
                <textarea v-model="mCenario" class="mt" rows="2"
                  placeholder="Em linguagem natural — o que quer prever? A IA estrutura para você."/>
                <button class="btn-ia" :disabled="!mCenario.trim() || mGerando" @click="gerarHipotese">
                  <span v-if="mGerando" class="spin-ia"></span>
                  <span v-else>✦</span>
                  {{ mGerando ? 'Gerando...' : 'Gerar hipótese com IA' }}
                </button>
              </div>
              <div class="mf">
                <label class="ml">Hipótese de previsão <span class="req">*</span></label>
                <textarea v-model="mHipotese" class="mt" rows="3"
                  placeholder="Como X vai impactar Y nos próximos Z meses?"/>
                <span class="mh">Guia o comportamento de todos os agentes.</span>
              </div>
            </div>

            <!-- Etapa 2: Parâmetros -->
            <div v-else-if="mEtapa === 2" class="modal-body">
              <div class="mresumo">
                <strong>{{ mTitulo }}</strong>
                <span>{{ mHipotese.slice(0,80) }}{{ mHipotese.length>80?'...':'' }}</span>
              </div>
              <div class="mparam">
                <div class="mparam-h">
                  <span class="mparam-l">Agentes</span>
                  <span class="mparam-v">{{ mAgentes }}</span>
                </div>
                <input type="range" min="5" max="500" step="5" v-model.number="mAgentes" class="slider"/>
                <div class="mparam-bounds"><span>5</span><span>500</span></div>
                <div class="mparam-desc">{{ mDescAg }}</div>
              </div>
              <div class="mparam">
                <div class="mparam-h">
                  <span class="mparam-l">Rodadas</span>
                  <span class="mparam-v">{{ mRodadas }}</span>
                </div>
                <input type="range" min="1" max="100" step="1" v-model.number="mRodadas" class="slider"/>
                <div class="mparam-bounds"><span>1</span><span>100</span></div>
                <div class="mparam-desc">{{ mDescRd }}</div>
              </div>
              <div class="mest">
                <div class="me"><div class="mel">⏱ Tempo</div><div class="mev">~{{ mEstMin }} min</div></div>
                <div class="mes"></div>
                <div class="me"><div class="mel">💳 Custo</div><div class="mev">~${{ mEstCusto }}</div></div>
                <div class="mes"></div>
                <div class="me"><div class="mel">🤖 Agentes</div><div class="mev ac">{{ mAgentes }}</div></div>
                <div class="mes"></div>
                <div class="me"><div class="mel">🔄 Rodadas</div><div class="mev ac2">{{ mRodadas }}</div></div>
              </div>
            </div>

            <div class="modal-foot">
              <button class="btn-ghost" @click="mEtapa===1 ? modal=false : mEtapa--">
                {{ mEtapa===1 ? 'Cancelar' : '← Voltar' }}
              </button>
              <button v-if="mEtapa < 2" class="btn-prox" :disabled="!mE1ok" @click="mEtapa=2">
                Próximo →
              </button>
              <button v-else class="btn-iniciar" :disabled="mCriando" @click="criarSimulacao">
                <span v-if="mCriando" class="spin-sm"></span>
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
/* Layout */
.loading { display:flex; align-items:center; gap:10px; padding:48px; color:var(--text-muted); }
.spinner,.spin-sm { width:18px; height:18px; border:2px solid var(--border-md); border-top-color:var(--accent); border-radius:50%; animation:spin .8s linear infinite; }
.spin-sm { width:13px; height:13px; border-width:2px; border-color:rgba(0,0,0,.2); border-top-color:#000; }
@keyframes spin { to { transform:rotate(360deg) } }
.empty-full { text-align:center; padding:60px 20px; color:var(--text-secondary); display:flex; flex-direction:column; align-items:center; gap:12px; }
.page { display:flex; flex-direction:column; gap:16px; }

/* Projeto card */
.proj-card { background:var(--bg-surface); border:1px solid var(--border); border-radius:14px; padding:20px 24px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.proj-nome { font-size:22px; font-weight:800; color:var(--text-primary); margin-bottom:8px; letter-spacing:-.4px; }
.proj-meta { font-size:12px; color:var(--text-muted); display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sep { opacity:.3; }

/* Grafo badges — discretos no meta */
.grafo-badge { display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:500; padding:2px 8px; border-radius:20px; }
.grafo-building { background:rgba(124,111,247,.1); color:var(--accent2); }
.grafo-ok       { background:rgba(0,229,195,.1);   color:var(--accent); }
.grafo-err      { background:rgba(255,90,90,.1);    color:var(--danger); }
.mini-spin { width:10px; height:10px; border:1.5px solid rgba(124,111,247,.3); border-top-color:var(--accent2); border-radius:50%; animation:spin .8s linear infinite; }
.grafo-prog { height:3px; background:var(--border); border-radius:2px; overflow:hidden; margin-top:8px; }
.grafo-prog-fill { height:100%; background:var(--accent2); border-radius:2px; transition:width .5s; }
.grafo-erro-msg { font-size:12px; color:var(--danger); margin-top:6px; line-height:1.5; }

.proj-actions { display:flex; align-items:center; gap:10px; flex-shrink:0; }
.btn-nova-secondary { background:var(--accent); color:#000; border:none; border-radius:8px; padding:8px 16px; font-size:13px; font-weight:700; cursor:pointer; transition:opacity .15s; white-space:nowrap; }
.btn-nova-secondary:hover { opacity:.85; }
.btn-del { background:none; border:1px solid var(--border); color:var(--text-muted); border-radius:8px; padding:7px 10px; cursor:pointer; font-size:14px; transition:all .15s; }
.btn-del:hover { border-color:var(--danger); color:var(--danger); }

/* Confirm */
.confirm { background:rgba(255,90,90,.06); border:1px solid rgba(255,90,90,.2); border-radius:10px; padding:14px 18px; display:flex; align-items:center; justify-content:space-between; gap:16px; font-size:13px; color:var(--text-secondary); }
.confirm-actions { display:flex; gap:10px; flex-shrink:0; }
.btn-danger { background:var(--danger); color:#fff; border:none; border-radius:6px; padding:7px 16px; font-size:12px; cursor:pointer; font-weight:600; }
.btn-danger:disabled { opacity:.5; }

/* Section */
.section-header { display:flex; align-items:center; justify-content:space-between; }
.section-titulo { font-size:16px; font-weight:700; color:var(--text-primary); margin:0; }
.btn-nova-sm { background:var(--accent2-dim); color:var(--accent2); border:1px solid rgba(124,111,247,.3); border-radius:6px; padding:6px 14px; font-size:12px; font-weight:600; cursor:pointer; transition:all .15s; }
.btn-nova-sm:hover { background:var(--accent2); color:#fff; }

/* Vazio */
.vazio { text-align:center; padding:52px 20px; background:var(--bg-surface); border:1px dashed var(--border-md); border-radius:14px; }
.vazio-emoji { font-size:48px; margin-bottom:14px; }
.vazio-titulo { font-size:18px; font-weight:700; color:var(--text-primary); margin-bottom:8px; }
.vazio-sub { font-size:13px; color:var(--text-secondary); max-width:420px; margin:0 auto; line-height:1.7; }

/* Simulações */
.sims { display:flex; flex-direction:column; gap:12px; }
.sim { background:var(--bg-surface); border:1px solid var(--border); border-radius:12px; padding:16px 20px; transition:border-color .2s; }
.sim:hover { border-color:var(--border-md); }
.s-running { border-color:rgba(245,166,35,.35)!important; }
.s-done    { border-color:rgba(0,229,195,.2)!important; }
.s-error   { border-color:rgba(255,90,90,.2)!important; }

.sim-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; gap:12px; }
.sim-top-left { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sim-top-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }

/* Dots de status */
.dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-green  { background:var(--accent); }
.dot-yellow { background:#f5a623; animation:pulse 1.4s infinite; }
.dot-purple { background:var(--accent2); }
.dot-red    { background:var(--danger); }
.dot-gray   { background:var(--text-muted); opacity:.4; }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:.3} }

.sim-idx { font-size:11px; color:var(--text-muted); font-family:var(--font-mono); }
.sim-status-label { font-size:12px; font-weight:600; color:var(--text-secondary); }
.s-running .sim-status-label { color:#f5a623; }
.s-done    .sim-status-label { color:var(--accent); }
.s-error   .sim-status-label { color:var(--danger); }
.sim-data { font-size:11px; color:var(--text-muted); }

/* Botões de ação das simulações */
.a-btn    { background:none; border:1px solid var(--border-md); color:var(--accent2); border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all .15s; white-space:nowrap; }
.a-btn:hover { background:var(--accent2-dim); }
.a-run    { background:rgba(245,166,35,.1); border:1px solid rgba(245,166,35,.4); color:#f5a623; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all .15s; white-space:nowrap; }
.a-run:hover { background:rgba(245,166,35,.2); }
.a-report { background:rgba(0,229,195,.1); border:1px solid rgba(0,229,195,.3); color:var(--accent); border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; transition:all .15s; white-space:nowrap; }
.a-report:hover { background:rgba(0,229,195,.2); }
.a-sec { background:none; border:1px solid var(--border); color:var(--text-muted); border-radius:6px; padding:5px 8px; font-size:12px; cursor:pointer; transition:all .15s; }
.a-sec:hover { color:var(--text-primary); }

.sim-hipotese { font-size:12px; color:var(--text-muted); line-height:1.6; margin-bottom:10px; padding-left:10px; border-left:2px solid var(--border-md); }

.sim-stats { display:flex; gap:24px; flex-wrap:wrap; margin-bottom:6px; }
.stat { display:flex; flex-direction:column; gap:2px; }
.stat-l { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.5px; }
.stat-v { font-size:15px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono); }
.stat-of { font-size:11px; font-weight:400; color:var(--text-muted); }
.stat-link { font-size:12px; font-weight:600; color:var(--accent2); cursor:pointer; }
.stat-link:hover { text-decoration:underline; }

.sim-prog { display:flex; align-items:center; gap:10px; margin-top:8px; }
.sim-prog-bar { flex:1; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.sim-prog-fill { height:100%; border-radius:2px; background:var(--accent2); transition:width .4s; }
.pf-running { background:#f5a623; animation:shimmer 1.5s infinite; }
.pf-done    { background:var(--accent); }
@keyframes shimmer { 0%,100%{opacity:1}50%{opacity:.5} }
.sim-prog-pct { font-size:11px; color:var(--text-muted); min-width:32px; text-align:right; font-family:var(--font-mono); }

/* Global buttons */
.btn-nova { background:var(--accent); color:#000; border:none; border-radius:8px; padding:8px 18px; font-size:13px; font-weight:700; cursor:pointer; transition:opacity .15s; }
.btn-nova:hover { opacity:.85; }
.btn-ghost { background:transparent; border:none; color:var(--text-secondary); cursor:pointer; font-size:13px; padding:8px 14px; border-radius:8px; transition:color .15s; }
.btn-ghost:hover { color:var(--text-primary); }

/* Transitions */
.slide-enter-active,.slide-leave-active { transition:all .2s ease; }
.slide-enter-from,.slide-leave-to { opacity:0; transform:translateY(-6px); }

/* ─── MODAL ─── */
.overlay { position:fixed; inset:0; background:rgba(0,0,0,.72); display:flex; align-items:center; justify-content:center; z-index:1000; padding:16px; backdrop-filter:blur(4px); }
.modal { background:var(--bg-surface); border:1px solid var(--border-md); border-radius:16px; width:100%; max-width:500px; box-shadow:0 24px 64px rgba(0,0,0,.5); display:flex; flex-direction:column; max-height:90vh; overflow:hidden; }
.modal-head { padding:20px 22px 0; position:relative; flex-shrink:0; }
.modal-titulo { font-size:17px; font-weight:700; color:var(--text-primary); margin-bottom:2px; }
.modal-sub { font-size:12px; color:var(--text-muted); }
.modal-close { position:absolute; top:16px; right:18px; background:none; border:none; color:var(--text-muted); font-size:22px; cursor:pointer; line-height:1; }
.modal-close:hover { color:var(--text-primary); }
.modal-steps { display:flex; align-items:center; gap:8px; padding:14px 22px 0; flex-shrink:0; }
.mstep { display:flex; align-items:center; gap:6px; }
.mstep-dot { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; background:var(--bg-raised); border:2px solid var(--border-md); color:var(--text-muted); transition:all .3s; }
.mstep.active .mstep-dot { background:var(--accent2); border-color:var(--accent2); color:#fff; }
.mstep.done   .mstep-dot { background:var(--accent);  border-color:var(--accent);  color:#000; }
.mstep-label { font-size:12px; color:var(--text-muted); margin-right:8px; }
.mstep.active .mstep-label { color:var(--accent2); font-weight:500; }
.modal-body { padding:16px 22px; display:flex; flex-direction:column; gap:14px; overflow-y:auto; }
.mf { display:flex; flex-direction:column; gap:6px; }
.ml { font-size:13px; font-weight:600; color:var(--text-secondary); }
.req { color:var(--accent); font-weight:400; }
.mh { font-size:11px; color:var(--text-muted); }
.mi { background:var(--bg-raised); border:1px solid var(--border-md); border-radius:8px; color:var(--text-primary); font-size:13px; padding:10px 12px; outline:none; transition:border-color .15s; width:100%; }
.mi:focus { border-color:var(--accent2); }
.mt { background:var(--bg-raised); border:1px solid var(--border-md); border-radius:8px; color:var(--text-primary); font-size:13px; padding:10px 12px; outline:none; resize:vertical; font-family:inherit; line-height:1.6; transition:border-color .15s; }
.mt:focus { border-color:var(--accent2); }
.btn-ia { background:var(--accent2); color:#fff; border:none; border-radius:8px; padding:8px 14px; font-size:12px; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:7px; transition:all .2s; align-self:flex-start; }
.btn-ia:hover:not(:disabled) { opacity:.85; }
.btn-ia:disabled { opacity:.4; cursor:not-allowed; }
.spin-ia { width:12px; height:12px; border:2px solid rgba(255,255,255,.3); border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; }
.mresumo { background:var(--bg-raised); border-radius:8px; padding:10px 14px; border-left:3px solid var(--accent2); display:flex; flex-direction:column; gap:4px; }
.mresumo strong { font-size:13px; color:var(--text-primary); }
.mresumo span { font-size:12px; color:var(--text-muted); }
.mparam { display:flex; flex-direction:column; gap:6px; }
.mparam-h { display:flex; justify-content:space-between; align-items:center; }
.mparam-l { font-size:13px; font-weight:600; color:var(--text-primary); }
.mparam-v { font-size:22px; font-weight:800; color:var(--accent2); font-family:var(--font-mono); }
.mparam-bounds { display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); }
.mparam-desc { font-size:12px; color:var(--text-secondary); background:var(--bg-raised); border-radius:6px; padding:7px 11px; }
.slider { width:100%; accent-color:var(--accent2); cursor:pointer; }
.mest { display:flex; background:var(--bg-raised); border:1px solid var(--border); border-radius:10px; overflow:hidden; }
.me { flex:1; padding:10px 12px; }
.mel { font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:.4px; margin-bottom:3px; }
.mev { font-size:15px; font-weight:700; color:var(--text-primary); font-family:var(--font-mono); }
.mes { width:1px; background:var(--border); margin:8px 0; }
.ac  { color:var(--accent); }
.ac2 { color:var(--accent2); }
.modal-foot { padding:14px 22px; border-top:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
.btn-prox { background:var(--accent2); color:#fff; border:none; border-radius:10px; padding:10px 20px; font-size:14px; font-weight:700; cursor:pointer; transition:all .2s; }
.btn-prox:hover:not(:disabled) { opacity:.85; }
.btn-prox:disabled { opacity:.3; cursor:not-allowed; }
.btn-iniciar { background:var(--accent); color:#000; border:none; border-radius:10px; padding:10px 20px; font-size:14px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:8px; transition:all .2s; }
.btn-iniciar:hover:not(:disabled) { opacity:.85; }
.btn-iniciar:disabled { opacity:.3; cursor:not-allowed; }
.modal-enter-active { transition:all .3s cubic-bezier(.34,1.56,.64,1); }
.modal-leave-active { transition:all .2s ease; }
.modal-enter-from   { opacity:0; transform:scale(.92); }
.modal-leave-to     { opacity:0; transform:scale(.96); }
</style>
