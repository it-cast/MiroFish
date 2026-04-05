<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import AugurButton from '../components/ui/AugurButton.vue'
import service from '../api'

const route = useRoute()
const router = useRouter()
const data = ref(null)
const statusMsg = ref('Iniciando...')

function traduzirMensagem(msg) {
  if (!msg) return msg
  const map = {
    Iniciando: 'Iniciando...',
    Starting: 'Iniciando...',
    building: 'Construindo grafo de conhecimento no Zep...',
    graph: 'Processando grafo de conhecimento...',
    entity: 'Extraindo entidades e relacionamentos...',
    chunk: 'Processando chunks do documento...',
    completed: 'Concluído!',
    failed: 'Falhou',
    preparing: 'Preparando agentes...',
    generating: 'Gerando perfis dos agentes com IA...',
    profile: 'Criando perfil do agente...',
    simulation: 'Configurando simulação...',
    ready: 'Pronto para iniciar!'
  }
  for (const [key, val] of Object.entries(map)) {
    if (msg.toLowerCase().includes(key.toLowerCase())) return val
  }
  if (/[\u4e00-\u9fff]/.test(msg)) return 'Processando...'
  return msg
}

onMounted(async () => {
  const response = await service.get('/api/simulation/history', { params: { limit: 20 } })
  const raw = response.data || response
  data.value = (raw.history || raw.items || raw.data || []).find((item) => String(item.project_id || item.id) === String(route.params.projectId))
  statusMsg.value = traduzirMensagem(data.value?.message || data.value?.status || 'ready')
})
</script>
<template>
  <AppShell title="Detalhes da Simulação">
    <section class="panel">
      <h3>{{ data?.name || 'Projeto AUGUR' }}</h3>
      <p>{{ statusMsg }}</p>
      <ul>
        <li>Agentes: {{ data?.agent_count || data?.entities_count || '-' }}</li>
        <li>Rodadas: {{ data?.max_rounds || data?.rounds || '-' }}</li>
        <li>Status: {{ data?.status || 'rascunho' }}</li>
      </ul>
      <AugurButton @click="router.push(`/simulacao/${data?.simulation_id || data?.id || route.params.projectId}/executar`)">Executar Simulação</AugurButton>
    </section>
  </AppShell>
</template>
<style scoped>
.panel { background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--r-md); padding: 18px; display: grid; gap: 10px; }
p { color: var(--text-secondary); margin: 0; }
</style>
