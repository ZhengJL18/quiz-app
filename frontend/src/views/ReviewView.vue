<template>
  <div class="max-w-2xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center">
          <RefreshCw :size="18" class="text-[var(--accent-indigo)]" />
        </div>
        今日复习
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">先回忆，再看答案 — 科学记忆</p>
    </div>

    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <div v-else-if="items.length === 0" class="py-20 text-center">
      <div class="inline-flex w-16 h-16 rounded-2xl bg-[var(--surface-2)] items-center justify-center mb-4">
        <CheckCircle :size="28" class="text-[var(--success)]" />
      </div>
      <p class="text-lg font-medium text-[var(--ink-primary)] mb-1">今日无复习任务</p>
      <p class="text-sm text-[var(--ink-muted)]">系统会根据记忆曲线自动安排复习</p>
    </div>

    <div v-else class="space-y-6">
      <div class="flex items-center gap-3">
        <div class="flex-1 h-1.5 bg-[var(--border-light)] rounded-full overflow-hidden">
          <div class="h-full bg-[var(--accent-indigo)] rounded-full transition-all duration-500"
               :style="{ width: `${(currentIdx / items.length) * 100}%` }" />
        </div>
        <span class="text-xs font-medium text-[var(--ink-muted)] tabular-nums">{{ currentIdx }}/{{ items.length }}</span>
      </div>

      <div v-if="!currentItem" class="py-16 text-center animate-scale-in">
        <CheckCircle :size="48" class="mx-auto text-[var(--success)] mb-4" />
        <p class="text-lg font-medium text-[var(--ink-primary)]">复习完成!</p>
        <router-link to="/" class="btn btn-primary mt-6 px-8 no-underline inline-flex">
          <Home :size="16" /> 返回首页
        </router-link>
      </div>

      <!-- ====== FLASHCARD ====== -->
      <div v-else class="review-card card p-6 sm:p-8 animate-scale-in">

        <!-- ═══ PHASE 1: Question only ═══ -->
        <div v-if="!revealed">
          <!-- Question text -->
          <div class="text-lg leading-relaxed mb-6 text-[var(--ink-primary)]"
               v-html="renderedQuestion" />

          <!-- SINGLE CHOICE -->
          <template v-if="qType === 'single_choice'">
            <p class="text-xs text-[var(--ink-muted)] mb-2">选择你的答案：</p>
            <div class="space-y-2 mb-6">
              <button v-for="(opt, key) in renderedOptions" :key="key"
                @click="userChoice = key"
                class="w-full text-left px-4 py-3 rounded-lg border transition-all duration-200 text-sm"
                :class="userChoice === key
                  ? 'border-[var(--ink-primary)] bg-[var(--surface-1)] font-medium'
                  : 'border-[var(--border-light)] hover:border-[var(--ink-muted)]'">
                <span class="font-medium mr-2 text-[var(--ink-muted)]">{{ key }}.</span><span v-html="opt" />
              </button>
            </div>
          </template>

          <!-- MULTIPLE CHOICE -->
          <template v-else-if="qType === 'multiple_choice'">
            <p class="text-xs text-[var(--ink-muted)] mb-2">选择所有你认为正确的答案：</p>
            <div class="space-y-2 mb-2">
              <button v-for="(opt, key) in renderedOptions" :key="key"
                @click="toggleChoice(key)"
                class="w-full text-left px-4 py-3 rounded-lg border transition-all duration-200 text-sm flex items-center gap-3"
                :class="userChoices.has(key)
                  ? 'border-[var(--ink-primary)] bg-[var(--surface-1)] font-medium'
                  : 'border-[var(--border-light)] hover:border-[var(--ink-muted)]'">
                <span class="w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0"
                  :class="userChoices.has(key)
                    ? 'border-[var(--ink-primary)] bg-[var(--ink-primary)] text-white'
                    : 'border-[var(--border)]'">
                  <Check v-if="userChoices.has(key)" :size="12" />
                </span>
                <span class="font-medium mr-2 text-[var(--ink-muted)]">{{ key }}.</span><span v-html="opt" />
              </button>
            </div>
            <p class="text-xs text-[var(--ink-muted)] mb-6">已选 {{ userChoices.size }} 个</p>
          </template>

          <!-- FILL BLANK -->
          <template v-else-if="qType === 'fill_blank'">
            <input v-model="userAnswer" type="text" placeholder="输入你的答案..."
              class="input text-base mb-6" @keydown.enter="revealAnswer" />
          </template>

          <!-- SHORT ANSWER / CALCULATION -->
          <template v-else>
            <p class="text-xs text-[var(--ink-muted)] mb-2">在脑中回忆答案，或写下要点：</p>
            <textarea v-model="userAnswer" rows="3" placeholder="写下你的答案（可选，用于自评对比）..."
              class="input resize-y text-sm mb-6" />
          </template>

          <button @click="revealAnswer"
            class="btn btn-primary w-full py-3 text-base font-medium">
            <Eye :size="18" />
            查看答案
          </button>
        </div>

        <!-- ═══ PHASE 2: Answer revealed + rating ═══ -->
        <div v-else class="animate-scale-in">
          <!-- Question recap -->
          <div class="text-sm font-medium text-[var(--ink-secondary)] mb-3 pb-3 border-b border-[var(--border-light)]"
               v-html="renderedQuestionCompact" />

          <!-- SINGLE CHOICE: option-by-option comparison -->
          <template v-if="qType === 'single_choice'">
            <div class="space-y-1.5 mb-6">
              <div v-for="(opt, key) in renderedOptions" :key="key"
                class="text-sm py-2 px-3 rounded flex items-center gap-2"
                :class="choiceResultClass(key)">
                <Check v-if="correctSet.has(key)" :size="14" class="text-[var(--success)]" />
                <X v-else-if="userChoice === key" :size="14" class="text-[var(--error)]" />
                <span v-else class="w-3.5" />
                <span class="font-medium mr-1 text-[var(--ink-muted)]">{{ key }}.</span><span v-html="opt" />
              </div>
            </div>
          </template>

          <!-- MULTIPLE CHOICE: checkmark per option -->
          <template v-else-if="qType === 'multiple_choice'">
            <div class="space-y-1.5 mb-6">
              <div v-for="(opt, key) in renderedOptions" :key="key"
                class="text-sm py-2 px-3 rounded flex items-center gap-2"
                :class="choiceResultClass(key)">
                <Check v-if="correctSet.has(key)" :size="14" class="text-[var(--success)]" />
                <X v-else-if="userChoices.has(key)" :size="14" class="text-[var(--error)]" />
                <span v-else class="w-3.5" />
                <span class="font-medium mr-1 text-[var(--ink-muted)]">{{ key }}.</span><span v-html="opt" />
              </div>
            </div>
          </template>

          <!-- FILL BLANK: side-by-side -->
          <template v-else-if="qType === 'fill_blank'">
            <div class="mb-6 space-y-2">
              <div class="flex items-center gap-2 text-sm">
                <span class="text-[var(--ink-muted)]">你的答案：</span>
                <span :class="isUserCorrect ? 'text-[var(--success)] font-medium' : 'text-[var(--error)]'">
                  {{ userAnswer || '(未填写)' }}
                </span>
                <Check v-if="isUserCorrect" :size="16" class="text-[var(--success)]" />
                <X v-else :size="16" class="text-[var(--error)]" />
              </div>
              <div class="text-sm">
                <span class="text-[var(--ink-muted)]">正确答案：</span>
                <span class="text-[var(--success)] font-medium" v-html="renderedCorrectDisplay" />
              </div>
            </div>
          </template>

          <!-- SHORT ANSWER: reference only -->
          <template v-else>
            <div class="mb-6 space-y-3">
              <div v-if="userAnswer" class="p-3 bg-[var(--surface-1)] rounded-lg text-sm text-[var(--ink-secondary)]">
                <span class="text-xs text-[var(--ink-muted)] block mb-1">你的回答：</span>
                {{ userAnswer }}
              </div>
              <div v-if="correctDisplay" class="p-3 bg-[var(--success-soft)] rounded-lg text-sm">
                <span class="text-xs text-[var(--success)] block mb-1 font-medium">参考答案：</span>
                <span v-html="renderedCorrectDisplay" />
              </div>
            </div>
          </template>

          <!-- Rating -->
          <div class="border-t border-[var(--border-light)] pt-4">
            <p class="text-sm font-medium text-[var(--ink-secondary)] mb-3 text-center">你的记忆程度如何?</p>
            <div class="flex gap-3">
              <button @click="submitReview(0)" :disabled="reviewing"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--error)] text-[var(--error)] font-medium
                       hover:bg-[var(--error-soft)] transition-colors text-sm disabled:opacity-50">
                完全忘记
              </button>
              <button @click="submitReview(3)" :disabled="reviewing"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--warning)] text-[var(--warning)] font-medium
                       hover:bg-[var(--warning-soft)] transition-colors text-sm disabled:opacity-50">
                部分想起
              </button>
              <button @click="submitReview(5)" :disabled="reviewing"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--success)] text-[var(--success)] font-medium
                       hover:bg-[var(--success-soft)] transition-colors text-sm disabled:opacity-50">
                完全记住
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RefreshCw, Loader, CheckCircle, Home, Eye, Check, X } from 'lucide-vue-next'
import client from '../api/client'
import { renderMarkdown } from '../composables/useKaTeX'

