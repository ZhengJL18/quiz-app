import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue'), meta: { requiresAuth: true } },
  { path: '/practice/:sessionId', name: 'Practice', component: () => import('../views/PracticeView.vue'), meta: { requiresAuth: true } },
  { path: '/wrong-book', name: 'WrongBook', component: () => import('../views/WrongBookView.vue'), meta: { requiresAuth: true } },
  { path: '/review', name: 'Review', component: () => import('../views/ReviewView.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
