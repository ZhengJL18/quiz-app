<template>
  <div class="max-w-2xl mx-auto px-4 py-8">
    <!-- ====== LESSON PHASE ====== -->
    <div v-if="store.phase === 'lesson'" class="animate-fade-in-up space-y-6">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-xl bg-[var(--accent-indigo-soft)] flex items-center justify-center">
          <BookOpen :size="20" class="text-[var(--accent-indigo)]" />
        </div>
        <div>
          <h2 class="font-semibold text-[var(--ink-primary)]">课前讲解</h2>
          <p class="text-xs text-[var(--ink-muted)]">先理解概念，再开始练习</p>
        </div>
      </div>

      <div class="card p-6 sm:p-8">
        <div class="prose prose-slate max-w-none text-[15px] leading-relaxed"
             v-html="renderedLesson" />
      </div>

      <button @click="store.phase = 'question'; resetTimer()"
        class="btn btn-primary w-full py-3.5 text-base font-medium shadow-lg hover:shadow-xl transition-shadow">
        <Play :size="18" />
        开始练习（8 题）
      </button>
    </div>

    <!-- ====== QUESTION PHASE ====== -->
    <div v-else-if="store.phase === 'question' && currentQuestion" class="animate-scale-in space-y-5">
      <!-- Top bar -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <!-- Progress -->
          <div v-if="store.mode === 'lesson'" class="flex items-center gap-2">
            <div class="w-32 h-1.5 bg-[var(--border-light)] rounded-full overflow-hidden">
              <div
                class="h-full bg-[var(--ink-primary)] rounded-full transition-all duration-500 ease-out"
                :style="{ width: `${((store.currentIndex + 1) / store.questions.length) * 100}%` }"
              />
            </div>
            <span class="text-xs font-medium text-[var(--ink-muted)] tabular-nums">
              {{ store.currentIndex + 1 }}/{{ store.questions.length }}
            </span>
          </div>
          <!-- Mode badge -->
          <span v-else class="badge bg-[var(--accent-indigo-soft)] text-[var(--accent-indigo)]">
            <Zap :size="12" /> 纯练习
          </span>
        </div>

        <!-- Timer -->
        <div class="flex items-center gap-1.5 text-sm tabular-nums"
             :class="elapsed > 60 ? 'text-[var(--warning)]' : 'text-[var(--ink-muted)]'">
          <Clock :size="14" />
          {{ formattedTime }}
        </div>
      </div>

      <!-- Question card -->
      <div class="card p-6 sm:p-8">
        <!-- Question text -->
        <div class="text-lg leading-relaxed mb-8 text-[var(--ink-primary)]"
             v-html="renderedQuestion" />

        <!-- Answer area -->
        <div class="space-y-3">
          <!-- Single choice -->
          <template v-if="qType === 'single_choice'">
            <QuizOption
              v-for="(opt, key) in parsedContent.options"
              :key="key"
              :value="key"
              :label-key="key"
              :label="opt"
              :is-selected="userAnswer === key"
              :disabled="submitting"
              @select="userAnswer = key"
            />
          </template>

          <!-- Multiple choice -->
          <template v-else-if="qType === 'multiple_choice'">
            <QuizOption
              v-for="(opt, key) in parsedContent.options"
              :key="key"
              :value="key"
              :label-key="key"
              :label="opt"
              :is-selected="multiSelected.has(key)"
              :disabled="submitting"
              @select="toggleMulti(key)"
            />
          </template>

          <!-- Fill blank -->
          <template v-else-if="qType === 'fill_blank'">
            <input
              v-model="userAnswer"
              type="text"
              placeholder="输入你的答案..."
              class="input text-lg"
              :disabled="submitting"
              @keydown.enter="handleSubmit"
            />
          </template>

          <!-- Text answer -->
          <template v-else>
            <textarea
              v-model="userAnswer"
              rows="4"
              placeholder="输入你的答案..."
              class="input resize-y"
              :disabled="submitting"
            />
          </template>
        </div>
      </div>

      <!-- Submit -->
      <button
        @click="handleSubmit"
        :disabled="!canSubmit || submitting"
        class="btn btn-primary w-full py-3.5 text-base font-medium shadow-lg hover:shadow-xl transition-shadow">
        <Send v-if="!submitting" :size="18" />
        <Loader v-else :size="18" class="animate-spin" />
        {{ submitting ? '判题中...' : '提交答案' }}
      </button>

      <!-- Skip hint for pure mode -->
      <p v-if="store.mode === 'pure'" class="text-center text-xs text-[var(--ink-muted)]">
        按 <kbd class="px-1.5 py-0.5 bg-[var(--surface-2)] rounded text-xs font-mono">Enter</kbd> 快速提交
      </p>
    </div>

    <!-- ====== FEEDBACK PHASE ====== -->
    <div v-else-if="store.phase === 'feedback' && store.lastResult" class="animate-scale-in space-y-5">
      <!-- Result banner -->
      <div class="card p-6 sm:p-8 text-center"
           :class="store.lastResult.is_correct ? 'border-[var(--success)]' : 'border-[var(--error)]'">
        <!-- Correct -->
        <div v-if="store.lastResult.is_correct === true" class="space-y-2">
          <div class="inline-flex w-14 h-14 rounded-full bg-[var(--success-soft)] items-center justify-center mb-2">
            <svg class="w-7 h-7 text-[var(--success)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" class="animate-[checkDraw_0.4s_ease-out]" />
            </svg>
          </div>
          <p class="text-xl font-bold text-[var(--success)]">回答正确!</p>
          <p class="text-sm text-[var(--ink-muted)]">继续保持</p>
        </div>

        <!-- Incorrect -->
        <div v-else-if="store.lastResult.is_correct === false" class="space-y-2">
          <div class="inline-flex w-14 h-14 rounded-full bg-[var(--error-soft)] items-center justify-center mb-2">
            <svg class="w-7 h-7 text-[var(--error)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </div>
          <p class="text-xl font-bold text-[var(--error)]">回答错误</p>
          <p class="text-sm text-[var(--ink-muted)]">仔细看看解析，下次一定对</p>
        </div>

        <!-- Manual review -->
        <div v-else class="space-y-2">
          <div class="inline-flex w-14 h-14 rounded-full bg-[var(--warning-soft)] items-center justify-center mb-2">
            <AlertCircle :size="28" class="text-[var(--warning)]" />
          </div>
          <p class="text-xl font-bold text-[var(--warning)]">已提交</p>
          <p class="text-sm text-[var(--ink-muted)]">等待人工评判</p>
        </div>
      </div>

      <!-- Explanation -->
      <div v-if="store.lastResult.explanation" class="card p-6 sm:p-8">
        <h3 class="text-sm font-semibold text-[var(--ink-secondary)] mb-3 flex items-center gap-2">
          <Lightbulb :size="16" class="text-[var(--warning)]" />
          解析
        </h3>
        <div class="prose prose-slate max-w-none text-[15px] leading-relaxed"
             v-html="renderedExplanation" />
      </div>

      <!-- Actions -->
      <div class="flex gap-3">
        <button
          v-if="store.mode === 'lesson' && store.currentIndex < store.questions.length - 1"
          @click="handleNext"
          class="btn btn-primary flex-1 py-3 font-medium">
          <ArrowRight :size="18" />
          下一题
        </button>
        <button
          v-else-if="store.mode === 'lesson'"
          @click="store.phase = 'done'"
          class="btn btn-primary flex-1 py-3 font-medium">
          <CheckCircle :size="18" />
          完成练习
        </button>

        <!-- Pure mode actions -->
        <template v-else>
          <button @click="handleNext" class="btn btn-primary flex-1 py-3 font-medium">
            <ArrowRight :size="18" />
            下一题
          </button>
          <button @click="store.phase = 'done'" class="btn btn-outline flex-1 py-3 font-medium">
            <StopCircle :size="18" />
            结束
          </button>
        </template>
      </div>
    </div>

    <!-- ====== DONE PHASE ====== -->
    <div v-else-if="store.phase === 'done'" class="animate-scale-in text-center py-16">
      <div class="inline-flex w-20 h-20 rounded-full bg-[var(--success-soft)] items-center justify-center mb-6">
        <CheckCircle :size="40" class="text-[var(--success)]" />
      </div>
      <h2 class="text-2xl font-bold text-[var(--ink-primary)] mb-2">练习完成!</h2>
      <p class="text-[var(--ink-muted)] mb-8">
        {{ store.mode === 'lesson' ? '你已完成本课时的全部练习' : '本次纯练习已结束' }}
      </p>
      <router-link to="/" class="btn btn-primary px-8 py-3 font-medium no-underline inline-flex">
        <Home :size="18" />
        返回首页
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePracticeStore } from '../stores/practice'
import { renderLatex, renderMarkdown } from '../composables/useKaTeX'
import QuizOption from '../components/subjects/QuizOption.vue'
import {
  BookOpen, Play, Zap, Clock, Send, Loader, Lightbulb,
  ArrowRight, CheckCircle, StopCircle, Home, AlertCircle
} from 'lucide-vue-next'

