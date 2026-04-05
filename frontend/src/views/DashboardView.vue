<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import service from '../api'
import AppShell from '../components/layout/AppShell.vue'
import AugurButton from '../components/ui/AugurButton.vue'

const props = defineProps({ projectId: { type: String, default: '' } })
const router = useRouter()

const loading = ref(false)
const projects = ref([])
const simulations = ref([])

const normalizeStatus = (status = '') => {
  const value = String(status).toLowerCase()
  if (value.includes('complete') || value.includes('conclu')) return 'completed'
  if (value.includes('running') || value.includes('exec')) return 'running'
  if (value.includes('prepar') || value.includes('build') || value.includes('generat')) return 'preparing'
  if (value.includes('fail') || value.includes('erro')) return 'failed'
  return 'draft'
}

const statusLabel = (status) => ({
  completed: 'Concluído',
  running: 'Em execução',
  preparing: 'Preparando',
  failed: 'Erro',
  draft: 'Sem simulações'
}[normalizeStatus(status)] || 'Sem simulações')

const projectsGrouped = computed(() => {
  const sortedProjects = [...projects.value]
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
    .filter((project) => !props.projectId || String(project.project_id) === String(props.projectId))

  return sortedProjects.map((project) => {
    const items = simulations.value
      .filter((sim) => String(sim.project_id) === String(project.project_id))
      .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())

    return {
      ...project,
      simulations: items,
      hasRunning: items.some((sim) => normalizeStatus(sim.status || sim.runner_status) === 'running')
    }
  })
})

const fetchData = async () => {
  loading.value = true
  try {
    const [projectRes, simRes] = await Promise.all([
      service.get('/api/graph/project/list'),
      service.get('/api/simulation/history', { params: { limit: 20 } })
    ])

    const p = projectRes.data || projectRes
    const s = simRes.data || simRes

    projects.value = p.data || p.projects || []
    simulations.value = s.data || s.history || s.items || []
  } finally {
    loading.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return 'Data não informada'
  return new Date(dateStr).toLocaleString('pt-BR')
}

const simulationStatus = (sim) => normalizeStatus(sim.status || sim.runner_status)

const trunc = (text, max = 96) => {
  if (!text) return 'Hipótese não informada'
  return text.length > max ? `${text.slice(0, max)}...` : text
}

const openSimulation = (sim) => {
  const status = simulationStatus(sim)
  if (status === 'completed' && sim.report_id) {
    return router.push(`/relatorio/${sim.report_id}`)
  }
  if (status === 'running') {
    return router.push(`/simulacao/${sim.simulation_id || sim.id}/executar`)
  }
  return router.push(`/simulacao/${sim.project_id}`)
}

onMounted(fetchData)
</script>

<template>
  <AppShell title="Dashboard">
    <template #actions>
      <AugurButton variant="ghost" @click="router.push('/novo')">Nova Simulação</AugurButton>
    </template>

    <section v-if="loading" class="empty">Carregando projetos...</section>

    <section v-else-if="!projectsGrouped.length" class="empty">
      <h3>Nenhum projeto ainda</h3>
      <p>Crie sua primeira simulação para começar.</p>
      <AugurButton @click="router.push('/novo')">Nova Simulação</AugurButton>
    </section>

    <section v-else class="project-list">
      <article
        v-for="project in projectsGrouped"
        :key="project.project_id"
        class="project-card"
        :class="{ running: project.hasRunning }"
      >
        <header>
          <div>
            <h3>{{ project.name || `Projeto ${project.project_id}` }}</h3>
            <small>{{ formatDate(project.created_at) }}</small>
          </div>
          <span class="badge" :class="project.hasRunning ? 'running' : project.simulations.length ? simulationStatus(project.simulations[0]) : 'draft'">
            {{ project.simulations.length ? statusLabel(project.simulations[0].status || project.simulations[0].runner_status) : 'Sem simulações' }}
          </span>
        </header>

        <p class="meta">{{ project.simulations.length }} simulação(ões)</p>

        <div v-if="project.simulations.length" class="sim-list">
          <button
            v-for="sim in project.simulations"
            :key="sim.simulation_id"
            class="sim-item"
            @click="openSimulation(sim)"
          >
            <div class="row">
              <strong>{{ trunc(sim.hypothesis || sim.objective || sim.name) }}</strong>
              <span class="badge" :class="simulationStatus(sim)">{{ statusLabel(sim.status || sim.runner_status) }}</span>
            </div>
            <small>
              {{ sim.entities_count || sim.agent_count || 0 }} agentes ·
              {{ sim.total_rounds || sim.rounds || 0 }} rodadas ·
              {{ formatDate(sim.created_at) }}
            </small>
            <small v-if="sim.report_id" class="link">Relatório disponível</small>
          </button>
        </div>

        <p v-else class="empty-inline">Sem simulações</p>
      </article>
    </section>
  </AppShell>
</template>

<style scoped>
.project-list { display: grid; gap: 12px; }
.project-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--r-md); padding: 14px; display: grid; gap: 10px; }
.project-card.running { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-dim) inset; }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
h3 { margin: 0; }
small { color: var(--text-muted); }
.meta { margin: 0; color: var(--text-secondary); }
.sim-list { display: grid; gap: 8px; }
.sim-item { width: 100%; text-align: left; background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--r-sm); padding: 10px; cursor: pointer; color: var(--text-primary); }
.sim-item:hover { border-color: var(--border-hi); }
.row { display: flex; justify-content: space-between; gap: 10px; }
.badge { padding: 3px 8px; border-radius: 999px; font-size: 12px; color: var(--text-primary); background: var(--bg-overlay); }
.badge.completed { color: #05231f; background: var(--accent); }
.badge.running { color: #1f1405; background: var(--warn); }
.badge.preparing { color: #f0edff; background: var(--accent2); }
.badge.failed { color: #fff; background: var(--danger); }
.badge.draft { color: var(--text-secondary); background: var(--bg-overlay); }
.link { color: var(--accent); }
.empty { background: var(--bg-surface); border: 1px dashed var(--border-md); border-radius: var(--r-md); padding: 24px; display: grid; gap: 8px; justify-items: start; }
.empty-inline { color: var(--text-muted); margin: 0; }
</style>
