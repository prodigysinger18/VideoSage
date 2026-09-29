import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import VideoList from '../views/VideoList.vue'
import VideoDetail from '../views/VideoDetail.vue'
import PersonList from '../views/PersonList.vue'
import PersonDetail from '../views/PersonDetail.vue'
import AnomalyView from '../views/AnomalyView.vue'
import AgentView from '../views/AgentView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/videos' },
    { path: '/dashboard', component: DashboardView, meta: { title: 'Dashboard' } },
    { path: '/videos', component: VideoList, meta: { title: '视频管理' } },
    { path: '/video/:id', component: VideoDetail, meta: { title: '视频详情' } },
    { path: '/persons', component: PersonList, meta: { title: '人物分析' } },
    { path: '/persons/:videoId', component: PersonList, meta: { title: '人物分析' } },
    { path: '/video/:videoId/person/:personId', component: PersonDetail, meta: { title: '人物详情' } },
    { path: '/anomalies', component: AnomalyView, meta: { title: '异常检测' } },
    { path: '/agent', component: AgentView, meta: { title: 'Agent 问答' } }
  ]
})
