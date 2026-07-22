import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/', name: 'Home', component: () => import('../views/HomeView.vue'), meta: { requiresAuth: true } },
  { path: '/ai', name: 'AIChat', component: () => import('../views/AIChatView.vue'), meta: { requiresAuth: true } },
  { path: '/classroom', name: 'Classroom', component: () => import('../views/ClassroomView.vue'), meta: { requiresAuth: true } },
  { path: '/practice/:sessionId', name: 'Practice', component: () => import('../views/PracticeView.vue'), meta: { requiresAuth: true } },
  { path: '/collection', name: 'Collection', component: () => import('../views/WrongBookView.vue'), meta: { requiresAuth: true } },
  { path: '/review', name: 'Review', component: () => import('../views/ReviewView.vue'), meta: { requiresAuth: true } },
  { path: '/vocab', name: 'Vocab', component: () => import('../views/VocabView.vue'), meta: { requiresAuth: true } },
  { path: '/notes', name: 'NotesList', component: () => import('../views/NotesListView.vue'), meta: { requiresAuth: true } },
  { path: '/notes/:id', name: 'Note', component: () => import('../views/NotesView.vue'), meta: { requiresAuth: true } },
  { path: '/stats', name: 'Dashboard', component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true } },
  { path: '/settings', name: 'Settings', component: () => import('../views/SettingsView.vue'), meta: { requiresAuth: true } },
  { path: '/account', name: 'Account', component: () => import('../views/AccountView.vue'), meta: { requiresAuth: true } },
  { path: '/admin', name: 'Admin', component: () => import('../views/AdminView.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/vault', name: 'Vault', component: () => import('../views/VaultView.vue'), meta: { requiresAuth: true } },
  { path: '/admin/user/:userId', name: 'AdminUserView', component: () => import('../views/AdminUserView.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFoundView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.requiresAdmin) {
    // Decode JWT to check role (simple base64 decode of payload)
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (payload.role !== 'admin' && payload.role !== 'superadmin') {
        next('/')
        return
      }
    } catch { next('/'); return }
    next()
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

router.afterEach((to) => {
  const titles = {
    '/': '学习中心',
    '/login': '登录',
    '/collection': '好题锦集',
    '/review': '今日复习',
    '/vocab': '背单词',
    '/settings': '设置',
    '/account': '账号管理',
    '/admin': '管理看板',
  }
  document.title = '三一 · ' + (titles[to.path] || '学而时习之')
})

export default router
