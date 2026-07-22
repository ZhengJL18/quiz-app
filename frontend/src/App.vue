<template>
  <div class="min-h-screen flex flex-col bg-[var(--surface-0)]">
    <!-- Navbar -->
    <nav v-if="authStore.isLoggedIn" class="sticky top-0 z-50 border-b border-[var(--border-light)] bg-[var(--surface-0)]/85 backdrop-blur-md relative">
      <div ref="navRef" class="max-w-5xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2">
        <!-- Left: Brand -->
        <router-link to="/account" class="flex items-center gap-2 no-underline group flex-shrink-0" title="账号管理">
          <div class="w-8 h-8 rounded-lg bg-[var(--ink-primary)] flex items-center justify-center text-white text-sm font-bold group-hover:bg-[var(--accent)] transition-colors">
            三
          </div>
          <span class="font-semibold text-[var(--ink-primary)] hidden sm:inline">三一</span>
        </router-link>

        <!-- Nav tabs: 听课 | 学习 | AI -->
        <div class="flex-1 flex justify-center gap-1">
          <router-link to="/classroom" class="nav-pill" active-class="nav-pill-active">
            <Headphones :size="16" />
            <span class="hidden sm:inline">听课</span>
          </router-link>
          <router-link to="/" class="nav-pill" active-class="nav-pill-active">
            <BookOpen :size="16" />
            <span class="hidden sm:inline">学习</span>
          </router-link>
          <router-link to="/ai" class="nav-pill" active-class="nav-pill-active">
            <Sparkles :size="16" />
            <span class="hidden sm:inline">AI</span>
          </router-link>
        </div>

        <!-- Right: Raw + Theme + Hamburger -->
        <div class="flex items-center gap-0.5 sm:gap-1 flex-shrink-0">
          <button @click="toggleRawMode" class="nav-link text-[var(--ink-muted)]" title="切换原始/渲染模式"
            :class="isRawMode ? '!text-[var(--accent)] !bg-[var(--accent-soft)]' : ''">
            <Code2 :size="16" />
            <span class="hidden sm:inline text-xs">{{ isRawMode ? '源码' : '渲染' }}</span>
          </button>
          <button @click="toggleTheme" class="nav-link text-[var(--ink-muted)]" title="切换主题">
            <Sun v-if="isDark" :size="16" />
            <Moon v-else :size="16" />
          </button>
          <button @click="mobileMenuOpen = !mobileMenuOpen" class="nav-link text-[var(--ink-muted)]" title="菜单">
            <Menu v-if="!mobileMenuOpen" :size="18" />
            <X v-else :size="18" />
          </button>
        </div>
      </div>

      <!-- Dropdown menu -->
      <div v-if="mobileMenuOpen" class="absolute right-3 top-14 w-56 bg-[var(--surface-card)] border border-[var(--border-light)] rounded-lg shadow-lg z-50 animate-scale-in">
        <div class="px-2 py-2 space-y-0.5">
          <router-link to="/collection" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <Star :size="16" /> 好题锦集
          </router-link>
          <router-link to="/vocab" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <BookOpen :size="16" /> 单词
          </router-link>
          <router-link to="/notes" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <FileText :size="16" /> 笔记
          </router-link>
          <router-link to="/vault" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <FolderOpen :size="16" /> 文件
          </router-link>
          <router-link to="/review" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <RefreshCw :size="16" /> 复习
          </router-link>
          <router-link to="/stats" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <BarChart3 :size="16" /> 统计
          </router-link>
          <router-link to="/settings" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <Settings :size="16" /> 设置
          </router-link>
          <router-link v-if="isAdmin" to="/admin" class="mobile-nav-link" active-class="mobile-nav-link-active">
            <Shield :size="16" /> 管理
          </router-link>
          <hr class="border-[var(--border-light)] my-1" />
          <button @click="authStore.logout(); mobileMenuOpen = false" class="mobile-nav-link text-[var(--error)] w-full">
            <LogOut :size="16" /> 退出登录
          </button>
        </div>
      </div>
    </nav>

    <!-- Main content (full width — ChatPanel is now a floating window) -->
    <main class="flex-1">
      <router-view v-slot="{ Component, route }">
        <transition name="page">
          <component :is="Component" :key="route.path" />
        </transition>
      </router-view>
    </main>

    <!-- Footer -->
    <footer v-if="authStore.isLoggedIn" class="py-4 text-center text-xs text-[var(--ink-muted)] border-t border-[var(--border-light)]">
      三一 · 学而时习之
    </footer>

    <!-- Floating AI Window (Teleported) -->
    <ChatPanel />

    <!-- Global Toast -->
    <Toast ref="toastRef" />

    <!-- Selection toolbar (appears when text is selected) -->
    <Teleport to="body">
      <div v-if="selToolbar.visible" class="fixed z-[9998] sel-toolbar" :style="selToolbar.style">
        <div class="flex items-center gap-0.5 px-1.5 py-1 rounded-lg bg-[var(--ink-primary)] text-white shadow-xl text-xs">
          <button @click="selCopy" @touchstart.prevent="selCopy" class="sel-btn" title="复制">
            <Copy :size="14" /><span class="hidden sm:inline ml-1">复制</span>
          </button>
          <button @click="selClip" @touchstart.prevent="selClip" class="sel-btn" title="摘录">
            <Scissors :size="14" /><span class="hidden sm:inline ml-1">摘录</span>
          </button>
          <button @click="selAskAI" @touchstart.prevent="selAskAI" class="sel-btn !text-[var(--accent-indigo-soft)]" title="问AI">
            <Sparkles :size="14" /><span class="hidden sm:inline ml-1">问AI</span>
          </button>
        </div>
      </div>
    </Teleport>

    <!-- Clip mode floating toolbar -->
    <Teleport to="body">
      <div v-if="clipMode" class="fixed top-16 left-1/2 -translate-x-1/2 z-[9999] pointer-events-none">
        <div class="pointer-events-auto flex items-center gap-3 px-5 py-2.5 rounded-full bg-[var(--ink-primary)] text-white text-sm font-medium shadow-2xl animate-slide-down">
          <Scissors :size="16" class="text-[var(--accent-indigo-soft)]" />
          <span class="hidden sm:inline">选中文字和公式</span>
          <span class="sm:hidden">选中内容</span>
          <kbd class="px-1.5 py-0.5 rounded bg-white/20 text-xs font-mono">Enter</kbd>
          <span class="text-white/60">摘录</span>
          <span class="text-white/40">·</span>
          <kbd class="px-1.5 py-0.5 rounded bg-white/20 text-xs font-mono">Esc</kbd>
          <span class="text-white/60">取消</span>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, RefreshCw, LogOut, Settings, Sun, Moon, Shield, Sparkles, Star, BarChart3, Menu, X, FileText, Scissors, Copy, Code2, FolderOpen, Headphones } from 'lucide-vue-next'
