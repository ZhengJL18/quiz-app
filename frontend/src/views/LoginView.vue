<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--surface-0)] px-4">
    <div class="w-full max-w-md animate-fade-in-up">
      <!-- Brand -->
      <div class="text-center mb-10">
        <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--ink-primary)] items-center justify-center text-white text-2xl font-bold mb-4 shadow-lg">
          学
        </div>
        <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1">一课一练</h1>
        <p class="text-[var(--ink-muted)] text-sm">刻意练习，步步为营</p>
      </div>

      <!-- Card -->
      <div class="card p-8">
        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">用户名</label>
            <input
              v-model="username"
              type="text"
              placeholder="输入用户名"
              required
              class="input"
              autocomplete="username"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">密码</label>
            <input
              v-model="password"
              type="password"
              placeholder="输入密码"
              required
              class="input"
              autocomplete="current-password"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="btn btn-primary w-full py-3 text-base"
          >
            <Loader v-if="loading" :size="18" class="animate-spin" />
            {{ loading ? '登录中...' : '登录' }}
          </button>

          <p v-if="error" class="text-sm text-center text-[var(--error)] bg-[var(--error-soft)] rounded-lg py-2 animate-shake">
            {{ error }}
          </p>
        </form>
      </div>

      <p class="text-center mt-6 text-xs text-[var(--ink-muted)]">
        默认账户 admin / admin123
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { Loader } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>
