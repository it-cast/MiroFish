<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import service from '../api'
import AppShell from '../components/layout/AppShell.vue'
import MetricCard from '../components/ui/MetricCard.vue'
import SentimentBar from '../components/ui/SentimentBar.vue'
import AugurButton from '../components/ui/AugurButton.vue'

const router = useRouter()
const projetos = ref([])
const carregando = ref(true)
const expandidos = ref({})

// ─── Carregar dados ───────────────────────────────────────────
async function carregarDados() {
  carregando.value = true
  try {
    const [projRes, simRes] = await Promise.allSettled([
      service.get('/api/graph/project/list'),
      service.get('/api/simulation/history', { params: { limit: 50 } })
    ])

    const projetosRaw = projRes.status === 'fulfilled'
      ? (projRes.value?.data || projRes.value || [])
      : []

    const simsRaw = simRes.status === 'fulfilled'
      ? (simRes.value?.data || simRes.value || [])
      : []

    const listaProj = Array.isArray(projetosRaw) ? projetosRaw
      : (projetosRaw.data || projetosRaw.projects || projetosRaw.items || [])

    const listaSims = Array.isArray(simsRaw) ? simsRaw
      : (simsRaw.data || simsRaw.history || simsRaw.simulations || simsRaw.items || [])

    projetos.value = listaProj
      .map(p => ({
        ...p,
        simulacoes: listaSims.filter(s =>
          s.project_id === p.project_id || s.project_id === p.id
        )
      }))
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))

    // Expandir o primeiro projeto por padrão
    if (projetos.value.length > 0) {
      expandidos.value[projetos.value[0].project_id || projetos.value[0].id] = true
    }
  } catch (e) {
    console.error('Erro ao carregar dashboard:', e)
  } finally {
    carregando.value = false
  }
}

// ─── Métricas ─────────────────────────────────────────────────
const metrics = computed(() => {
  const todasSims = projetos.value.flatMap(p => p.simulacoes || [])
  return {
    projetos: projetos.value.length,
    simulacoes: todasSims.length,
    agentes: todasSims.reduce((acc, s) => acc + (s.entities_count || s.agent_count || 0), 0),
    relatorios: todasSims.filter(s => s.report_id).length
  }
})

// ─── Helpers ─────────────────────────────────────────────────
function toggleExpandir(id) {
  expandidos.value[id] = !expandidos.value[id]
}

function abrirSimulacao(sim) {
  const status = sim.runner_status || sim.status
  if (status === 'running') return router.push(`/simulacao/${sim.simulation_id}/executar`)
  if (sim.report_id) return router.push(`/relatorio/${sim.report_id}`)
  return router.push(`/simulacao/${sim.project_id}`)
}

function novaSimulacao() {
  router.push('/novo')
}

function statusBadge(sim) {
  const status = sim.runner_status || sim.status
  if (status === 'running') return { label: 'Em execução', cls: 'badge-running' }
  if (status === 'completed') return { label: 'Concluído', cls: 'badge-done' }
  if (status === 'failed') return { label: 'Erro', cls: 'badge-error' }
  if (status === 'preparing' || status === 'ready') return { label: 'Preparando', cls: 'badge-preparing' }
  return { label: 'Rascunho', cls: 'badge-draft' }
}

function projetoStatusBadge(projeto) {
  if (projeto.simulacoes?.some(s => (s.runner_status || s.status) === 'running')) {
    return { label: 'Ativo', cls: 'badge-running' }
  }
  if (projeto.status === 'graph_completed') return { label: 'Pronto', cls: 'badge-done' }
  if (projeto.status === 'graph_building') return { label: 'Construindo', cls: 'badge-preparing' }
  return { label: projeto.status || 'Criado', cls: 'badge-draft' }
}

