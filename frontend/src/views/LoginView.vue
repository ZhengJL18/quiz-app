<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--surface-0)] px-4">
    <div class="w-full max-w-md animate-fade-in-up">
      <div class="text-center mb-10">
        <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--ink-primary)] items-center justify-center text-white text-2xl font-bold mb-4 shadow-lg">
          三
        </div>
        <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1">三一</h1>
        <p class="text-[var(--ink-muted)] text-sm">学而时习之</p>
      </div>

      <!-- Tab toggle -->
      <div class="flex mb-4 bg-[var(--surface-2)] rounded-lg p-1">
        <button @click="mode = 'login'" class="flex-1 py-2 text-sm font-medium rounded-md transition-colors"
          :class="mode === 'login' ? 'bg-[var(--surface-0)] text-[var(--ink-primary)] shadow-sm' : 'text-[var(--ink-muted)]'">
          登录
        </button>
        <button @click="mode = 'signup'" class="flex-1 py-2 text-sm font-medium rounded-md transition-colors"
          :class="mode === 'signup' ? 'bg-[var(--surface-0)] text-[var(--ink-primary)] shadow-sm' : 'text-[var(--ink-muted)]'">
          注册
        </button>
      </div>

      <!-- Login form -->
      <form v-if="mode === 'login'" @submit.prevent="handleLogin" class="card p-8 space-y-5">
        <div>
          <label for="login-username" class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">用户名</label>
          <input id="login-username" v-model="username" type="text" placeholder="输入用户名" required class="input" autocomplete="username" />
        </div>
        <div>
          <label for="login-password" class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">密码</label>
          <input id="login-password" v-model="password" type="password" placeholder="输入密码" required class="input" autocomplete="current-password" />
        </div>
        <button type="submit" :disabled="loading" class="btn btn-primary w-full py-3 text-base">
          <Loader v-if="loading" :size="18" class="animate-spin" />
          {{ loading ? '登录中...' : '登录' }}
        </button>
        <p v-if="error" class="text-sm text-center text-[var(--error)] bg-[var(--error-soft)] rounded-lg py-2 animate-shake">{{ error }}</p>
      </form>

      <!-- Signup form -->
      <form v-else @submit.prevent="handleSignup" class="card p-8 space-y-5">
        <div>
          <label for="signup-username" class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">用户名</label>
          <input id="signup-username" v-model="signupUsername" type="text" placeholder="设置用户名" required class="input" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">密码</label>
          <input v-model="signupPassword" type="password" placeholder="至少8位" required class="input" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">确认密码</label>
          <input v-model="signupConfirm" type="password" placeholder="再次输入密码" required class="input" />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">
            DeepSeek API Key
            <span class="text-[var(--ink-muted)] font-normal">（必填，用于AI出题和讲义。每人独立密钥，互不影响）</span>
          </label>
          <input v-model="signupApiKey" type="password" placeholder="sk-..." required class="input" />
          <p class="text-xs text-[var(--ink-muted)] mt-1">前往 <a href="https://platform.deepseek.com/api_keys" target="_blank" class="text-[var(--accent-indigo)] underline">platform.deepseek.com</a> 免费获取</p>
        </div>
        <button type="submit" :disabled="loading" class="btn btn-primary w-full py-3 text-base">
          <Loader v-if="loading" :size="18" class="animate-spin" />
          {{ loading ? '注册中...' : '注册' }}
        </button>
        <p class="text-xs text-[var(--ink-muted)] text-center">注册后科目默认为空，可在设置中按需添加或让AI辅助生成</p>
        <p v-if="error" class="text-sm text-center text-[var(--error)] bg-[var(--error-soft)] rounded-lg py-2 animate-shake">{{ error }}</p>
      </form>
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
const mode = ref('login')
const loading = ref(false)
const error = ref('')

// Login
const username = ref('')
const password = ref('')

async function handleLogin() {
  loading.value = true; error.value = ''
  try { await authStore.login(username.value, password.value); router.push('/') }
  catch (e) { error.value = e.response?.data?.detail || '登录失败' }
  finally { loading.value = false }
}

// Signup
const signupUsername = ref('')
const signupPassword = ref('')
const signupConfirm = ref('')
const signupApiKey = ref('')

async function handleSignup() {
  loading.value = true; error.value = ''
  try {
    if (signupPassword.value !== signupConfirm.value) {
      error.value = '两次密码不一致'; loading.value = false; return
    }
    if (signupPassword.value.length < 8) {
      error.value = '密码至少8位'; loading.value = false; return
    }
    await authStore.signup(signupUsername.value, signupPassword.value, signupApiKey.value)
    router.push('/')
  } catch (e) { error.value = e.response?.data?.detail || '注册失败' }
  finally { loading.value = false }
}
</script>
