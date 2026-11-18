import { createRouter, createWebHashHistory } from 'vue-router'
import { auth, refreshAuth } from './store'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('./views/Login.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue') },
    { path: '/instances/:id', name: 'instance', component: () => import('./views/Instance.vue'), props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

router.beforeEach(async (to) => {
  if (!auth.checked) {
    try {
      await refreshAuth()
    } catch (e) {
      /* ignore */
    }
  }
  if (!to.meta.public && !auth.authenticated) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.authenticated) {
    return { name: 'dashboard' }
  }
  return true
})

export default router