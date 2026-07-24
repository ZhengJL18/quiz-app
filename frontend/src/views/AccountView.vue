<template>
  <div class="max-w-lg mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--ink-primary)] flex items-center justify-center text-white text-sm font-bold">三</div>
        账号管理
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">{{ user?.role === 'superadmin' ? '超级管理员' : user?.role === 'admin' ? '管理员' : '普通用户' }}</p>
    </div>

    <div class="card p-6 space-y-5">
      <!-- Username -->
      <div>
        <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">用户名</label>
        <div class="flex gap-2">
          <input v-model="form.username" type="text" class="input text-sm flex-1" :placeholder="user?.username" />
          <button @click="saveField('username')" :disabled="saving || !form.username || form.username === user?.username"
            class="btn btn-primary text-xs py-1.5 px-3 flex-shrink-0">保存</button>
        </div>
      </div>

      <!-- Password -->
      <div>
        <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">修改密码</label>
        <div class="space-y-2">
          <input v-model="form.old_password" type="password" class="input text-sm w-full" placeholder="当前密码" />
          <div class="flex gap-2">
            <input v-model="form.password" type="password" class="input text-sm flex-1" placeholder="新密码（至少8位）" />
            <button @click="saveField('password')" :disabled="saving || !form.old_password || !form.password || form.password.length < 8"
              class="btn btn-primary text-xs py-1.5 px-3 flex-shrink-0">修改</button>
          </div>
        </div>
        <p v-if="form.password && form.password.length < 8" class="text-xs text-[var(--error)] mt-1">至少8位</p>
      </div>

      <!-- API Key -->
      <div>
        <label class="block text-sm font-medium text-[var(--ink-secondary)] mb-1.5">
          DeepSeek API Key
          <span class="text-[var(--ink-muted)] font-normal text-xs">（你的个人密钥，优先级高于全局配置）</span>
        </label>
        <div class="flex gap-2">
          <input v-model="form.api_key" type="password" class="input text-sm flex-1"
            :placeholder="user?.api_key ? '已设置 (' + user.api_key.substring(0, 8) + '...)' : '未设置，使用全局配置'" />
          <button @click="saveField('api_key')" :disabled="saving || form.api_key === (user?.api_key || '')"
            class="btn btn-primary text-xs py-1.5 px-3 flex-shrink-0">保存</button>
        </div>
        <button v-if="user?.api_key" @click="clearApiKey" :disabled="saving"
          class="text-xs text-[var(--error)] hover:underline mt-1">清除密钥，恢复使用全局配置</button>
      </div>

      <!-- Feedback -->
      <p v-if="successMsg" class="text-sm text-center text-[var(--success)] bg-[var(--success-soft)] rounded-lg py-2">{{ successMsg }}</p>
      <p v-if="errorMsg" class="text-sm text-center text-[var(--error)] bg-[var(--error-soft)] rounded-lg py-2">{{ errorMsg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import client from '../api/client'

const authStore = useAuthStore()
const user = computed(() => authStore.user)
const saving = ref(false)
const successMsg = ref('')
const errorMsg = ref('')

const form = reactive({ username: '', old_password: '', password: '', api_key: '' })

onMounted(async () => {
  await authStore.fetchMe()
  form.username = authStore.user?.username || ''
  form.api_key = authStore.user?.api_key || ''
})

async function saveField(field) {
  saving.value = true; successMsg.value = ''; errorMsg.value = ''
  try {
    const body = {}
    if (field === 'username') body.username = form.username
    if (field === 'password') { body.old_password = form.old_password; body.password = form.password }
    if (field === 'api_key') body.api_key = form.api_key
    const res = await client.put('/auth/me', body)
    authStore.user = res.data
    if (field === 'password') { form.old_password = ''; form.password = '' }
    successMsg.value = { username: '用户名已更新', password: '密码已修改', api_key: 'API Key 已更新' }[field]
    setTimeout(() => successMsg.value = '', 3000)
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || '修改失败'
  } finally { saving.value = false }
}

async function clearApiKey() {
  saving.value = true
  try {
    const res = await client.put('/auth/me', { api_key: '' })
    authStore.user = res.data
    form.api_key = ''
    successMsg.value = '已恢复使用全局 API 配置'
    setTimeout(() => successMsg.value = '', 3000)
  } catch (e) { errorMsg.value = '操作失败' }
  finally { saving.value = false }
}
</script>
