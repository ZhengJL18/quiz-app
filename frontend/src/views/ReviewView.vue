<template>
  <div class="max-w-2xl mx-auto px-4 py-8 animate-fade-in-up">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center">
          <RefreshCw :size="18" class="text-[var(--accent-indigo)]" />
        </div>
        今日复习
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">基于记忆曲线，科学安排复习</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <!-- Empty -->
    <div v-else-if="items.length === 0" class="py-20 text-center">
      <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--surface-2)] items-center justify-center mb-4">
        <CheckCircle :size="28" class="text-[var(--success)]" />
      </div>
      <p class="text-lg font-medium text-[var(--ink-primary)] mb-1">今日无复习任务</p>
      <p class="text-sm text-[var(--ink-muted)]">系统会根据记忆曲线自动安排复习</p>
    </div>

    <!-- Review card -->
    <div v-else class="space-y-6">
      <!-- Progress -->
      <div class="flex items-center gap-3">
        <div class="flex-1 h-1.5 bg-[var(--border-light)] rounded-full overflow-hidden">
          <div
            class="h-full bg-[var(--accent-indigo)] rounded-full transition-all duration-500 ease-out"
            :style="{ width: `${(currentIdx / items.length) * 100}%` }"
          />
        </div>
        <span class="text-xs font-medium text-[var(--ink-muted)] tabular-nums">
          {{ currentIdx }}/{{ items.length }}
        </span>
      </div>

      <!-- Done -->
      <div v-if="!currentItem" class="py-16 text-center animate-scale-in">
        <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--success-soft)] items-center justify-center mb-4">
          <CheckCircle :size="28" class="text-[var(--success)]" />
        </div>
        <p class="text-lg font-medium text-[var(--ink-primary)]">复习完成!</p>
        <router-link to="/" class="btn btn-primary mt-6 px-8 no-underline inline-flex">
          <Home :size="16" /> 返回首页
        </router-link>
      </div>

      <!-- Flashcard -->
      <div v-else class="card p-6 sm:p-8 animate-scale-in">
        <!-- Question -->
        <div class="text-lg leading-relaxed mb-8 text-[var(--ink-primary)]"
             v-html="renderedQuestion" />

        <div class="border-t border-[var(--border-light)] pt-6">
          <p class="text-sm font-medium text-[var(--ink-secondary)] mb-4 text-center">你的记忆程度如何?</p>
          <div class="flex gap-3">
            <button @click="submitReview(0)"
              class="flex-1 py-3 rounded-lg border-2 border-[var(--error)] text-[var(--error)] font-medium
                     hover:bg-[var(--error-soft)] transition-colors text-sm">
              完全忘记
            </button>
            <button @click="submitReview(3)"
              class="flex-1 py-3 rounded-lg border-2 border-[var(--warning)] text-[var(--warning)] font-medium
                     hover:bg-[var(--warning-soft)] transition-colors text-sm">
              部分想起
            </button>
            <button @click="submitReview(5)"
              class="flex-1 py-3 rounded-lg border-2 border-[var(--success)] text-[var(--success)] font-medium
                     hover:bg-[var(--success-soft)] transition-colors text-sm">
              完全记住
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RefreshCw, Loader, CheckCircle, Home } from 'lucide-vue-next'
import client from '../api/client'
import { renderLatex } from '../composables/useKaTeX'

const items = ref([])
const currentIdx = ref(0)
const loading = ref(true)

const currentItem = computed(() => {
  if (currentIdx.value < items.value.length) return items.value[currentIdx.value]
  return null
})

const renderedQuestion = computed(() => {
  if (!currentItem.value?.question) return ''
  try {
    const c = JSON.parse(currentItem.value.question.content_json)
    return renderLatex(c.question_text || '')
  } catch { return '' }
})

async function submitReview(quality) {
  if (!currentItem.value) return
  try {
    await client.post('/srs/review', {
      wrong_book_id: currentItem.value.wrong_book_id,
      quality,
    })
    currentIdx.value++
  } catch (e) {
    console.error('Review submission failed', e)
  }
}

onMounted(async () => {
  try {
    const res = await client.get('/srs/review-today')
    items.value = res.data
  } catch (e) {
    console.error('Failed to load reviews', e)
  } finally {
    loading.value = false
  }
})
</script>