const store = usePracticeStore()

const userAnswer = ref('')
const multiSelected = ref(new Set())
const submitting = ref(false)
const elapsed = ref(0)
let timer = null

// Computed
const currentQuestion = computed(() => {
  if (store.currentIndex < store.questions.length) {
    return store.questions[store.currentIndex]
  }
  return null
})

const parsedContent = computed(() => {
  if (!currentQuestion.value) return {}
  try { return JSON.parse(currentQuestion.value.content_json) }
  catch { return {} }
})

const qType = computed(() => currentQuestion.value?.question_type || 'single_choice')

const renderedQuestion = computed(() => renderLatex(parsedContent.value.question_text || ''))
const renderedLesson = computed(() => renderMarkdown(store.lessonContent || ''))
const renderedExplanation = computed(() => renderMarkdown(store.lastResult?.explanation || ''))

const formattedTime = computed(() => {
  const m = Math.floor(elapsed.value / 60)
  const s = elapsed.value % 60
  return `${m}:${String(s).padStart(2, '0')}`
})

const canSubmit = computed(() => {
  if (qType.value === 'multiple_choice') return multiSelected.value.size > 0
  if (qType.value === 'fill_blank' || qType.value === 'text') return userAnswer.value.trim().length > 0
  return !!userAnswer.value
})

