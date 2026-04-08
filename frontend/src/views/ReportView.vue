<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/layout/AppShell.vue'
import AugurButton from '../components/ui/AugurButton.vue'
import SentimentBar from '../components/ui/SentimentBar.vue'
import service from '../api'

const route = useRoute()
const router = useRouter()
const report = ref({ summary: '', insights: [], metrics: {}, keywords: [] })
const activeTab = ref('forcas')
const languageWarning = ref('')

const hasCJK = (value = '') => /[\u3400-\u9FFF]/.test(value)
const sanitizeText = (value = '') => {
  if (!value) return ''
  return hasCJK(value)
    ? 'Conteúdo em idioma não-português detectado. Gere uma nova rodada com prompt forçando saída em português.'
    : value
}

onMounted(async () => {
  const response = await service.get(`/api/report/${route.params.reportId}`)
  const raw = response.data || response
  const summaryRaw = raw.summary || raw.executive_summary || 'Sem sumário disponível.'
  const insightsRaw = Array.isArray(raw.insights) ? raw.insights : []
  const cjkFound = hasCJK(summaryRaw) || insightsRaw.some((i) => hasCJK(i?.text || i?.description || ''))
  languageWarning.value = cjkFound ? '⚠️ Detectamos conteúdo em idioma não-português. O relatório abaixo foi higienizado para leitura executiva em português.' : ''
  report.value = {
    summary: sanitizeText(summaryRaw),
    insights: insightsRaw.map((insight) => ({
      ...insight,
      text: sanitizeText(insight.text || insight.description || '')
    })),
    metrics: raw.metrics || {},
    keywords: (raw.keywords || []).map((k) => sanitizeText(String(k)))
  }
})

const colorByTag = (tag) => ({ Oportunidade: '#00e5c3', Risco: '#ff5a5a', Observação: '#7c6ff7' }[tag] || '#9898b0')
const confidence = computed(() => {
  const c = Number(report.value.metrics.confidence ?? report.value.metrics.score ?? 72)
  return Math.max(0, Math.min(100, Number.isFinite(c) ? c : 72))
})
const scenariosCount = computed(() => {
  return Number(report.value.metrics.scenarios || report.value.metrics.cenarios || 3)
})
const risksCount = computed(() => {
  return report.value.insights.filter(i => (i.tag || '').toLowerCase().includes('risco')).length
})
const topDecision = computed(() => {
  if (confidence.value < 55) return 'Reavaliar posicionamento antes do lançamento amplo'
  if (risksCount.value >= 3) return 'Lançar com piloto controlado e gestão de risco ativa'
  return 'Lançamento faseado com foco em aquisição + retenção'
})
const briefCards = computed(() => ([
  { title: 'Decisão recomendada', value: topDecision.value },
  { title: 'Cenário mais provável', value: report.value.metrics.top_scenario || 'Crescimento sustentável' },
  { title: 'Risco crítico agora', value: risksCount.value ? `${risksCount.value} risco(s) monitorar` : 'Sem risco crítico identificado' },
  { title: 'Sentimento geral', value: report.value.metrics.sentiment_summary || 'Predomínio neutro com sinais mistos' }
]))
const mapaForcas = computed(() => ([
  { nome: 'Tração de mercado', valor: Number(report.value.metrics.purchase_intent || 0), cor: '#00e5c3' },
  { nome: 'Potencial de viralização', valor: Number(report.value.metrics.viral_probability || 0), cor: '#7c6ff7' },
  { nome: 'Confiança da análise', valor: confidence.value, cor: '#5fdbff' },
  { nome: 'Risco reputacional', valor: Math.min(100, risksCount.value * 20), cor: '#ff5a5a' }
]))
const padroesEmergentes = computed(() => {
  const keys = report.value.keywords.filter(Boolean).slice(0, 8)
  return keys.length ? keys : ['Preço', 'Conveniência', 'Confiança', 'Identidade local']
})
const hipotesesCausais = computed(() => {
  const base = report.value.insights.slice(0, 3).map(i => i.text).filter(Boolean)
  if (base.length) return base.map((b, idx) => `H${idx + 1}: ${b}`)
  return [
    'H1: Mensagem local + proposta diferenciada aumenta intenção de compra no curto prazo.',
    'H2: Pressão competitiva reduz margem se não houver narrativa clara de valor.',
    'H3: Ganho de confiança ocorre quando prova social acompanha a campanha de lançamento.'
  ]
})

