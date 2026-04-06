import { createRouter, createWebHistory } from 'vue-router'
import DashboardView    from '../views/DashboardView.vue'
import NovoProjetoView  from '../views/NovoProjetoView.vue'
import ProjetoView      from '../views/ProjetoView.vue'
import SimulationView   from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView       from '../views/ReportView.vue'
import InteractionView  from '../views/InteractionView.vue'
import GraphView        from '../views/GraphView.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: DashboardView
  },
  {
    // Rota principal de criação — /projeto/novo
    path: '/projeto/novo',
    name: 'NovoProjeto',
    component: NovoProjetoView
  },
  {
    // Detalhe do projeto com lista de simulações
    path: '/projeto/:projectId',
    name: 'Projeto',
    component: ProjetoView,
    props: true
  },
  {
    // /novo redireciona para /projeto/novo (mantém compatibilidade)
    path: '/novo',
    redirect: '/projeto/novo'
  },
  {
    // Pipeline de preparação: construção do grafo → criar sim → preparar → iniciar
    path: '/simulacao/:projectId',
    name: 'Simulacao',
    component: SimulationView,
    props: true
  },
  {
    // Execução ao vivo da simulação
    path: '/simulacao/:simulationId/executar',
    name: 'Execucao',
    component: SimulationRunView,
    props: true
  },
  {
    // Relatório analítico
    path: '/relatorio/:reportId',
    name: 'Relatorio',
    component: ReportView,
    props: true
  },
  {
    // Entrevista com agentes
    path: '/agentes/:reportId',
    name: 'Agentes',
    component: InteractionView,
    props: true
  },
  {
    // Grafo de conhecimento do projeto
    path: '/projeto/:projectId/grafo',
    name: 'Grafo',
    component: GraphView,
    props: true
  },
  {
    // Fallback — qualquer rota não encontrada vai para home
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})
