<template>
  <div class="max-w-3xl mx-auto px-4 py-8 animate-fade-in-up">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center">
          <Star :size="18" class="text-[var(--accent)]" />
        </div>
        好题锦集
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">收藏的好题 · 做错的经典题 · 值得反复练习</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0" class="py-20 text-center">
      <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--surface-2)] items-center justify-center mb-4">
        <Star :size="28" class="text-[var(--ink-muted)]" />
      </div>
      <p class="text-lg font-medium text-[var(--ink-primary)] mb-1">好题锦集为空</p>
      <p class="text-sm text-[var(--ink-muted)]">做错的或喜欢的好题，点一下 ⭐ 收藏就来啦</p>
    </div>

    <!-- List -->
    <div v-else class="space-y-3 stagger">
      <!-- Summary -->
      <div class="card p-4 flex items-center gap-4 mb-4">
        <div class="flex-1 text-center">
          <div class="text-xl font-bold text-[var(--accent)]">{{ items.length }}</div>
          <div class="text-xs text-[var(--ink-muted)]">好题总数</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <div class="flex-1 text-center">
          <div class="text-xl font-bold text-[var(--warning)]">{{ notMasteredCount }}</div>
          <div class="text-xs text-[var(--ink-muted)]">待复习</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <div class="flex-1 text-center">
          <div class="text-xl font-bold text-[var(--success)]">{{ masteredCount }}</div>
          <div class="text-xs text-[var(--ink-muted)]">已掌握</div>
        </div>
      </div>

      <!-- Items -->
      <div v-for="item in items" :key="item.id" class="card p-5">
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <!-- Status + wrong count -->
            <div class="flex items-center gap-2 mb-2">
              <span class="badge" :class="statusClass(item.mastery_status)">
                {{ statusLabel(item.mastery_status) }}
              </span>
              <span class="text-xs text-[var(--ink-muted)]">
                错误 {{ item.wrong_count }} 次
              </span>
            </div>

            <!-- Question preview -->
            <p v-if="item.question" class="text-sm text-[var(--ink-primary)] font-medium mb-1 line-clamp-2"
               v-html="renderedQuestion(item)" />
            <p v-if="item.question" class="text-xs text-[var(--ink-muted)] uppercase tracking-wide mb-2">
              {{ item.question.question_type }}
            </p>

            <!-- Explanation -->
            <div v-if="item.ai_explanation" class="mt-3 p-3 bg-[var(--surface-1)] rounded-lg text-sm leading-relaxed text-[var(--ink-secondary)]"
                 v-html="renderedExplanation(item)" />

            <!-- Inline editor (shown when editing) -->
            <div v-if="editingId === item.id" class="mt-3 space-y-3">
              <div>
                <label class="text-xs font-medium text-[var(--ink-secondary)] mb-1 block">AI 解析</label>
                <textarea
                  v-model="editForm.ai_explanation"
                  rows="4"
                  class="input text-sm resize-y"
                  placeholder="编辑 AI 生成的解析..."
                />
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--ink-secondary)] mb-1 block">个人笔记</label>
                <textarea
                  v-model="editForm.user_note"
                  rows="2"
                  class="input text-sm resize-y"
                  placeholder="添加你的笔记..."
                />
              </div>
              <div class="flex gap-2">
                <button @click="saveEdit(item.id)" :disabled="savingEdit"
                  class="btn btn-primary text-xs py-1.5 px-3">
                  {{ savingEdit ? '保存中...' : '保存' }}
                </button>
                <button @click="cancelEdit" class="btn btn-ghost text-xs py-1.5 px-3">
                  取消
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center gap-2 mt-4 pt-3 border-t border-[var(--border-light)]">
          <button
            @click="generateSimilar(item)"
            :disabled="generatingId === item.id"
            class="btn btn-outline text-xs py-1.5 px-3 gap-1.5"
          >
            <Sparkles :size="13" />
            {{ generatingId === item.id ? '生成中...' : '相似题再练' }}
          </button>
          <button
            @click="regenerateExplanation(item)"
            :disabled="regeneratingId === item.id"
            class="btn btn-ghost text-xs py-1.5 px-3 gap-1.5"
          >
            <RefreshCw :size="13" :class="{ 'animate-spin': regeneratingId === item.id }" />
            {{ regeneratingId === item.id ? '生成中...' : '换个讲解' }}
          </button>
          <button
            v-if="editingId !== item.id"
            @click="startEdit(item)"
            class="btn btn-ghost text-xs py-1.5 px-3 gap-1.5"
          >
            <Pencil :size="13" />
            编辑
          </button>

          <!-- Spacer -->
          <div class="flex-1" />

          <!-- Delete -->
          <button
            @click="deleteEntry(item)"
            :disabled="deletingId === item.id"
            class="btn btn-ghost text-xs py-1.5 px-3 text-[var(--ink-muted)] hover:text-[var(--error)]"
          >
            <Trash2 :size="13" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle, BookOpen, Loader, RefreshCw,
  Sparkles, Pencil, Trash2, Star
} from 'lucide-vue-next'
import client from '../api/client'
import { renderMarkdown } from '../composables/useKaTeX'

