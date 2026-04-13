import { createRouter, createWebHistory, useRouter } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import { useApiStore } from '@/stores/api'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      meta: { title: 'Dashboard' },
      component: HomeView,
    },
    {
      path: '/login',
      name: 'login',
      meta: { title: 'Login' },
      component: LoginView,
    },
    {
      path: '/about',
      name: 'about',
      meta: { title: 'About' },
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import('../views/AboutView.vue'),
    },
  ],
})
router.beforeEach((route) => {
  const api = useApiStore()
  const router = useRouter()
  if (route.path == '/login' && api.logged) {
    router.push({ name: 'home' })
  }
})

// Change title of the page to include the title of the route. Add "- Dev" in dev mode.
router.afterEach((route) => {
  let title = 'PhotoV'
  if (import.meta.env.DEV) {
    title += ' - Dev'
  }
  title += ' | ' + route.meta.title
  document.title = title
})

export default router
