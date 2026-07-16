<template>
  <div class="min-h-screen flex flex-col bg-[var(--surface-0)]">
    <!-- Navbar -->
    <nav v-if="authStore.isLoggedIn" class="sticky top-0 z-50 border-b border-[var(--border-light)] bg-white/85 backdrop-blur-md">
      <div class="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <!-- Left: Brand + Nav -->
        <div class="flex items-center gap-1">
          <router-link to="/" class="flex items-center gap-2 mr-4 no-underline group">
            <div class="w-8 h-8 rounded-lg bg-[var(--ink-primary)] flex items-center justify-center text-white text-sm font-bold group-hover:bg-[var(--accent)] transition-colors">
              学
            </div>
            <span class="font-semibold text-[var(--ink-primary)] hidden sm:inline">一课一练</span>
          </router-link>

          <router-link to="/" class="nav-link" active-class="nav-link-active">
            <BookOpen :size="16" />
            <span class="hidden sm:inline">学习</span>
          </router-link>
          <router-link to="/wrong-book" class="nav-link" active-class="nav-link-active">
            <AlertCircle :size="16" />
            <span class="hidden sm:inline">错题</span>
          </router-link>
          <router-link to="/review" class="nav-link" active-class="nav-link-active">
            <RefreshCw :size="16" />
            <span class="hidden sm:inline">复习</span>
          </router-link>
        </div>

        <!-- Right: User -->
        <button @click="authStore.logout" class="nav-link text-[var(--ink-muted)] hover:text-[var(--error)]">
          <LogOut :size="16" />
          <span class="hidden sm:inline">退出</span>
        </button>
      </div>
    </nav>

    <!-- Main -->
    <main class="flex-1">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- Footer -->
    <footer v-if="authStore.isLoggedIn" class="py-4 text-center text-xs text-[var(--ink-muted)] border-t border-[var(--border-light)]">
      一课一练 · 刻意练习，步步为营
    </footer>
  </div>
</template>

<script setup>
import { BookOpen, AlertCircle, RefreshCw, LogOut } from 'lucide-vue-next'
import { useAuthStore } from './stores/auth'
const authStore = useAuthStore()
</script>

<style scoped>
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

/* Page transitions */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