function formatarData(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function truncar(txt, n = 80) {
  if (!txt) return '—'
  return txt.length > n ? txt.slice(0, n) + '...' : txt
}

onMounted(carregarDados)
</script>

<template>
  <AppShell title="Dashboard">
    <template #actions>
      <button class="btn-nova" @click="novaSimulacao">+ Nova Simulação</button>
    </template>

    <!-- Métricas -->
    <section class="grid-metrics">
      <MetricCard title="Projetos" :value="metrics.projetos" sub="Ideias em simulação" trend="up" />
      <MetricCard title="Simulações" :value="metrics.simulacoes" sub="Total executadas" trend="up" />
      <MetricCard title="Agentes Totais" :value="metrics.agentes" sub="Base ativa" trend="up" />
      <MetricCard title="Relatórios" :value="metrics.relatorios" sub="Concluídos" />
    </section>

    <!-- Carregando -->
    <div v-if="carregando" class="loading-state">
      <div class="spinner"></div>
      <span>Carregando projetos...</span>
    </div>

    <!-- Estado vazio -->
    <div v-else-if="projetos.length === 0" class="empty-state">
      <div class="empty-icon">🔭</div>
      <div class="empty-title">Nenhum projeto ainda</div>
      <div class="empty-sub">Crie sua primeira simulação para começar a prever o futuro do seu negócio.</div>
      <button class="btn-nova" @click="novaSimulacao" style="margin-top:16px;">+ Criar primeira simulação</button>
    </div>

    <!-- Lista de projetos -->
    <div v-else class="projetos-lista">
      <div
        v-for="projeto in projetos"
        :key="projeto.project_id || projeto.id"
        class="projeto-card"
        :class="{ 'projeto-ativo': projeto.simulacoes?.some(s => (s.runner_status || s.status) === 'running') }"
      >
        <!-- Header do projeto -->
        <div class="projeto-header" @click="toggleExpandir(projeto.project_id || projeto.id)">
          <div class="projeto-info">
            <div class="projeto-nome">{{ projeto.name || 'Projeto sem nome' }}</div>
            <div class="projeto-meta">
              <span>{{ formatarData(projeto.created_at) }}</span>
              <span class="meta-sep">·</span>
              <span>{{ (projeto.files || []).length }} arquivo{{ (projeto.files || []).length !== 1 ? 's' : '' }}</span>
              <span class="meta-sep">·</span>
              <span>{{ projeto.simulacoes?.length || 0 }} simulação{{ (projeto.simulacoes?.length || 0) !== 1 ? 'ões' : '' }}</span>
            </div>
          </div>
          <div class="projeto-actions">
            <span :class="['badge', projetoStatusBadge(projeto).cls]">
              {{ projetoStatusBadge(projeto).label }}
            </span>
            <button class="btn-sim-nova" @click.stop="novaSimulacao" title="Nova simulação neste projeto">
              + Simular
            </button>
            <span class="chevron" :class="{ aberto: expandidos[projeto.project_id || projeto.id] }">›</span>
          </div>
        </div>

        <!-- Simulações do projeto -->
        <div v-if="expandidos[projeto.project_id || projeto.id]" class="simulacoes-lista">

          <!-- Sem simulações -->
          <div v-if="!projeto.simulacoes?.length" class="sim-vazia">
            <span>Nenhuma simulação ainda para este projeto.</span>
            <button class="btn-link" @click="novaSimulacao">Criar simulação →</button>
          </div>

          <!-- Lista de simulações -->
          <div
            v-for="sim in projeto.simulacoes"
            :key="sim.simulation_id"
            class="sim-item"
            @click="abrirSimulacao(sim)"
          >
            <div class="sim-hipotese">{{ truncar(sim.simulation_requirement || sim.hypothesis || '—') }}</div>
            <div class="sim-meta">
              <span>{{ formatarData(sim.created_at) }}</span>
              <span class="meta-sep">·</span>
              <span>{{ sim.entities_count || sim.agent_count || 0 }} agentes</span>
              <span v-if="sim.current_round || sim.total_rounds" class="meta-sep">·</span>
              <span v-if="sim.current_round || sim.total_rounds">
                Rodada {{ sim.current_round || 0 }}/{{ sim.total_rounds || 0 }}
              </span>
            </div>
            <div class="sim-footer">
              <span :class="['badge', statusBadge(sim).cls]">{{ statusBadge(sim).label }}</span>
              <div class="sim-links">
                <span v-if="sim.report_id" class="link-btn" @click.stop="router.push(`/relatorio/${sim.report_id}`)">Ver relatório →</span>
                <span v-else-if="(sim.runner_status || sim.status) === 'running'" class="link-btn" @click.stop="router.push(`/simulacao/${sim.simulation_id}/executar`)">Acompanhar →</span>
                <span v-else class="link-btn" @click.stop="abrirSimulacao(sim)">Abrir →</span>
              </div>
            </div>

            <!-- Barra de progresso se em execução -->
            <div v-if="(sim.runner_status || sim.status) === 'running' && sim.total_rounds" class="sim-progress">
              <div class="sim-progress-fill" :style="{ width: Math.round(((sim.current_round || 0) / sim.total_rounds) * 100) + '%' }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Sentimento (decorativo por enquanto) -->
    <div style="margin-top: 24px;">
      <SentimentBar label="Sentimento médio — última semana" :positive="58" :neutral="27" :negative="15" />
    </div>
  </AppShell>
</template>

<style scoped>
.grid-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 24px; }