import Toast from './components/Toast.vue'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import { isRawMode } from './composables/useKaTeX'
import ChatPanel from './components/chat/ChatPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const chatStore = useChatStore()

const mobileMenuOpen = ref(false)

// ── Global Clip Mode ──
const clipMode = ref(false)
const clipBusy = ref(false)

function toggleClipMode() {
  if (clipMode.value) { exitClipMode(); return }
  // Check if text is already selected → clip immediately
  const sel = window.getSelection()
  if (sel && !sel.isCollapsed && sel.toString().trim()) {
    doClip()
    return
  }
  enterClipMode()
}

function enterClipMode() {
  clipMode.value = true
  document.body.style.cursor = 'text'
  document.addEventListener('keydown', onClipKeydown)
  document.addEventListener('mouseup', onClipMouseup)
}

function exitClipMode() {
  clipMode.value = false
  document.body.style.cursor = ''
  document.removeEventListener('keydown', onClipKeydown)
  document.removeEventListener('mouseup', onClipMouseup)
}

function onClipKeydown(e) {
  if (e.key === 'Escape') { e.preventDefault(); exitClipMode() }
  if (e.key === 'Enter') {
    e.preventDefault()
    const sel = window.getSelection()
    if (sel && !sel.isCollapsed && sel.toString().trim()) {
      doClip().then(() => exitClipMode())
    } else {
      window.__toast?.warning('请先选中要摘录的内容')
    }
  }
}

