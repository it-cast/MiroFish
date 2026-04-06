<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import AugurButton from '../components/ui/AugurButton.vue'
import service from '../api'

const route  = useRoute()
const router = useRouter()
const report     = ref(null)
const analytics  = ref(null)
const carregando = ref(true)
const erro       = ref('')
const abaAtiva   = ref('relatorio')

onMounted(async () => {
  carregando.value = true
  try {
    const rRes = await service.get(`/api/report/${route.params.reportId}`).catch(e => ({ error: e }))
    if (rRes.error) throw rRes.error
    const raw = rRes?.data?.data || rRes?.data || rRes
    report.value = raw
    if (raw?.simulation_id) {
      try {
        const aRes = await service.get(`/api/analytics/${raw.simulation_id}`)
        analytics.value = aRes?.data?.data || aRes?.data || null
      } catch { /* opcional */ }
    }
  } catch (e) {
    erro.value = e?.response?.data?.error || e?.message || 'Erro ao carregar relatório.'
  } finally {
    carregando.value = false
  }
})

const titulo   = computed(() => report.value?.outline?.title   || 'Relatório de Previsão')
const resumo   = computed(() => report.value?.outline?.summary || '')
const secoes   = computed(() => report.value?.outline?.sections || [])
const simReq   = computed(() => report.value?.simulation_requirement || '')
const geradoEm = computed(() => {
  const d = report.value?.completed_at || report.value?.created_at
  if (!d) return ''
  return new Date(d).toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
})

const totalInteracoes = computed(() => analytics.value?.combined?.total_interactions || 0)
const totalRodadas    = computed(() => analytics.value?.combined?.total_rounds || 0)
const twPosts  = computed(() => analytics.value?.twitter?.totals?.posts || 0)
const rdPosts  = computed(() => analytics.value?.reddit?.totals?.posts  || 0)
const combinedRounds = computed(() => analytics.value?.combined?.rounds || [])
const twTopPosts = computed(() => (analytics.value?.twitter?.top_posts || []).slice(0,5))
const rdTopPosts = computed(() => (analytics.value?.reddit?.top_posts  || []).slice(0,5))
const twEngagement = computed(() => analytics.value?.twitter?.engagement || [])

const indiceConfianca = computed(() => {
  const text = resumo.value + ' ' + (secoes.value[0]?.content || '')
  const m = text.match(/(\d{2,3})\s*%/)
  return m ? Math.min(parseInt(m[1]), 99) : 72
})

function tipoSecao(s, idx) {
  const t = (s.title || '').toLowerCase()
  if (idx === 0 || t.includes('resumo')   || t.includes('executivo'))  return 'resumo'
  if (idx === 1 || t.includes('cenário')  || t.includes('futuro'))     return 'cenarios'
  if (idx === 2 || t.includes('risco')    || t.includes('fator'))      return 'riscos'
  if (idx === 3 || t.includes('força')    || t.includes('mapa'))       return 'forcas'
  if (idx === 4 || t.includes('cronolog') || t.includes('rodada'))     return 'cronologia'
  if (idx === 5 || t.includes('padrão')   || t.includes('emergente'))  return 'padroes'
  if (idx === 6 || t.includes('hipótese') || t.includes('causal'))     return 'hipoteses'
  if (idx === 7 || t.includes('recomend') || t.includes('estratég'))   return 'recomendacoes'
  if (idx === 8 || t.includes('previsão') || t.includes('previsao'))   return 'previsoes'
  return 'geral'
}

// Gauge arc path
function gaugePath(pct, r = 44) {
  const angle = Math.PI * pct / 100
  const sx = 60 - r * Math.cos(Math.PI)
  const sy = 58 - r * Math.sin(Math.PI) * -1
  const ex = 60 - r * Math.cos(Math.PI - angle)
  const ey = 58 - r * Math.sin(Math.PI - angle) * -1
  return `M ${sx} ${sy} A ${r} ${r} 0 ${pct > 50 ? 1 : 0} 1 ${ex} ${ey}`
}