.btn-nova {
  background: var(--accent); color: #000; border: none; border-radius: 8px;
  padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s;
}
.btn-nova:hover { opacity: 0.85; }

/* Loading */
.loading-state { display: flex; align-items: center; gap: 12px; padding: 40px; color: var(--text-muted); }
.spinner { width: 20px; height: 20px; border: 2px solid var(--border-md); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-title { font-size: 18px; font-weight: 500; color: var(--text-primary); margin-bottom: 8px; }
.empty-sub { font-size: 14px; color: var(--text-secondary); max-width: 400px; margin: 0 auto; }

/* Projetos */
.projetos-lista { display: flex; flex-direction: column; gap: 12px; }

.projeto-card {
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden; transition: border-color 0.2s;
}
.projeto-card.projeto-ativo { border-color: rgba(0,229,195,0.3); }

.projeto-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; cursor: pointer; transition: background 0.15s;
}
.projeto-header:hover { background: var(--bg-raised); }

.projeto-nome { font-size: 15px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; }
.projeto-meta { font-size: 12px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
.meta-sep { opacity: 0.4; }

.projeto-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.btn-sim-nova {
  background: var(--accent2-dim); color: var(--accent2); border: 1px solid rgba(124,111,247,0.3);
  border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer; transition: all 0.15s;
}
.btn-sim-nova:hover { background: var(--accent2); color: #fff; }

.chevron { font-size: 18px; color: var(--text-muted); transition: transform 0.2s; display: inline-block; }
.chevron.aberto { transform: rotate(90deg); }

/* Badges */
.badge { padding: 3px 8px; border-radius: 20px; font-size: 11px; font-weight: 500; }
.badge-done { background: rgba(0,229,195,0.1); color: var(--accent); }
.badge-running { background: rgba(245,166,35,0.1); color: #f5a623; }
.badge-error { background: rgba(255,90,90,0.1); color: var(--danger); }
.badge-preparing { background: rgba(124,111,247,0.1); color: var(--accent2); }
.badge-draft { background: rgba(107,107,128,0.15); color: var(--text-muted); }

/* Simulações */
.simulacoes-lista { border-top: 1px solid var(--border); }

.sim-vazia {
  padding: 16px 20px; display: flex; align-items: center; gap: 12px;
  font-size: 13px; color: var(--text-muted);
}
.btn-link { background: none; border: none; color: var(--accent2); cursor: pointer; font-size: 13px; }
.btn-link:hover { text-decoration: underline; }

.sim-item {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  cursor: pointer; transition: background 0.15s;
}
.sim-item:last-child { border-bottom: none; }
.sim-item:hover { background: var(--bg-raised); }

.sim-hipotese { font-size: 13px; color: var(--text-primary); margin-bottom: 4px; line-height: 1.5; }
.sim-meta { font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }

.sim-footer { display: flex; align-items: center; justify-content: space-between; }
.sim-links { display: flex; gap: 10px; }
.link-btn { font-size: 12px; color: var(--accent2); cursor: pointer; }
.link-btn:hover { text-decoration: underline; }

.sim-progress { height: 3px; background: var(--border); border-radius: 2px; margin-top: 8px; overflow: hidden; }
.sim-progress-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.3s; }

@media (max-width: 1080px) {
  .grid-metrics { grid-template-columns: repeat(2, 1fr); }
}
</style>