// Methods
function toggleMulti(key) {
  const s = new Set(multiSelected.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  multiSelected.value = s
}

function resetTimer() {
  elapsed.value = 0
}

async function handleSubmit() {
  if (!currentQuestion.value || !canSubmit.value) return
  submitting.value = true
  const answer = qType.value === 'multiple_choice'
    ? JSON.stringify([...multiSelected.value].sort())
    : userAnswer.value
  try {
    await store.submitAnswer(currentQuestion.value.id, answer, elapsed.value)
  } catch (e) {
    console.error('Submit failed', e)
  } finally {
    submitting.value = false
  }
}

async function handleNext() {
  if (store.mode === 'lesson') {
    store.nextQuestion()
  } else {
    try { await store.fetchMoreQuestion() }
    catch (e) { console.error('Next failed', e) }
  }
  userAnswer.value = ''
  multiSelected.value = new Set()
  resetTimer()
}

// Timer + session loading
onMounted(async () => {
  timer = setInterval(() => { elapsed.value++ }, 1000)
  // Load session if navigating directly (store is empty)
  if (!store.session) {
    const sessionId = route.params.sessionId
    if (sessionId) {
      try {
        await store.loadSession(sessionId)
      } catch (e) {
        console.error('Failed to load session', e)
      }
    }
  }
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