// Chart
const chartW = 500; const chartH = 150
const cP = { t: 14, r: 14, b: 26, l: 32 }
const chartPoints = computed(() => {
  const rounds = combinedRounds.value
  if (rounds.length < 2) return null
  const maxVal = Math.max(...rounds.map(r => r.total), 1)
  const w = chartW - cP.l - cP.r
  const h = chartH - cP.t - cP.b
  const x = i => cP.l + (i / Math.max(rounds.length - 1, 1)) * w
  const y = v => cP.t + h - (v / maxVal) * h
  const path = fn => rounds.map((r,i) => `${i===0?'M':'L'}${x(i).toFixed(1)},${y(fn(r)).toFixed(1)}`).join(' ')
  const n = rounds.length
  const labels = rounds.filter((_,i) => i % Math.max(Math.floor(n/7),1) === 0)
    .map(r => ({ r: r.round, x: x(rounds.indexOf(r)) }))
  return {
    tw: path(r => r.twitter), rd: path(r => r.reddit), total: path(r => r.total),
    area: `${path(r=>r.total)} L${x(n-1).toFixed(1)},${(cP.t+h).toFixed(1)} L${cP.l},${(cP.t+h).toFixed(1)} Z`,
    labels, maxVal,
    yLines: [0,.33,.66,1].map(f => ({ val: Math.round(maxVal*f), y: y(maxVal*f) }))
  }
})

function md(text) {
  if (!text) return ''
  return text
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm,  '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,   '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,    '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,    '<em>$1</em>')
    .replace(/^> (.+)$/gm,    '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm,    '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>\n?)+/g, s => `<ul>${s}</ul>`)
    .replace(/^\d+\. (.+)$/gm,'<li>$1</li>')
    .replace(/\n\n/g,         '</p><p>')
    .replace(/^(?!<)(.+)$/gm, m => `<p>${m}</p>`)
}

function truncar(t, n=180) { return !t ? '' : t.length > n ? t.slice(0,n)+'...' : t }
function corBar(idx) { return ['#00e5c3','#7c6ff7','#f5a623','#ff5a5a','#1da1f2'][idx%5] }

function exportarPDF() { window.print() }

async function voltar() {
  let pid = report.value?.project_id
  if (!pid && report.value?.simulation_id) {
    try {
      const res = await service.get('/api/simulation/list', { params: { limit: 200 } })
      const lista = res?.data?.data || res?.data || []
      pid = lista.find(s => s.simulation_id === report.value.simulation_id)?.project_id
    } catch { /* ignorar */ }
  }
  router.push(pid ? `/projeto/${pid}` : '/')
}
</script>