const router = useRouter()
const items = ref([])
const loading = ref(true)

// Action states
const generatingId = ref(null)
const regeneratingId = ref(null)
const deletingId = ref(null)
const editingId = ref(null)
const savingEdit = ref(false)
const editForm = ref({ ai_explanation: '', user_note: '' })

// Computed
const notMasteredCount = computed(() => items.value.filter(i => i.mastery_status === 'not_mastered').length)
const masteredCount = computed(() => items.value.filter(i => i.mastery_status === 'mastered').length)

const statusLabel = (s) => ({ not_mastered: '未掌握', reviewing: '复习中', mastered: '已掌握' }[s] || s)
const statusClass = (s) => ({
  not_mastered: 'bg-[var(--error-soft)] text-[var(--error)]',
  reviewing: 'bg-[var(--warning-soft)] text-[var(--warning)]',
  mastered: 'bg-[var(--success-soft)] text-[var(--success)]',
}[s] || 'bg-gray-100 text-gray-600')

function renderedQuestion(item) {
  if (!item.question) return ''
  try {
    const raw = item.question.content_json
    const c = typeof raw === 'string' ? JSON.parse(raw) : raw
    return renderMarkdown(c.question_text || '')
  } catch { return '' }
}

function renderedExplanation(item) {
  return renderMarkdown(item.ai_explanation || '')
}

// ── Actions ──

async function generateSimilar(item) {
  generatingId.value = item.id
  try {
    const res = await client.post(`/wrong-book/${item.id}/similar`)
    const newQuestion = res.data
    // Create a quick session with exactly the generated question
    const sessionRes = await client.post('/practice/pure', {
      subject_id: newQuestion.subject_id,
      question_ids: [newQuestion.id],
    })
    router.push(`/practice/${sessionRes.data.session_id}`)
  } catch (e) {
    console.error('Failed to generate similar question', e)
    alert('生成相似题失败，请稍后重试')
  } finally {
    generatingId.value = null
  }
}

async function regenerateExplanation(item) {
  regeneratingId.value = item.id
  const token = localStorage.getItem('token')
  const idx = items.value.findIndex(i => i.id === item.id)

  // Show immediate streaming placeholder
  if (idx >= 0) {
    items.value[idx] = { ...items.value[idx], ai_explanation: '' }
  }

  try {
    const resp = await fetch(`http://43.139.179.58/api/v1/wrong-book/${item.id}/explanation-stream`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let full = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.chunk) {
              full += data.chunk
              if (idx >= 0) items.value[idx] = { ...items.value[idx], ai_explanation: full }
            } else if (data.done || data.error) {
              if (data.error) {
                full = '> ❌ ' + data.error
                if (idx >= 0) items.value[idx] = { ...items.value[idx], ai_explanation: full }
              }
            }
          } catch { /* skip */ }
        }
      }
    }
  } catch (e) {
    console.error('Stream failed', e)
    if (idx >= 0) items.value[idx] = { ...items.value[idx], ai_explanation: '> ❌ 流式生成失败，请重试' }
  } finally {
    regeneratingId.value = null
  }
}

function startEdit(item) {
  editingId.value = item.id
  editForm.value = {
    ai_explanation: item.ai_explanation || '',
    user_note: item.user_note || '',
  }
}

function cancelEdit() {
  editingId.value = null
  editForm.value = { ai_explanation: '', user_note: '' }
}

async function saveEdit(wrongBookId) {
  savingEdit.value = true
  try {
    const res = await client.put(`/wrong-book/${wrongBookId}`, {
      ai_explanation: editForm.value.ai_explanation,
      user_note: editForm.value.user_note,
    })
    const idx = items.value.findIndex(i => i.id === wrongBookId)
    if (idx >= 0) items.value[idx] = res.data
    cancelEdit()
  } catch (e) {
    console.error('Failed to save edit', e)
    alert('保存失败，请稍后重试')
  } finally {
    savingEdit.value = false
  }
}

async function deleteEntry(item) {
  if (!confirm(`确定删除这道错题记录吗？题目本身不会被删除。`)) return
  deletingId.value = item.id
  try {
    await client.delete(`/wrong-book/${item.id}`)
    items.value = items.value.filter(i => i.id !== item.id)
  } catch (e) {
    console.error('Failed to delete', e)
    alert('删除失败，请稍后重试')
  } finally {
    deletingId.value = null
  }
}

// ── Init ──
async function loadItems() {
  loading.value = true
  try {
    const res = await client.get('/wrong-book')
    items.value = res.data
  } catch (e) {
    console.error('Failed to load wrong book', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadItems)
</script>