const items = ref([])
const currentIdx = ref(0)
const loading = ref(true)
const revealed = ref(false)
const reviewing = ref(false)
const userChoice = ref('')
const userChoices = ref(new Set())
const userAnswer = ref('')

const currentItem = computed(() => {
  if (currentIdx.value < items.value.length) return items.value[currentIdx.value]
  return null
})

const parsedContent = computed(() => {
  if (!currentItem.value?.question) return {}
  try { return JSON.parse(currentItem.value.question.content_json) }
  catch { return {} }
})

const qType = computed(() => currentItem.value?.question?.question_type || 'short_answer')

function choiceToIndex(val) {
  const v = String(val || '').trim().toUpperCase()
  if (/^[A-H]$/.test(v)) return String(v.charCodeAt(0) - 65)
  return v
}

const correctSet = computed(() => {
  if (qType.value === 'single_choice')
    return new Set([choiceToIndex(parsedContent.value.correct_answer)].filter(Boolean))
  const a = parsedContent.value.correct_answers || parsedContent.value.correct_answer
  if (!a) return new Set()
  if (Array.isArray(a)) return new Set(a.map(choiceToIndex))
  try { const arr = JSON.parse(a); return new Set(Array.isArray(arr) ? arr.map(choiceToIndex) : [choiceToIndex(a)]) }
  catch { return new Set([choiceToIndex(a)]) }
})