<template>
  <AppShell :title="titulo">
    <template #actions>
      <AugurButton variant="ghost" @click="voltar" class="no-print">← Projeto</AugurButton>
      <AugurButton @click="exportarPDF" class="no-print">⬇ Exportar PDF</AugurButton>
    </template>

    <div v-if="carregando" class="loading no-print">
      <div class="spin"></div>
      <div>
        <div class="ld-t">Carregando relatório...</div>
        <div class="ld-s">Processando análises da simulação</div>
      </div>
    </div>

    <div v-else-if="erro" class="erro-state no-print">
      <div style="font-size:48px">⚠️</div>
      <div style="color:var(--danger);font-size:14px">{{ erro }}</div>
      <button class="btn-ghost" @click="voltar">← Voltar</button>
    </div>

    <div v-else-if="report" class="rw">

      <!-- ══════════════════════════════════════════ -->
      <!-- CAPA                                       -->
      <!-- ══════════════════════════════════════════ -->
      <div class="capa pb-after">
        <div class="capa-top">
          <div class="capa-brand">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" class="capa-logo">
              <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#00e5c3"/><stop offset="100%" stop-color="#7c6ff7"/>
              </linearGradient></defs>
              <rect width="32" height="32" rx="8" fill="url(#lg)"/>
              <circle cx="8"  cy="16" r="2.5" fill="white" opacity="0.9"/>
              <circle cx="16" cy="8"  r="2.5" fill="white" opacity="0.9"/>
              <circle cx="24" cy="16" r="2.5" fill="white" opacity="0.9"/>
              <circle cx="16" cy="24" r="2.5" fill="white" opacity="0.9"/>
              <line x1="8" y1="16" x2="16" y2="8"  stroke="white" stroke-width="1.5" opacity="0.6"/>
              <line x1="16" y1="8" x2="24" y2="16"  stroke="white" stroke-width="1.5" opacity="0.6"/>
              <line x1="24" y1="16" x2="16" y2="24" stroke="white" stroke-width="1.5" opacity="0.6"/>
              <line x1="16" y1="24" x2="8" y2="16"  stroke="white" stroke-width="1.5" opacity="0.6"/>
            </svg>
            <div>
              <div class="brand-n">AUGUR</div>
              <div class="brand-s">Motor de Previsão com IA · by itcast</div>
            </div>
          </div>
          <div class="capa-badge">RELATÓRIO DE PREVISÃO</div>
        </div>

        <div class="capa-divider">
          <div class="div-line"></div>
          <div class="div-gem"></div>
          <div class="div-line"></div>
        </div>

        <div class="capa-mid">
          <h1 class="capa-titulo">{{ titulo }}</h1>
          <div v-if="simReq" class="capa-hip">
            <div class="hip-lbl">Hipótese testada</div>
            <div class="hip-txt">{{ simReq }}</div>
          </div>
          <div v-if="resumo" class="capa-resumo">{{ resumo }}</div>
        </div>

        <!-- Métricas com gauge -->
        <div class="capa-stats">
          <div class="cs-item">
            <svg :viewBox="`0 0 120 70`" class="gauge-svg">
              <defs><linearGradient id="gg" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#ff5a5a"/>
                <stop offset="50%" stop-color="#f5a623"/>
                <stop offset="100%" stop-color="#00e5c3"/>
              </linearGradient></defs>
              <path d="M 16 64 A 44 44 0 0 1 104 64" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10" stroke-linecap="round"/>
              <path :d="gaugePath(indiceConfianca)" fill="none" stroke="url(#gg)" stroke-width="10" stroke-linecap="round"/>
              <text x="60" y="56" text-anchor="middle" font-size="20" font-weight="800" fill="#f0f0f8" font-family="monospace">{{ indiceConfianca }}%</text>
            </svg>
            <div class="cs-lbl">Índice de Confiança</div>
          </div>
          <div class="cs-sep"></div>
          <div class="cs-item">
            <div class="cs-val" style="color:var(--accent)">{{ secoes.length }}</div>
            <div class="cs-lbl">Cenários Analisados</div>
          </div>
          <div class="cs-sep"></div>
          <div class="cs-item">
            <div class="cs-val" style="color:var(--accent2)">{{ totalRodadas || '—' }}</div>
            <div class="cs-lbl">Rodadas Simuladas</div>
          </div>
          <div class="cs-sep"></div>
          <div class="cs-item">
            <div class="cs-val">{{ totalInteracoes ? totalInteracoes.toLocaleString('pt-BR') : (twPosts+rdPosts)||'—' }}</div>
            <div class="cs-lbl">Interações Totais</div>
          </div>
        </div>

        <div class="capa-foot">
          <div>Gerado em {{ geradoEm }}</div>
          <div>Documento Confidencial — AUGUR by itcast</div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════ -->
      <!-- SUMÁRIO (só print)                         -->
      <!-- ══════════════════════════════════════════ -->
      <div class="sumario pb-after print-only" v-if="secoes.length">
        <div class="sec-hd"><div class="sec-num">◆</div><h2 class="sec-title">Sumário</h2></div>
        <div class="sum-lista">
          <div v-for="(s,i) in secoes" :key="i" class="sum-item">
            <span class="sum-n">{{ String(i+1).padStart(2,'0') }}</span>
            <span class="sum-nome">{{ s.title }}</span>
            <span class="sum-dots"></span>
          </div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════ -->
      <!-- ABAS (só tela)                             -->
      <!-- ══════════════════════════════════════════ -->
      <div class="abas no-print">
        <button :class="['aba',{active:abaAtiva==='relatorio'}]" @click="abaAtiva='relatorio'">📋 Relatório</button>
        <button v-if="analytics" :class="['aba',{active:abaAtiva==='analytics'}]" @click="abaAtiva='analytics'">📈 Analytics</button>
        <button v-if="twTopPosts.length||rdTopPosts.length" :class="['aba',{active:abaAtiva==='posts'}]" @click="abaAtiva='posts'">💬 Posts</button>
      </div>

      <!-- ══════════════════════════════════════════ -->
      <!-- SEÇÕES DO RELATÓRIO                        -->
      <!-- ══════════════════════════════════════════ -->
      <div v-show="abaAtiva==='relatorio'" class="secoes">

        <div v-if="secoes.length">
          <div v-for="(s, idx) in secoes" :key="idx" :class="['secao', `tipo-${tipoSecao(s,idx)}`]">
            <div class="sec-hd">
              <div class="sec-num">{{ String(idx+1).padStart(2,'0') }}</div>
              <h2 class="sec-title">{{ s.title }}</h2>
            </div>

            <div v-if="s.content" class="sec-body">
              <!-- Cenários: 3 cards coloridos + conteúdo completo -->
              <div v-if="tipoSecao(s,idx)==='cenarios'" class="cen-wrap">
                <div class="cen-cards">
                  <div class="cen-card cen-ot">
                    <div class="cen-icon">🌟</div>
                    <div class="cen-nome">Cenário Otimista</div>
                    <div class="cen-desc">Alta probabilidade de sucesso com execução adequada.</div>
                  </div>
                  <div class="cen-card cen-bs">
                    <div class="cen-icon">⚖️</div>
                    <div class="cen-nome">Cenário Base</div>
                    <div class="cen-desc">Resultado mais provável com condições normais de mercado.</div>
                  </div>
                  <div class="cen-card cen-ps">
                    <div class="cen-icon">⚠️</div>
                    <div class="cen-nome">Cenário Pessimista</div>
                    <div class="cen-desc">Riscos a considerar com execução inadequada ou adversidades.</div>
                  </div>
                </div>
                <div class="md-body" v-html="md(s.content)"></div>
              </div>

              <!-- Recomendações: destaque visual -->
              <div v-else-if="tipoSecao(s,idx)==='recomendacoes'" class="rec-wrap">
                <div class="md-body" v-html="md(s.content)"></div>
              </div>

              <!-- Default -->
              <div v-else class="md-body" v-html="md(s.content)"></div>
            </div>

            <div v-else-if="s.description" class="sec-desc">{{ s.description }}</div>
          </div>
        </div>

        <!-- Fallback markdown -->
        <div v-else-if="report?.markdown_content" class="secao">
          <div class="sec-body"><div class="md-body" v-html="md(report.markdown_content)"></div></div>
        </div>

        <!-- Gráfico de atividade (tela e print) -->
        <div v-if="chartPoints" class="secao">
          <div class="sec-hd">
            <div class="sec-num">◆</div>
            <h2 class="sec-title">Evolução da Simulação por Rodada</h2>
          </div>
          <div class="sec-body">
            <div class="chart-legend">
              <span style="color:#1da1f2;font-size:12px;font-weight:600">■ Twitter</span>
              <span style="color:#ff4500;font-size:12px;font-weight:600">■ Reddit</span>
              <span style="color:#00e5c3;font-size:12px;font-weight:600">— Total</span>
            </div>
            <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="chart-svg" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#00e5c3" stop-opacity="0.2"/>
                  <stop offset="100%" stop-color="#00e5c3" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <g v-for="l in chartPoints.yLines" :key="l.val">
                <line :x1="cP.l" :y1="l.y" :x2="chartW-cP.r" :y2="l.y" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
                <text :x="cP.l-4" :y="l.y+4" text-anchor="end" fill="rgba(255,255,255,0.28)" font-size="9">{{ l.val }}</text>
              </g>
              <g v-for="lb in chartPoints.labels" :key="lb.r">
                <text :x="lb.x" :y="chartH-cP.b+14" text-anchor="middle" fill="rgba(255,255,255,0.28)" font-size="9">R{{ lb.r }}</text>
              </g>
              <path :d="chartPoints.area"  fill="url(#ag)" stroke="none"/>
              <path :d="chartPoints.tw"    fill="none" stroke="#1da1f2" stroke-width="1.5" stroke-linejoin="round"/>
              <path :d="chartPoints.rd"    fill="none" stroke="#ff4500" stroke-width="1.5" stroke-linejoin="round"/>
              <path :d="chartPoints.total" fill="none" stroke="#00e5c3" stroke-width="2.5" stroke-linejoin="round"/>
            </svg>
          </div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════ -->
      <!-- ABA ANALYTICS (só tela)                    -->
      <!-- ══════════════════════════════════════════ -->
      <div v-if="abaAtiva==='analytics' && analytics" class="analytics no-print">
        <div class="an-metrics">
          <div class="an-m"><div class="an-ml">Total de interações</div><div class="an-mv">{{ totalInteracoes.toLocaleString('pt-BR') }}</div></div>
          <div class="an-m"><div class="an-ml">Posts Twitter</div><div class="an-mv" style="color:#1da1f2">{{ twPosts }}</div></div>
          <div class="an-m"><div class="an-ml">Posts Reddit</div><div class="an-mv" style="color:#ff4500">{{ rdPosts }}</div></div>
          <div class="an-m"><div class="an-ml">Rodadas</div><div class="an-mv">{{ totalRodadas }}</div></div>
        </div>
        <div class="an-chart" v-if="chartPoints">
          <div class="an-chart-head">
            <span style="font-size:14px;font-weight:600;color:var(--text-primary)">Atividade por Rodada</span>
            <div style="display:flex;gap:12px">
              <span style="color:#1da1f2;font-size:11px;font-weight:600">■ Twitter</span>
              <span style="color:#ff4500;font-size:11px;font-weight:600">■ Reddit</span>
            </div>
          </div>
          <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="chart-svg">
            <g v-for="l in chartPoints.yLines" :key="l.val">
              <line :x1="cP.l" :y1="l.y" :x2="chartW-cP.r" :y2="l.y" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
              <text :x="cP.l-4" :y="l.y+4" text-anchor="end" fill="rgba(255,255,255,0.28)" font-size="9">{{ l.val }}</text>
            </g>
            <g v-for="lb in chartPoints.labels" :key="lb.r">
              <text :x="lb.x" :y="chartH-cP.b+14" text-anchor="middle" fill="rgba(255,255,255,0.28)" font-size="9">R{{ lb.r }}</text>
            </g>
            <path :d="chartPoints.area" fill="url(#ag)" stroke="none"/>
            <path :d="chartPoints.tw"   fill="none" stroke="#1da1f2" stroke-width="2" stroke-linejoin="round"/>
            <path :d="chartPoints.rd"   fill="none" stroke="#ff4500" stroke-width="2" stroke-linejoin="round"/>
          </svg>
        </div>
        <!-- Barras de agentes -->
        <div class="an-chart" v-if="twEngagement.length">
          <div style="font-size:14px;font-weight:600;color:var(--text-primary);margin-bottom:14px">Top Agentes — Posts publicados</div>
          <div class="bar-list">
            <div v-for="(ag,i) in twEngagement.slice(0,8)" :key="ag.name" class="bar-row">
              <div class="bar-name">{{ ag.name || `Agente ${i+1}` }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{width:((ag.posts/(twEngagement[0]?.posts||1))*100)+'%',background:corBar(i)}"></div>
              </div>
              <div class="bar-val">{{ ag.posts }}</div>
              <div class="bar-likes">❤️ {{ ag.likes_received }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════ -->
      <!-- ABA POSTS (só tela)                        -->
      <!-- ══════════════════════════════════════════ -->
      <div v-if="abaAtiva==='posts'" class="posts no-print">
        <div class="posts-col" v-if="twTopPosts.length">
          <div class="ph"><span class="tw-b">Twitter / X</span><span class="ps">Top posts</span></div>
          <div v-for="p in twTopPosts" :key="p.post_id" class="pc tw-l">
            <div class="pa">{{ p.name||p.user_name||'Agente' }}</div>
            <div class="pct">{{ truncar(p.content,200) }}</div>
            <div class="pst"><span class="sl">❤️ {{ p.num_likes }}</span><span v-if="p.num_dislikes" class="sd">👎 {{ p.num_dislikes }}</span></div>
          </div>
        </div>
        <div class="posts-col" v-if="rdTopPosts.length">
          <div class="ph"><span class="rd-b">Reddit</span><span class="ps">Top posts</span></div>
          <div v-for="p in rdTopPosts" :key="p.post_id" class="pc rd-l">
            <div class="pa">{{ p.name||p.user_name||'Agente' }}</div>
            <div class="pct">{{ truncar(p.content,200) }}</div>
            <div class="pst"><span class="sl">❤️ {{ p.num_likes }}</span></div>
          </div>
        </div>
      </div>

      <!-- Rodapé doc -->
      <div class="doc-foot print-only">
        <span>Documento gerado automaticamente pelo AUGUR · by itcast</span>
        <span>{{ geradoEm }}</span>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
/* ─── Utilitários ──────────────────────────────────────────── */
.loading { display:flex;align-items:center;gap:16px;padding:60px; }
.spin { width:28px;height:28px;border:3px solid var(--border-md);border-top-color:var(--accent);border-radius:50%;animation:sp .8s linear infinite;flex-shrink:0; }
@keyframes sp { to { transform:rotate(360deg); } }
.ld-t { font-size:15px;font-weight:600;color:var(--text-primary); }
.ld-s { font-size:13px;color:var(--text-muted);margin-top:4px; }
.erro-state { text-align:center;padding:60px;display:flex;flex-direction:column;align-items:center;gap:14px; }
.btn-ghost { background:none;border:1px solid var(--border);color:var(--text-secondary);border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer; }
.rw { display:flex;flex-direction:column;gap:20px; }

/* ─── Capa ──────────────────────────────────────────────────── */
.capa { background:linear-gradient(150deg,#0e0e1a 0%,#111128 50%,#0d0d18 100%);border:1px solid rgba(124,111,247,0.2);border-radius:16px;padding:36px 40px;display:flex;flex-direction:column;gap:28px;position:relative;overflow:hidden; }
.capa::before { content:'';position:absolute;top:-80px;right:-60px;width:260px;height:260px;background:radial-gradient(circle,rgba(124,111,247,0.1) 0%,transparent 70%);pointer-events:none; }
.capa-top { display:flex;align-items:center;justify-content:space-between; }
.capa-brand { display:flex;align-items:center;gap:12px; }
.capa-logo { width:42px;height:42px;border-radius:10px; }
.brand-n { font-size:21px;font-weight:900;color:#f0f0f8;letter-spacing:3px; }
.brand-s { font-size:10px;color:#6b6b80;letter-spacing:1.2px;text-transform:uppercase;margin-top:2px; }
.capa-badge { font-size:10px;font-weight:700;color:var(--accent2);letter-spacing:2px;text-transform:uppercase;background:rgba(124,111,247,0.1);border:1px solid rgba(124,111,247,0.25);border-radius:20px;padding:5px 14px; }

.capa-divider { display:flex;align-items:center; }
.div-line { flex:1;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent); }
.div-gem { width:8px;height:8px;background:var(--accent2);transform:rotate(45deg);flex-shrink:0;margin:0 14px; }

.capa-mid { display:flex;flex-direction:column;gap:14px; }
.capa-titulo { font-size:clamp(18px,2.5vw,28px);font-weight:800;color:#f0f0f8;line-height:1.3;letter-spacing:-.4px;margin:0; }
.capa-hip { background:rgba(0,229,195,0.05);border:1px solid rgba(0,229,195,0.15);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;padding:13px 16px; }
.hip-lbl { font-size:10px;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px; }
.hip-txt { font-size:13px;color:#9898b0;line-height:1.7; }
.capa-resumo { font-size:13px;color:#6b6b80;font-style:italic;line-height:1.7; }

.capa-stats { display:flex;align-items:stretch;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;overflow:hidden; }
.cs-item { flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:18px 12px; }
.cs-sep { width:1px;background:rgba(255,255,255,0.06);margin:12px 0; }
.cs-val { font-size:26px;font-weight:900;color:#f0f0f8;font-family:monospace; }
.cs-lbl { font-size:10px;color:#6b6b80;text-transform:uppercase;letter-spacing:.8px;text-align:center; }
.gauge-svg { width:110px;height:auto; }

.capa-foot { display:flex;justify-content:space-between;font-size:11px;color:#6b6b80;border-top:1px solid rgba(255,255,255,0.06);padding-top:12px; }

/* ─── Sumário ─────────────────────────────────────────────── */
.sumario { padding:20px 0; }
.sum-lista { display:flex;flex-direction:column;gap:10px;margin-top:16px; }
.sum-item { display:flex;align-items:baseline;gap:10px;font-size:14px; }
.sum-n { font-size:11px;font-weight:700;color:var(--accent2);font-family:monospace;min-width:26px; }
.sum-nome { color:var(--text-primary);font-weight:500; }
.sum-dots { flex:1;border-bottom:1px dotted var(--border-md); }

/* ─── Abas ─────────────────────────────────────────────────── */
.abas { display:flex;gap:4px;border-bottom:1px solid var(--border); }
.aba { background:none;border:none;border-bottom:2px solid transparent;color:var(--text-muted);padding:8px 18px;font-size:13px;font-weight:500;cursor:pointer;transition:all .2s;margin-bottom:-1px;border-radius:8px 8px 0 0; }
.aba:hover { color:var(--text-secondary);background:var(--bg-raised); }
.aba.active { color:var(--accent2);border-bottom-color:var(--accent2);background:var(--bg-surface); }

/* ─── Seções ──────────────────────────────────────────────── */
.secoes { display:flex;flex-direction:column;gap:16px; }
.secao { background:var(--bg-surface);border:1px solid var(--border);border-radius:14px;overflow:hidden; }
.sec-hd { display:flex;align-items:center;gap:14px;padding:16px 22px;background:var(--bg-raised);border-bottom:1px solid var(--border); }
.sec-num { font-size:11px;font-weight:800;color:var(--accent2);background:rgba(124,111,247,0.12);border:1px solid rgba(124,111,247,0.2);padding:4px 10px;border-radius:6px;flex-shrink:0;font-family:monospace; }
.sec-title { font-size:16px;font-weight:700;color:var(--text-primary);margin:0; }
.sec-body { padding:22px; }
.sec-desc { padding:16px 22px;color:var(--text-muted);font-size:13px;font-style:italic; }

/* ─── Markdown ─────────────────────────────────────────────── */
.md-body { color:var(--text-secondary);font-size:14px;line-height:1.88; }
.md-body :deep(h1),.md-body :deep(h2) { font-size:16px;font-weight:700;color:var(--text-primary);margin:20px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px; }
.md-body :deep(h3),.md-body :deep(h4) { font-size:14px;font-weight:600;color:var(--accent2);margin:14px 0 7px; }
.md-body :deep(strong) { color:var(--text-primary); }
.md-body :deep(em) { color:var(--accent);font-style:normal;font-weight:600; }
.md-body :deep(blockquote) { border-left:3px solid var(--accent2);background:rgba(124,111,247,0.06);padding:10px 16px;margin:14px 0;border-radius:0 8px 8px 0;color:var(--text-secondary);font-style:italic; }
.md-body :deep(ul) { padding-left:22px;margin:10px 0; }
.md-body :deep(li) { margin-bottom:8px; }
.md-body :deep(p) { margin:0 0 14px; }

/* ─── Cenários ─────────────────────────────────────────────── */
.cen-wrap { display:flex;flex-direction:column;gap:16px; }
.cen-cards { display:grid;grid-template-columns:repeat(3,1fr);gap:12px; }
.cen-card { border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:8px; }
.cen-ot { background:rgba(0,229,195,0.06);border:1px solid rgba(0,229,195,0.2); }
.cen-bs { background:rgba(245,166,35,0.06);border:1px solid rgba(245,166,35,0.2); }
.cen-ps { background:rgba(255,90,90,0.06);border:1px solid rgba(255,90,90,0.2); }
.cen-icon { font-size:22px; }
.cen-nome { font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px; }
.cen-ot .cen-nome { color:var(--accent); }
.cen-bs .cen-nome { color:#f5a623; }
.cen-ps .cen-nome { color:var(--danger); }
.cen-desc { font-size:12px;color:var(--text-muted);line-height:1.6; }

/* ─── Chart ─────────────────────────────────────────────────── */
.chart-legend { display:flex;gap:16px;margin-bottom:10px; }
.chart-svg { width:100%;height:auto;display:block; }

/* ─── Analytics ─────────────────────────────────────────────── */
.analytics { display:flex;flex-direction:column;gap:16px; }
.an-metrics { display:grid;grid-template-columns:repeat(4,1fr);gap:12px; }
.an-m { background:var(--bg-surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px; }
.an-ml { font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px; }
.an-mv { font-size:24px;font-weight:800;color:var(--text-primary);font-family:monospace; }
.an-chart { background:var(--bg-surface);border:1px solid var(--border);border-radius:12px;padding:20px; }
.an-chart-head { display:flex;align-items:center;justify-content:space-between;margin-bottom:12px; }
.bar-list { display:flex;flex-direction:column;gap:9px; }
.bar-row { display:flex;align-items:center;gap:10px; }
.bar-name { font-size:12px;color:var(--text-secondary);min-width:130px;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.bar-track { flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden; }
.bar-fill { height:100%;border-radius:3px;transition:width .4s; }
.bar-val { font-size:12px;color:var(--text-primary);font-family:monospace;min-width:22px;text-align:right; }
.bar-likes { font-size:11px;color:var(--text-muted);min-width:42px; }

/* ─── Posts ─────────────────────────────────────────────────── */
.posts { display:grid;grid-template-columns:1fr 1fr;gap:16px; }
.posts-col { display:flex;flex-direction:column;gap:10px; }
.ph { display:flex;align-items:center;gap:10px;margin-bottom:4px; }
.tw-b { background:rgba(29,161,242,.15);color:#1da1f2;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px; }
.rd-b { background:rgba(255,69,0,.15);color:#ff4500;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px; }
.ps { font-size:12px;color:var(--text-muted); }
.pc { background:var(--bg-surface);border:1px solid var(--border);border-radius:10px;padding:13px;display:flex;flex-direction:column;gap:7px; }
.tw-l { border-left:3px solid #1da1f2; }
.rd-l { border-left:3px solid #ff4500; }
.pa { font-size:12px;font-weight:600;color:var(--text-secondary); }
.pct { font-size:13px;color:var(--text-primary);line-height:1.6; }
.pst { display:flex;gap:12px;font-size:12px; }
.sl { color:#f5a623; }
.sd { color:var(--danger); }

/* ─── Doc footer ─────────────────────────────────────────────── */
.doc-foot { display:none; }

/* ─── PRINT ─────────────────────────────────────────────────── */
@media print {
  * { -webkit-print-color-adjust:exact !important; print-color-adjust:exact !important; box-sizing:border-box; }
  body { background:#fff !important; color:#111 !important; }
  .no-print { display:none !important; }
  .print-only { display:block !important; }

  @page { size:A4; margin:16mm 15mm 18mm 15mm; }

  .rw { gap:0; }
  .pb-after { page-break-after:always; break-after:page; }
  .secao { page-break-inside:avoid; break-inside:avoid; margin-bottom:28px !important; }

  /* Capa em print */
  .capa { background:#0d0d1a !important;border:none !important;border-radius:0 !important;padding:56px 50px !important;min-height:100vh;justify-content:space-between !important; }
  .capa::before { display:none; }
  .capa-titulo { color:#f0f0f8 !important;font-size:26px !important; }
  .brand-n { color:#f0f0f8 !important; }
  .brand-s,.cs-lbl,.capa-foot { color:#6b6b80 !important; }
  .cs-val { color:#f0f0f8 !important; }
  .capa-badge { color:#a78bfa !important;border-color:rgba(124,111,247,0.4) !important; }
  .hip-txt { color:#9898b0 !important; }
  .capa-resumo { color:#6b6b80 !important; }
  .capa-stats { background:rgba(255,255,255,0.03) !important;border-color:rgba(255,255,255,0.08) !important; }

  /* Sumário em print */
  .sumario { padding:40px 0 !important; }
  .sec-title { color:#1a1a2e !important; }
  .sum-nome { color:#1a1a2e !important; }
  .sum-n,.sec-num { color:#7c6ff7 !important;background:#ede9ff !important;border-color:#c4b5fd !important; }
  .sec-hd { background:#f8f8fc !important;border-bottom:2px solid #e8e8f0 !important;border-radius:0 !important; }

  /* Seções em print */
  .secao { background:#fff !important;border:none !important;border-radius:0 !important;border-bottom:1px solid #e0e0ee !important; }
  .sec-body { padding:16px 0 !important; }
  .sec-hd { padding:12px 0 10px !important;margin-bottom:12px !important; }
  .md-body { color:#2a2a3e !important;font-size:12.5px !important;line-height:1.9 !important; }
  .md-body :deep(h1),.md-body :deep(h2) { color:#1a1a2e !important;border-bottom-color:#e0e0ee !important; }
  .md-body :deep(h3),.md-body :deep(h4) { color:#5046a8 !important; }
  .md-body :deep(strong) { color:#1a1a2e !important; }
  .md-body :deep(blockquote) { background:#f0efff !important;border-left-color:#7c6ff7 !important;color:#3a3a5e !important; }

  /* Cenários em print: 3 cols */
  .cen-card { border:1.5px solid #d1d5db !important; }
  .cen-ot { background:#f0fdf4 !important;border-color:#86efac !important; }
  .cen-bs { background:#fffbeb !important;border-color:#fcd34d !important; }
  .cen-ps { background:#fff1f2 !important;border-color:#fca5a5 !important; }
  .cen-ot .cen-nome { color:#15803d !important; }
  .cen-bs .cen-nome { color:#92400e !important; }
  .cen-ps .cen-nome { color:#991b1b !important; }
  .cen-desc { color:#374151 !important; }

  /* Chart em print */
  .chart-legend span { color: inherit !important; }

  /* Footer doc */
  .doc-foot { display:flex !important;justify-content:space-between !important;font-size:10px !important;color:#9898b0 !important;border-top:1px solid #e0e0ee !important;padding-top:10px !important;margin-top:36px !important; }

  /* Esconder analytics/posts em print */
  .analytics,.posts { display:none !important; }
  .abas { display:none !important; }
}

@media screen {
  .print-only { display:none !important; }
}
@media (max-width:1080px) {
  .an-metrics { grid-template-columns:repeat(2,1fr); }
  .posts { grid-template-columns:1fr; }
  .cen-cards { grid-template-columns:1fr; }
}
</style>