function onClipMouseup() {
  // Visual feedback: the floating bar already tells them what to do
  // Don't auto-clip on mouseup — user might want to adjust selection
}

async function doClip() {
  if (clipBusy.value) return
  clipBusy.value = true
  try {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      window.__toast?.warning('请先选中要摘录的内容（支持文字和公式），再点击摘录')
      return
    }
    const range = sel.getRangeAt(0).cloneContents()
    const div = document.createElement('div')
    div.appendChild(range)
    const content = div.innerHTML || sel.toString()
    const pageTitle = document.title?.replace('三一 · 学而时习之', '').replace(/^[-\s]+/, '').trim().slice(0, 50) || ''

    const { default: client } = await import('./api/client')
    await client.post('/notes/materials', { content, source_label: pageTitle })
    window.__toast?.success(`已摘录${pageTitle ? '：' + pageTitle : ''}`)
  } catch (e) {
    window.__toast?.error('摘录失败：' + (e.message || '未知错误').slice(0, 60))
    console.error('Clip failed', e)
  } finally {
    clipBusy.value = false
  }
}

// Expose globally so ChatPanel can reuse
if (typeof window !== 'undefined') window.__clipContent = toggleClipMode

// Clean up clip mode on route change
watch(() => router.currentRoute.value.path, () => {
  mobileMenuOpen.value = false
  if (clipMode.value) exitClipMode()
})

// Redirect to login on logout
watch(() => authStore.isLoggedIn, (val) => {
  if (!val && router.currentRoute.value.path !== '/login') {
    router.push('/login')
  }
})

// Dark theme toggle
const isDark = ref(false)
const isAdmin = computed(() => authStore.user?.role === 'admin' || authStore.user?.role === 'superadmin')

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}

// ── Raw mode toggle ──
function toggleRawMode() {
  isRawMode.value = !isRawMode.value
  if (typeof window !== 'undefined') window.__rawMode = isRawMode.value
  localStorage.setItem('rawMode', isRawMode.value ? 'true' : 'false')
}

// ── Selection toolbar ──
const selToolbar = reactive({ visible: false, style: {}, text: '', html: '' })

function updateSelToolbar() {
  try {
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !sel.toString().trim() || clipMode.value) {
      selToolbar.visible = false; return
    }
    const range = sel.getRangeAt(0)
    const rect = range.getBoundingClientRect()
    const isMobileView = window.innerWidth < 640
    // On mobile: position toolbar ABOVE the selection so it's not covered by the finger
    // and center it horizontally. On desktop: position below selection.
    const top = isMobileView
      ? Math.max(10, rect.top - 50)
      : Math.min(rect.bottom + 8, window.innerHeight - 50)
    const left = isMobileView
      ? Math.max(8, Math.min(window.innerWidth - 200, rect.left + (rect.width / 2) - 90))
      : Math.min(rect.right, window.innerWidth - 200)
    selToolbar.style = { top: top + 'px', left: left + 'px' }
    selToolbar.text = sel.toString().trim()
    const clone = range.cloneContents()
    const div = document.createElement('div')
    div.appendChild(clone)
    selToolbar.html = div.innerHTML
    selToolbar.visible = true
  } catch { selToolbar.visible = false }
}

function selCopy() {
  const sel = window.getSelection()
  // Check if selection contains KaTeX rendered formulas
  const hasKatex = sel && sel.rangeCount > 0 && sel.getRangeAt(0).cloneContents().querySelectorAll('.katex').length > 0
  navigator.clipboard.writeText(selToolbar.text).then(() => {
    if (hasKatex) {
      window.__toast?.warning('已复制文字。公式源码需在编辑模式下复制')
    } else {
      window.__toast?.success('已复制')
    }
  }).catch(() => {})
  selToolbar.visible = false
}