const correctDisplay = computed(() => {
  const a = parsedContent.value.correct_answers || parsedContent.value.correct_answer
  if (!a) return ''
  return Array.isArray(a) ? a.join(' / ') : String(a)
})
const renderedCorrectDisplay = computed(() => renderMarkdown(correctDisplay.value))

const isUserCorrect = computed(() => {
  if (qType.value === 'single_choice') return correctSet.value.has(choiceToIndex(userChoice.value))
  if (qType.value === 'multiple_choice')
    return setsEqual(new Set([...userChoices.value].map(choiceToIndex)), correctSet.value)
  if (qType.value === 'fill_blank') return null  // subjective, user self-judges
  return null
})

function setsEqual(a, b) {
  if (a.size !== b.size) return false
  for (const x of a) if (!b.has(x)) return false
  return true
}

const renderedOptions = computed(() => {
  const opts = parsedContent.value.options || parsedContent.value.choices || {}
  const result = {}
  for (const [key, val] of Object.entries(opts)) {
    result[key] = renderMarkdown(String(val))
  }
  return result
})

const renderedQuestion = computed(() => {
  if (!currentItem.value?.question) return ''
  return renderMarkdown(parsedContent.value.question_text || '')
})

const renderedQuestionCompact = computed(() => {
  if (!currentItem.value?.question) return ''
  let html = renderMarkdown(parsedContent.value.question_text || '')
  if (qType.value === 'fill_blank') {
    html += `<div class="mt-1 text-xs text-[var(--success)]">答案：${renderMarkdown(correctDisplay.value)}</div>`
  }
  return html
})

function choiceResultClass(key) {
  if (correctSet.value.has(key) && (userChoice.value === key || userChoices.value.has(key)))
    return 'bg-[var(--success-soft)] text-[var(--success)] font-medium'
  if (correctSet.value.has(key))
    return 'bg-[var(--success-soft)]/50 text-[var(--success)]'
  if ((userChoice.value === key || userChoices.value.has(key)) && !correctSet.value.has(key))
    return 'bg-[var(--error-soft)] text-[var(--error)]'
  return 'text-[var(--ink-muted)]'
}

function toggleChoice(key) {
  const s = new Set(userChoices.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  userChoices.value = s
}

function revealAnswer() { revealed.value = true }

async function submitReview(quality) {
  if (!currentItem.value || reviewing.value) return
  reviewing.value = true
  try {
    await client.post('/srs/review', { wrong_book_id: currentItem.value.wrong_book_id, quality })
    currentIdx.value++
    revealed.value = false
    userChoice.value = ''
    userChoices.value = new Set()
    userAnswer.value = ''
  } catch (e) { console.error('Review submission failed', e) }
  finally { reviewing.value = false }
}

onMounted(async () => {
  try {
    const res = await client.get('/srs/review-today')
    items.value = res.data
  } catch { /* no reviews */ }
  finally { loading.value = false }
})
</script>
