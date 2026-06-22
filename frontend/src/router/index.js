import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'
import api from '../api/client'

const routes = [
  { path: '/', component: HomeView },
  { path: '/login', component: LoginView },
  { path: '/workspace', component: WorkspaceView }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

let sessionVerified = false

router.beforeEach(async (to) => {
  if (to.path === '/workspace') {
    if (!sessionVerified) {
      try {
        await api.get('/me')
        sessionVerified = true
        localStorage.setItem('isAuthenticated', 'true')
      } catch {
        sessionVerified = true
        localStorage.removeItem('isAuthenticated')
        return '/login'
      }
    }
    const authed = localStorage.getItem('isAuthenticated') === 'true'
    if (!authed) return '/login'
  }
  
  if (to.path === '/login') {
    const authed = localStorage.getItem('isAuthenticated') === 'true'
    if (authed) return '/'
  }
})

router.resetSessionVerified = () => {
  sessionVerified = false
}

export default router
