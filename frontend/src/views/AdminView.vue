<template>
  <div class="max-w-5xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center">
          <Shield :size="18" class="text-[var(--accent-indigo)]" />
        </div> 管理看板
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">超级管理员 · 全站数据与文件管理</p>
    </div>

    <!-- Tab switcher -->
    <div class="flex gap-1 mb-6">
      <button @click="tab = 'dashboard'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="tab === 'dashboard' ? 'bg-[var(--ink-primary)] text-white' : 'text-[var(--ink-muted)] hover:bg-[var(--surface-1)]'">
        📊 数据概览
      </button>
      <button @click="tab = 'files'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="tab === 'files' ? 'bg-[var(--ink-primary)] text-white' : 'text-[var(--ink-muted)] hover:bg-[var(--surface-1)]'">
        📁 文件管理
      </button>
    </div>

    <!-- Tab: Dashboard -->
    <template v-if="tab === 'dashboard'">
      <div v-if="loading" class="py-20 text-center">
        <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
      </div>

      <template v-else-if="data">
        <!-- Totals -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <div v-for="stat in totalsCards" :key="stat.label" class="card p-4 text-center">
            <div class="text-2xl font-bold" :class="stat.color">{{ stat.value }}</div>
            <div class="text-xs text-[var(--ink-muted)] mt-1">{{ stat.label }}</div>
          </div>
        </div>

        <!-- User table -->
        <div class="card overflow-hidden">
          <div class="px-5 py-4 border-b border-[var(--border-light)]">
            <h2 class="font-semibold text-[var(--ink-primary)]">用户列表</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-[var(--border-light)] text-left text-xs text-[var(--ink-muted)] uppercase tracking-wide">
                  <th class="px-5 py-3 font-medium">用户</th>
                  <th class="px-5 py-3 font-medium">角色</th>
                  <th class="px-5 py-3 font-medium">科目</th>
                  <th class="px-5 py-3 font-medium">题目</th>
                  <th class="px-5 py-3 font-medium">练习</th>
                  <th class="px-5 py-3 font-medium">错题</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="u in data.users" :key="u.id" @click="$router.push(`/admin/user/${u.id}`)"
                  class="border-b border-[var(--border-light)]/50 hover:bg-[var(--surface-1)] transition-colors cursor-pointer">
                  <td class="px-5 py-3">
                    <span class="font-medium text-[var(--ink-primary)]">{{ u.username }}</span>
                  </td>
                  <td class="px-5 py-3">
                    <span class="badge" :class="roleClass(u.role)">{{ roleLabel(u.role) }}</span>
                  </td>
                  <td class="px-5 py-3 text-[var(--ink-secondary)]">{{ u.subjects }}</td>
                  <td class="px-5 py-3 text-[var(--ink-secondary)]">{{ u.questions }}</td>
                  <td class="px-5 py-3 text-[var(--ink-secondary)]">{{ u.sessions }}</td>
                  <td class="px-5 py-3 text-[var(--ink-secondary)]">{{ u.wrong_entries }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>

    <!-- Tab: File Manager -->
    <template v-else-if="tab === 'files'">
      <VaultBrowser />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Shield, Loader } from 'lucide-vue-next'
import VaultBrowser from '../components/admin/VaultBrowser.vue'
import client from '../api/client'

const tab = ref('dashboard')
const data = ref(null)
const loading = ref(true)

const totalsCards = computed(() => {
  if (!data.value) return []
  const t = data.value.totals
  return [
    { label: '用户', value: t.users, color: 'text-[var(--ink-primary)]' },
    { label: '科目', value: t.subjects, color: 'text-[var(--accent)]' },
    { label: '题目', value: t.questions, color: 'text-[var(--accent-indigo)]' },
    { label: '练习', value: t.sessions, color: 'text-[var(--success)]' },
    { label: '错题', value: t.wrong_entries, color: 'text-[var(--error)]' },
    { label: '单词', value: t.vocab_cards, color: 'text-[var(--warning)]' },
  ]
})

function roleLabel(r) { return { superadmin: '超级管理员', admin: '管理员', user: '用户' }[r] || r }
function roleClass(r) {
  return {
    superadmin: 'bg-[var(--ink-primary)] text-white',
    admin: 'bg-[var(--accent-indigo-soft)] text-[var(--accent-indigo)]',
    user: 'bg-[var(--surface-2)] text-[var(--ink-muted)]',
  }[r] || ''
}

onMounted(async () => {
  try { const res = await client.get('/admin/dashboard'); data.value = res.data }
  catch { /* not admin */ }
  finally { loading.value = false }
})
</script>