const exportPdf = () => {
  const html = `<!doctype html><html><head><meta charset="utf-8"/><title>Relatório AUGUR</title>
  <style>
  body{font-family:Inter,Arial,sans-serif;padding:28px;color:#0f172a} h1{margin:0 0 6px} h2{margin:24px 0 8px}
  .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
  .card{border:1px solid #d7def0;border-radius:10px;padding:12px;background:#f8fbff}
  .bar{height:8px;background:#e8eefc;border-radius:999px;overflow:hidden}.fill{height:100%}
  ul{margin:8px 0 0 18px}
  </style></head><body>
  <h1>Relatório Executivo AUGUR</h1>
  <div>${new Date().toLocaleString('pt-BR')}</div>
  <h2>Resumo Executivo</h2>
  <div class="card">${report.value.summary}</div>
  <h2>Briefing CEO</h2>
  <div class="grid">${briefCards.value.map(c=>`<div class="card"><b>${c.title}</b><div>${c.value}</div></div>`).join('')}</div>
  <h2>Mapa de Forças</h2>
  ${mapaForcas.value.map(i=>`<div style="margin:8px 0">${i.nome} — ${i.valor}%<div class="bar"><div class="fill" style="width:${i.valor}%;background:${i.cor}"></div></div></div>`).join('')}
  <h2>Padrões Emergentes</h2>
  <div class="card">${padroesEmergentes.value.join(' • ')}</div>
  <h2>Hipóteses Causais</h2>
  <ul>${hipotesesCausais.value.map(h=>`<li>${h}</li>`).join('')}</ul>
  </body></html>`
  const win = window.open('', '_blank')
  if (!win) return
  win.document.write(html)
  win.document.close()
  win.focus()
  win.print()
}
</script>
<template>
  <AppShell title="Relatório">
    <template #actions>
      <AugurButton variant="ghost" @click="exportPdf">Exportar PDF</AugurButton>
      <AugurButton @click="router.push(`/agentes/${route.params.reportId}`)">Entrevistar Agentes</AugurButton>
    </template>
    <section class="layout">
      <div class="main">
        <article v-if="languageWarning" class="warning">{{ languageWarning }}</article>
        <article class="summary"><h3>Sumário Executivo</h3><p>{{ report.summary }}</p></article>
        <article class="brief">
          <h3>Briefing CEO — 1 minuto</h3>
          <div class="brief-grid">
            <div v-for="card in briefCards" :key="card.title" class="brief-card">
              <small>{{ card.title }}</small>
              <strong>{{ card.value }}</strong>
            </div>
          </div>
        </article>
        <article class="tabs-card">
          <h3>Análise Profunda</h3>
          <div class="tabs">
            <button class="tab" :class="{active:activeTab==='forcas'}" @click="activeTab='forcas'">Mapa de Forças</button>
            <button class="tab" :class="{active:activeTab==='padroes'}" @click="activeTab='padroes'">Padrões Emergentes</button>
            <button class="tab" :class="{active:activeTab==='causais'}" @click="activeTab='causais'">Hipóteses Causais</button>
          </div>
          <div v-if="activeTab==='forcas'" class="forcas">
            <div v-for="item in mapaForcas" :key="item.nome" class="forca-item">
              <div class="forca-row"><span>{{ item.nome }}</span><strong>{{ item.valor }}%</strong></div>
              <div class="bar"><div class="fill" :style="{ width: item.valor + '%', background: item.cor }"></div></div>
            </div>
          </div>
          <div v-else-if="activeTab==='padroes'" class="keywords">
            <span v-for="(k, idx) in padroesEmergentes" :key="idx">{{ k }}</span>
          </div>
          <ul v-else class="causais">
            <li v-for="h in hipotesesCausais" :key="h">{{ h }}</li>
          </ul>
        </article>
        <article class="card">
          <h3>Insights detalhados</h3>
          <div v-for="(insight, idx) in report.insights" :key="idx" class="insight">
            <span class="tag" :style="{ color: colorByTag(insight.tag), borderColor: colorByTag(insight.tag) }">{{ insight.tag || 'Observação' }}</span>
            <p>{{ insight.text || insight.description }}</p>
            <small>Confiança: {{ insight.confidence || 0 }}%</small>
          </div>
        </article>
      </div>
      <aside class="side">
        <article class="card mini-stats">
          <p><strong>{{ confidence }}%</strong> confiança</p>
          <p><strong>{{ scenariosCount }}</strong> cenários</p>
          <p><strong>{{ risksCount }}</strong> riscos mapeados</p>
        </article>
        <SentimentBar label="Sentimento geral" :positive="report.metrics.positive || 50" :neutral="report.metrics.neutral || 30" :negative="report.metrics.negative || 20" />
        <article class="card"><h3>Principais métricas</h3><p>Agentes alcançados: {{ report.metrics.agents_reached || 0 }}</p><p>Posts gerados: {{ report.metrics.posts_generated || 0 }}</p><p>Intenção de compra: {{ report.metrics.purchase_intent || 0 }}%</p><p>Probabilidade de viral: {{ report.metrics.viral_probability || 0 }}%</p></article>
        <article class="card"><h3>Palavras-chave</h3><div class="keywords"><span v-for="(keyword,idx) in report.keywords" :key="idx">{{ keyword }}</span></div></article>
      </aside>
    </section>
  </AppShell>
</template>
<style scoped>
.layout{display:grid;grid-template-columns:2fr 1fr;gap:12px}.main,.side{display:grid;gap:10px}
.summary{border-left:3px solid var(--accent);background:var(--bg-raised);padding:14px;border-radius:var(--r-md);border:1px solid var(--border)}
.warning{background:rgba(255,166,0,.12);border:1px solid rgba(255,166,0,.4);padding:10px;border-radius:var(--r-sm);font-size:13px}
.card{background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--r-md);padding:14px}
.brief{background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--r-md);padding:14px}
.brief-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.brief-card{border:1px solid var(--border);background:var(--bg-overlay);border-radius:10px;padding:10px;display:grid;gap:4px}
.tabs-card{background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--r-md);padding:14px}
.tabs{display:flex;gap:8px;margin-bottom:10px}
.tab{border:1px solid var(--border);background:var(--bg-overlay);padding:7px 10px;border-radius:8px;cursor:pointer}
.tab.active{border-color:var(--accent2);color:var(--accent2)}
.forcas{display:grid;gap:10px}.forca-row{display:flex;justify-content:space-between;font-size:13px}
.bar{height:8px;background:var(--border);border-radius:999px;overflow:hidden}.fill{height:100%}
.causais{padding-left:18px;display:grid;gap:8px}
.insight{border-top:1px solid var(--border);padding-top:10px;margin-top:10px}.tag{border:1px solid;padding:2px 7px;border-radius:999px;font-size:12px}
.keywords{display:flex;gap:8px;flex-wrap:wrap}.keywords span{background:var(--accent-dim);padding:4px 8px;border-radius:999px}
.mini-stats p{margin:0;display:flex;justify-content:space-between}
@media(max-width:1080px){.layout{grid-template-columns:1fr}}
</style>
