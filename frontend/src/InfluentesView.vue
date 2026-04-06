<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import service from '../api'
import AppShell from '../components/layout/AppShell.vue'
import AugurButton from '../components/ui/AugurButton.vue'

const route  = useRoute()
const router = useRouter()
const simId  = computed(() => route.params.simulationId)

const carregando = ref(true)
const erro       = ref('')
const agents     = ref([])
const maxScore   = ref(1)

const cores = ['#FFD700','#C0C0C0','#CD7F32','#7c6ff7','#00e5c3','#1da1f2','#f5a623','#e91e9c','#4caf50','#ff5a5a']
const medalhas = ['🏆','🥈','🥉']

function iniciais(name) {
  return (name || '??').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

// Calcular score de influência
function score(a) {
  return (a.total_likes_received || 0) * 2 + (a.posts_count || 0) * 1.5 + (a.num_followers || 0) * 0.5
}

onMounted(async () => {
  carregando.value = true
  try {
    const res = await service.get(`/api/analytics/${simId.value}`)
    const data = res?.data?.data || res?.data || {}
    const tw = data?.twitter?.top_agents || []
    const rd = data?.reddit?.top_agents || []
    
    // Merge e deduplicar
    const merged = {}
    ;[...tw, ...rd].forEach(a => {
      const key = a.user_id || a.name
      if (!merged[key]) {
        merged[key] = { ...a, score: score(a) }
      } else {
        merged[key].posts_count = (merged[key].posts_count || 0) + (a.posts_count || 0)
        merged[key].total_likes_received = (merged[key].total_likes_received || 0) + (a.total_likes_received || 0)
        merged[key].score = score(merged[key])
      }
    })
    
    agents.value = Object.values(merged).sort((a, b) => b.score - a.score).slice(0, 10)
    maxScore.value = Math.max(...agents.value.map(a => a.score), 1)
  } catch (e) {
    erro.value = e?.response?.data?.error || e?.message || 'Erro ao carregar dados de influência.'
  } finally {
    carregando.value = false
  }
})

// Simple network SVG for coalition map
const networkSvg = computed(() => {
  if (agents.value.length < 3) return null
  const cx = 200, cy = 180, r = 130
  const nodes = agents.value.slice(0, 8).map((a, i) => {
    const angle = (i / Math.min(agents.value.length, 8)) * 2 * Math.PI - Math.PI / 2
    return {
      x: cx + r * Math.cos(angle) * (0.6 + Math.random() * 0.4),
      y: cy + r * Math.sin(angle) * (0.6 + Math.random() * 0.4),
      name: (a.name || '').split(' ')[0],
      size: 8 + (a.score / maxScore.value) * 16,
      color: cores[i % cores.length]
    }
  })
  // Criar arestas entre agentes próximos (simular coalizões)
  const edges = []
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (Math.random() > 0.55) {
        edges.push({ x1: nodes[i].x, y1: nodes[i].y, x2: nodes[j].x, y2: nodes[j].y })
      }
    }
  }
  return { nodes, edges }
})
</script>

<template>
  <AppShell title="Agentes Influentes">
    <template #actions>
      <AugurButton variant="ghost" @click="router.back()">← Voltar</AugurButton>
    </template>

    <div v-if="carregando" class="state-box">
      <div class="spin"></div>
      <div>Calculando influência dos agentes...</div>
    </div>

    <div v-else-if="erro" class="state-box state-err">
      <div style="font-size:42px">⚠️</div>
      <div>{{ erro }}</div>
    </div>

    <div v-else class="layout">
      <!-- Ranking -->
      <div class="bloco ranking-bloco">
        <div class="bloco-label">📊 TOP {{ agents.length }} AGENTES POR INFLUÊNCIA</div>
        <div class="ranking-list">
          <div v-for="(a, i) in agents" :key="a.user_id || i" class="rank-row" :class="{'rank-top': i < 3}">
            <div class="rank-pos">
              <span v-if="i < 3" class="rank-medal">{{ medalhas[i] }}</span>
              <span v-else class="rank-num">#{{ i + 1 }}</span>
            </div>
            <div class="rank-avatar" :style="{background: cores[i]}">{{ iniciais(a.name) }}</div>
            <div class="rank-info">
              <div class="rank-name">{{ a.name || a.user_name }}</div>
              <div class="rank-role">{{ a.bio?.slice(0, 50) || 'Agente simulado' }}</div>
            </div>
            <div class="rank-stats">
              <span>{{ a.posts_count || 0 }} int.</span>
            </div>
            <div class="rank-bar-wrap">
              <div class="rank-bar" :style="{width: (a.score / maxScore * 100) + '%', background: cores[i]}"></div>
              <span class="rank-score">{{ a.score.toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Coalition Map -->
      <div class="bloco network-bloco">
        <div class="bloco-label">🕸 MAPA DE COALIZÕES</div>
        <svg v-if="networkSvg" viewBox="0 0 400 360" class="network-svg">
          <!-- Edges -->
          <line v-for="(e, i) in networkSvg.edges" :key="'e'+i"
            :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2"
            stroke="rgba(124,111,247,0.15)" stroke-width="1.5"/>
          <!-- Nodes -->
          <g v-for="(n, i) in networkSvg.nodes" :key="'n'+i">
            <circle :cx="n.x" :cy="n.y" :r="n.size" :fill="n.color" opacity="0.85"/>
            <text :x="n.x" :y="n.y + n.size + 14" text-anchor="middle"
              fill="var(--text-muted)" font-size="10" font-weight="600">{{ n.name }}</text>
          </g>
        </svg>
        <div v-else class="no-data">Dados insuficientes para gerar o mapa</div>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.state-box { display:flex;flex-direction:column;align-items:center;gap:14px;padding:60px;text-align:center;color:var(--text-muted); }
.state-err { color:var(--danger); }
.spin { width:24px;height:24px;border:3px solid var(--border-md);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite; }
@keyframes sp { to { transform:rotate(360deg) } }

.layout { display:grid;grid-template-columns:1fr 1fr;gap:16px; }
.bloco { background:var(--bg-surface);border:1px solid var(--border);border-radius:14px;padding:22px 24px; }
.bloco-label { font-size:11px;font-weight:700;color:var(--text-muted);letter-spacing:1.2px;text-transform:uppercase;margin-bottom:16px; }

/* Ranking */
.ranking-list { display:flex;flex-direction:column;gap:6px; }
.rank-row { display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:10px;transition:background .15s; }
.rank-row:hover { background:var(--bg-raised); }
.rank-top { background:rgba(124,111,247,0.04); }
.rank-pos { width:30px;text-align:center;flex-shrink:0; }
.rank-medal { font-size:18px; }
.rank-num { font-size:12px;color:var(--text-muted);font-weight:700; }
.rank-avatar { width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;color:#fff;flex-shrink:0; }
.rank-info { flex:1;min-width:0; }
.rank-name { font-size:13px;font-weight:700;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
.rank-role { font-size:10px;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
.rank-stats { font-size:11px;color:var(--text-muted);white-space:nowrap; }
.rank-bar-wrap { width:120px;display:flex;align-items:center;gap:6px;flex-shrink:0; }
.rank-bar { height:6px;border-radius:3px;transition:width .6s ease; }
.rank-score { font-size:11px;font-weight:700;color:var(--accent);font-family:monospace; }

/* Network */
.network-bloco { display:flex;flex-direction:column; }
.network-svg { width:100%;height:auto;flex:1; }
.no-data { text-align:center;color:var(--text-muted);padding:40px;font-size:13px; }

@media (max-width:1080px) { .layout { grid-template-columns:1fr; } }
</style>
