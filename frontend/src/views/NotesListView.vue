<template>
  <div class="max-w-3xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)]">笔记</h1>
      <button @click="createNote" class="btn btn-primary text-sm px-4 py-2">
        <Plus :size="16" /> 新建笔记
      </button>
    </div>

    <div v-if="loading" class="py-20 text-center"><Loader :size="24" class="animate-spin mx-auto" /></div>

    <div v-else-if="notes.length === 0" class="py-20 text-center text-[var(--ink-muted)]">
      <BookOpen :size="40" class="mx-auto mb-3 text-[var(--border)]" />
      <p>还没有笔记，点击上方按钮新建</p>
    </div>

    <div v-else class="space-y-2">
      <div v-for="n in notes" :key="n.id"
        @click="$router.push(`/notes/${n.id}`)"
        class="card card-interactive p-4 flex items-center justify-between">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span v-if="n.is_pinned">📌</span>
            <span class="font-medium text-[var(--ink-primary)] truncate">{{ n.title }}</span>
          </div>
          <p class="text-xs text-[var(--ink-muted)] mt-1">
            {{ formatDate(n.updated_at) }} · {{ (n.content || '').length }} 字
          </p>
        </div>
        <button @click.stop="deleteNote(n.id)" class="btn btn-ghost p-1 text-[var(--ink-muted)] hover:text-[var(--error)]">
          <Trash2 :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Loader, BookOpen, Trash2 } from 'lucide-vue-next'
import client from '../api/client'

const router = useRouter()
const notes = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await client.get('/notes')
    notes.value = res.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
})

async function createNote() {
  try {
    const res = await client.post('/notes', { title: '无标题笔记', content: '' })
    router.push(`/notes/${res.data.id}`)
  } catch (e) { console.error(e) }
}

async function deleteNote(id) {
  if (!confirm('删除此笔记？')) return
  try {
    await client.delete(`/notes/${id}`)
    notes.value = notes.value.filter(n => n.id !== id)
  } catch (e) { console.error(e) }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
}
</script>
