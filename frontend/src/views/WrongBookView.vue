<template>
  <div class="max-w-3xl mx-auto px-4 py-8 animate-fade-in-up">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--error-soft)] flex items-center justify-center">
          <AlertCircle :size="18" class="text-[var(--error)]" />
        </div>
        错题本
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">练习中答错的题目会自动收录</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0" class="py-20 text-center">
      <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--surface-2)] items-center justify-center mb-4">
        <BookOpen :size="28" class="text-[var(--ink-muted)]" />
      </div>
      <p class="text-lg font-medium text-[var(--ink-primary)] mb-1">错题本为空</p>
      <p class="text-sm text-[var(--ink-muted)]">很棒！目前没有错题记录</p>
    </div>

    <!-- List -->
    <div v-else class="space-y-3 stagger">
      <!-- Summary -->
      <div class="card p-4 flex items-center gap-4 mb-4">
        <div class="flex-1 text-center">
          <div class="text-xl font-bold text-[var(--error)]">{{ items.length }}</div>
          <div class="text-xs text-[var(--ink-muted)]">错题总数</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <div class="flex-1 text-center">
          <div class="text-xl font-bold text-[var(--warning)]">{{ notMasteredCount }}</div>
          <div class="text-xs text-[var(--ink-muted)]">未掌握</div>
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

            <!-- Question type -->
            <p v-if="item.question" class="text-xs text-[var(--ink-muted)] uppercase tracking-wide mb-2">
              {{ item.question.question_type }}
            </p>

            <!-- Explanation -->
            <div v-if="item.ai_explanation" class="mt-3 p-3 bg-[var(--surface-1)] rounded-lg text-sm leading-relaxed text-[var(--ink-secondary)]"
                 v-html="renderedExplanation(item)" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { AlertCircle, BookOpen, Loader } from 'lucide-vue-next'
import client from '../api/client'
import { renderMarkdown } from '../composables/useKaTeX'

const items = ref([])
const loading = ref(true)

const notMasteredCount = computed(() => items.value.filter(i => i.mastery_status === 'not_mastered').length)
const masteredCount = computed(() => items.value.filter(i => i.mastery_status === 'mastered').length)

const statusLabel = (s) => ({ not_mastered: '未掌握', reviewing: '复习中', mastered: '已掌握' }[s] || s)
const statusClass = (s) => ({
  not_mastered: 'bg-[var(--error-soft)] text-[var(--error)]',
  reviewing: 'bg-[var(--warning-soft)] text-[var(--warning)]',
  mastered: 'bg-[var(--success-soft)] text-[var(--success)]',
}[s] || 'bg-gray-100 text-gray-600')

function renderedExplanation(item) {
  return renderMarkdown(item.ai_explanation || '')
}

onMounted(async () => {
  try {
    const res = await client.get('/wrong-book')
    items.value = res.data
  } catch (e) {
    console.error('Failed to load wrong book', e)
  } finally {
    loading.value = false
  }
})
</script>