function selClip() {
  if (selToolbar.html) {
    const pageTitle = document.title?.replace('三一 · 学而时习之', '').replace(/^[-\s]+/, '').trim().slice(0, 50) || ''
    import('./api/client').then(({ default: client }) => {
      client.post('/notes/materials', { content: selToolbar.html, source_label: pageTitle })
        .then(() => window.__toast?.success('已摘录'))
        .catch(e => window.__toast?.error('摘录失败'))
    })
  }
  selToolbar.visible = false
}

function selAskAI() {
  // Open floating AI window with pre-filled question
  const text = selToolbar.text.replace(/\s+/g, ' ').trim()
  chatStore.open = true
  // Use global askAI to prefill the chat input
  window.__askAI?.('请讲解：' + text)
  selToolbar.visible = false
}

function onSelectionChange() {
  // Don't show toolbar during clip mode
  if (clipMode.value) { selToolbar.visible = false; return }
  updateSelToolbar()
}

function hideSelToolbar(e) {
  // Hide if clicking outside toolbar
  if (!e.target.closest('.sel-toolbar')) {
    selToolbar.visible = false
  }
}

onMounted(async () => {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }
  document.addEventListener('selectionchange', onSelectionChange)
  document.addEventListener('mousedown', hideSelToolbar)
  document.addEventListener('touchstart', hideSelToolbar, { passive: true })
  if (authStore.isLoggedIn && !authStore.user) {
    await authStore.fetchMe()
  }
})
onUnmounted(() => {
  document.removeEventListener('selectionchange', onSelectionChange)
  document.removeEventListener('mousedown', hideSelToolbar)
  document.removeEventListener('touchstart', hideSelToolbar)
  if (clipMode.value) exitClipMode()
})
</script>

<style scoped>
.nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--ink-muted);
  text-decoration: none;
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.nav-pill:hover { color: var(--ink-primary); background: var(--surface-1); }
.nav-pill-active { color: white; background: var(--ink-primary); }
.nav-pill-active:hover { color: white; background: var(--ink-primary); }

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--ink-secondary);
  text-decoration: none;
  transition: all var(--duration-fast) var(--ease-out);
}
.nav-link:hover {
  color: var(--ink-primary);
  background: var(--surface-1);
}
.nav-link-active {
  color: var(--ink-primary);
  background: var(--surface-2);
  font-weight: 500;
}

/* ── Selection toolbar buttons ── */
.sel-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 6px;
  color: rgba(255,255,255,0.85);
  background: none;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}
.sel-btn:hover { background: rgba(255,255,255,0.15); }

/* ── Mobile nav dropdown ── */
.mobile-nav-link {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--ink-secondary);
  text-decoration: none;
  transition: all var(--duration-fast) var(--ease-out);
  width: 100%;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.mobile-nav-link:hover {
  color: var(--ink-primary);
  background: var(--surface-1);
}
.mobile-nav-link-active {
  color: var(--ink-primary);
  background: var(--surface-2);
  font-weight: 500;
}

/* ── Mobile touch target sizing ── */
@media (max-width: 640px) {
  .mobile-nav-link {
    min-height: 44px;
    padding: 0.625rem 0.75rem;
    font-size: var(--text-sm);
  }
  .sel-btn {
    min-width: 44px;
    min-height: 44px;
    justify-content: center;
    padding: 8px 10px;
  }
  .nav-link {
    min-height: 44px;
    padding: 0.5rem 0.625rem;
  }
  .nav-pill {
    min-height: 44px;
    padding: 0.5rem 0.875rem;
  }
  .sel-toolbar > div {
    padding: 0.5rem 0.5rem !important;
    gap: 0.25rem !important;
  }
  .sel-toolbar :deep(.sel-btn svg) {
    width: 16px;
    height: 16px;
  }
}

/* ── Very small screens: compact nav ── */
@media (max-width: 380px) {
  .nav-link {
    padding: 0.25rem 0.5rem !important;
  }
}
</style>

<style>
/* Global clip-mode animation (Teleported to body, outside scoped styles) */
.animate-slide-down {
  animation: clipSlideDown 0.3s ease-out;
}
@keyframes clipSlideDown {
  from { opacity: 0; transform: translate(-50%, -12px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
</style>
