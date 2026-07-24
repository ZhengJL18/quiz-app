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
        <!-- Toolbar -->
        <div class="ml-auto flex items-center gap-1">
          <!-- Edit/Save toggle -->
          <template v-if="renderedLesson && !store.streaming">
            <button v-if="!store.editingLesson" @click="store.startEditLesson()"
              class="btn btn-ghost text-xs py-1 px-2" title="编辑讲义">
              <Pencil :size="14" />
              <span class="hidden sm:inline">编辑</span>
            </button>
            <template v-else>
              <button @click="store.cancelEditLesson()"
                class="btn btn-ghost text-xs py-1 px-2" title="取消编辑">
                <X :size="14" />
              </button>
              <button @click="store.saveLessonEdit()"
                class="btn btn-primary text-xs py-1 px-2" title="保存修改">
                <Check :size="14" />
                <span class="hidden sm:inline">保存</span>
              </button>
            </template>
            <!-- Regenerate -->
            <button @click="regenerating = true; store.regenerateLesson().finally(() => regenerating = false)"
              :disabled="regenerating"
              class="btn btn-ghost text-xs py-1 px-2" title="重新生成讲义">
              <RefreshCw :size="14" :class="regenerating ? 'animate-spin' : ''" />
              <span class="hidden sm:inline">重新生成</span>
            </button>
          </template>
        </div>
      </div>

      <div class="card p-6 sm:p-8">
        <!-- Streaming indicator (waiting for first token) -->
        <div v-if="store.streaming && !renderedLesson" class="flex items-center gap-3 py-8 justify-center">
          <Loader :size="20" class="animate-spin text-[var(--accent-indigo)]" />
          <span class="text-sm text-[var(--ink-muted)]">AI 正在生成讲义...</span>
        </div>
        <!-- Edit mode: textarea -->
        <div v-else-if="store.editingLesson">
          <textarea v-model="store.lessonDraft"
            class="input min-h-[300px] font-mono text-sm leading-relaxed resize-y"
            placeholder="在此编辑 Markdown 讲义内容..."></textarea>
        </div>
        <!-- Content (updates in real-time via SSE streaming) -->
        <div v-else class="prose prose-slate max-w-none text-[15px] leading-relaxed"
             v-html="renderedLesson || ''" />
        <!-- Still streaming indicator at bottom -->
        <div v-if="store.streaming && renderedLesson" class="mt-3 text-xs text-[var(--ink-muted)] animate-pulse">
          正在生成...
        </div>
      </div>

      <button
        @click="store.phase = 'question'; resetTimer()"
        :disabled="store.streaming && !renderedLesson"
        class="btn btn-primary w-full py-3.5 text-base font-medium shadow-lg hover:shadow-xl transition-shadow">
        <Play :size="18" />
        开始练习（{{ store.questions.length || 8 }} 题）
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
          <span v-else-if="store.mode === 'pure'" class="badge bg-[var(--accent-indigo-soft)] text-[var(--accent-indigo)]">
            <Zap :size="12" /> 纯练习
          </span>
          <span v-else-if="store.mode === 'exam'" class="badge bg-[var(--accent-soft)] text-[var(--accent)]">
            <ClipboardList :size="12" /> 模拟考
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
      <div class="card p-6 sm:p-8 landscape-split">
        <!-- Question text -->
        <div class="question-area text-lg leading-relaxed mb-8 text-[var(--ink-primary)]"
             v-html="renderedQuestion" />

        <!-- Answer area -->
        <div class="space-y-3">
          <!-- Single choice -->
          <template v-if="qType === 'single_choice'">
            <QuizOption
              v-for="(opt, key) in renderedOptions"
              :key="key"
              :value="key"
              :label-key="key"
              :label="opt"
              :is-selected="userAnswer === key"
              :disabled="submitting"
              @select="selectOption($event)"
            />
          </template>

          <!-- Multiple choice -->
          <template v-else-if="qType === 'multiple_choice'">
            <QuizOption
              v-for="(opt, key) in renderedOptions"
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
        @click.prevent="handleSubmit"
        :disabled="!canSubmit || submitting"
        type="button"
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
          <p class="text-sm text-[var(--ink-muted)]">已自动收录 · 可收藏到好题锦集</p>
        </div>

        <!-- Self-judge (subjective: fill_blank, short_answer, calculation, proof) -->
        <div v-else class="space-y-3">
          <div class="inline-flex w-14 h-14 rounded-full bg-[var(--warning-soft)] items-center justify-center mb-2">
            <AlertCircle :size="28" class="text-[var(--warning)]" />
          </div>
          <p class="text-xl font-bold text-[var(--ink-primary)]">主观题 · 自行判分</p>
          <p class="text-sm text-[var(--ink-muted)]">对照解析，判断自己的答案是否正确</p>
          <div class="flex gap-3 justify-center mt-3">
            <button @click="handleSelfJudge(true)" :disabled="selfJudging"
              class="btn px-6 py-2 bg-[var(--success)] text-white hover:opacity-90 disabled:opacity-50">
              ✅ 答对了
            </button>
            <button @click="handleSelfJudge(false)" :disabled="selfJudging"
              class="btn px-6 py-2 bg-[var(--error)] text-white hover:opacity-90 disabled:opacity-50">
              ❌ 答错了
            </button>
          </div>
          <p v-if="selfJudged !== null" class="text-sm font-medium" :class="selfJudged ? 'text-[var(--success)]' : 'text-[var(--error)]'">
            {{ selfJudged ? '已标记为正确 ✓' : '已标记为错误，已加入错题本' }}
          </p>
        </div>
      </div>

      <!-- Question recap with correct answer highlighted -->
      <div v-if="currentQuestion && qType === 'single_choice'" class="card p-4">
        <div class="text-sm font-medium text-[var(--ink-secondary)] mb-3">题目回顾</div>
        <div class="space-y-1.5">
          <QuizOption
            v-for="(opt, key) in renderedOptions"
            :key="key"
            :value="key"
            :label-key="key"
            :label="opt"
            :is-selected="lastUserAnswer === key"
            :is-correct="key === correctAnswerKey"
            :show-result="true"
            :disabled="true"
          />
        </div>
      </div>

      <!-- Multiple choice recap -->
      <div v-else-if="currentQuestion && qType === 'multiple_choice'" class="card p-4">
        <div class="text-sm font-medium text-[var(--ink-secondary)] mb-3">题目回顾</div>
        <div class="space-y-1.5">
          <QuizOption
            v-for="(opt, key) in renderedOptions"
            :key="key"
            :value="key"
            :label-key="key"
            :label="opt"
            :is-selected="lastUserAnswerSet.has(key)"
            :is-correct="correctAnswerSet.has(key)"
            :show-result="true"
            :disabled="true"
          />
        </div>
      </div>

      <!-- Fill blank recap -->
      <div v-else-if="currentQuestion && qType === 'fill_blank'" class="card p-4">
        <div class="text-sm font-medium text-[var(--ink-secondary)] mb-2">你的答案：<span :class="store.lastResult.is_correct ? 'text-[var(--success)]' : 'text-[var(--error)]'">{{ lastUserAnswer }}</span></div>
        <div class="text-sm text-[var(--ink-muted)]">正确答案：<span v-html="renderedCorrectDisplay" /></div>
      </div>

      <!-- Bookmark -->
      <div class="flex justify-center">
        <button @click="toggleBookmark(currentQuestion.id)" class="btn btn-outline py-2 px-5 text-sm font-medium">
          <Star :size="16" :class="bookmarked ? 'text-[var(--accent)] fill-[var(--accent)]' : ''" />
          {{ bookmarked ? '已收藏' : '收藏到好题锦集' }}
        </button>
      </div>

      <!-- Explanation -->
      <div v-if="store.lastResult.explanation" class="card p-6 sm:p-8">
        <h3 class="text-sm font-semibold text-[var(--ink-secondary)] mb-3 flex items-center gap-2">
          <Lightbulb :size="16" class="text-[var(--warning)]" />
          解析
        </h3>
        <!-- Streaming indicator for subjective -->
        <div v-if="store.explanationStreaming && !renderedExplanation" class="flex items-center gap-2 text-sm text-[var(--ink-muted)] py-4">
          <Loader :size="18" class="animate-spin" />
          AI 正在生成解析...
        </div>
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
          <button v-if="store.mode === 'pure'" @click="store.phase = 'done'" class="btn btn-outline flex-1 py-3 font-medium">
            <StopCircle :size="18" />
            结束
          </button>
          <button v-else-if="store.mode === 'exam'" @click="store.phase = 'done'" class="btn btn-outline flex-1 py-3 font-medium">
            <CheckCircle :size="18" />
            交卷
          </button>
        </template>
      </div>
    </div>

    <!-- ====== DONE PHASE ====== -->
    <div v-else-if="store.phase === 'done'" class="animate-scale-in text-center py-12">
      <div class="inline-flex w-20 h-20 rounded-full bg-[var(--success-soft)] items-center justify-center mb-6">
        <CheckCircle :size="40" class="text-[var(--success)]" />
      </div>
      <h2 class="text-2xl font-bold text-[var(--ink-primary)] mb-2">练习完成!</h2>
      <p class="text-[var(--ink-muted)] mb-1">
        {{ store.mode === 'lesson' ? '你已完成本课时的全部练习' : store.mode === 'exam' ? '模拟考已交卷' : '本次练习已结束' }}
      </p>
      <p class="text-xs text-[var(--ink-muted)] mb-6">Agent 已自动分析了你的答题数据</p>
      <div class="flex flex-col items-center gap-3 mb-6">
        <button @click="chatStore.toggle()" class="btn btn-primary px-6 py-3 font-medium inline-flex items-center gap-2">
          <Sparkles :size="18" />
          让 AI 帮你分析这次练习
        </button>
        <div class="flex gap-3">
          <router-link to="/" class="btn btn-outline px-4 py-2 text-sm no-underline inline-flex items-center gap-1">
            <Home :size="14" /> 首页
          </router-link>
          <router-link to="/collection" class="btn btn-outline px-4 py-2 text-sm no-underline inline-flex items-center gap-1">
            <Star :size="14" /> 好题
          </router-link>
          <button v-if="store.mode !== 'exam'" @click="store.fetchMoreQuestions().catch(()=>{})" class="btn btn-outline px-4 py-2 text-sm inline-flex items-center gap-1">
            <RefreshCw :size="14" /> 继续刷
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { usePracticeStore } from '../stores/practice'
import { renderMarkdown } from '../composables/useKaTeX'
import QuizOption from '../components/subjects/QuizOption.vue'
import {
  BookOpen, Play, Zap, Clock, Send, Loader, Lightbulb,
  ArrowRight, CheckCircle, StopCircle, Home, AlertCircle, ClipboardList, Star,
  Pencil, X, Check, RefreshCw, Sparkles
} from 'lucide-vue-next'
import { useChatStore } from '../stores/chat'

const route = useRoute()
const store = usePracticeStore()
const chatStore = useChatStore()

const userAnswer = ref('')
const multiSelected = ref(new Set())
const submitting = ref(false)
const elapsed = ref(0)
const bookmarked = ref(false)
const regenerating = ref(false)
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

const renderedOptions = computed(() => {
  const opts = parsedContent.value.options || parsedContent.value.choices || {}
  const result = {}
  for (const [key, val] of Object.entries(opts)) {
    result[key] = renderMarkdown(String(val))
  }
  return result
})

const qType = computed(() => currentQuestion.value?.question_type || 'single_choice')

const renderedQuestion = computed(() => renderMarkdown(parsedContent.value.question_text || ''))
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

// Feedback phase — correct answer display
const lastUserAnswer = ref('')
const lastUserAnswerSet = ref(new Set())

// Normalize choice answers: A→0, B→1, etc. (same logic as backend)
function choiceToIndex(val) {
  const v = String(val || '').trim().toUpperCase()
  if (/^[A-H]$/.test(v)) return String(v.charCodeAt(0) - 65)
  return v
}
const correctAnswerKey = computed(() => choiceToIndex(parsedContent.value.correct_answer || ''))
const correctAnswerSet = computed(() => {
  const answers = parsedContent.value.correct_answers || parsedContent.value.correct_answer
  if (!answers) return new Set()
  if (Array.isArray(answers)) return new Set(answers.map(choiceToIndex))
  try { const arr = JSON.parse(answers); return new Set(Array.isArray(arr) ? arr.map(choiceToIndex) : [choiceToIndex(answers)]) }
  catch { return new Set([choiceToIndex(answers)]) }
})
const correctDisplay = computed(() => {
  if (qType.value === 'fill_blank') {
    const a = parsedContent.value.correct_answers || parsedContent.value.correct_answer
    return Array.isArray(a) ? a.join(' / ') : (a || '')
  }
  return ''
})
const renderedCorrectDisplay = computed(() => renderMarkdown(correctDisplay.value))

// Methods
function selectOption(key) {
  userAnswer.value = key
}

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
  // Remember selection for feedback highlighting
  lastUserAnswer.value = answer
  lastUserAnswerSet.value = new Set(multiSelected.value)
  try {
    await store.submitAnswer(currentQuestion.value.id, answer, elapsed.value)
  } catch (e) {
    console.error('Submit failed', e)
  } finally {
    submitting.value = false
  }
}

async function handleNext() {
  userAnswer.value = ''
  multiSelected.value = new Set()
  lastUserAnswer.value = ''
  lastUserAnswerSet.value = new Set()
  resetTimer()
  resetSelfJudge()

  if (store.mode === 'lesson') {
    store.nextQuestion()
  } else if (store.mode === 'exam') {
    // Exam: advance through all questions, no fetching more
    if (store.currentIndex < store.questions.length - 1) {
      store.nextQuestion()
    } else {
      store.finishSession()
    }
  } else {
    // Pure mode: advance through batch, fetch more when exhausted
    if (store.currentIndex < store.questions.length - 1) {
      store.nextQuestion()
    } else {
      try { await store.fetchMoreQuestions() }
      catch (e) { store.finishSession() }
    }
  }

  // Auto-save progress
  await saveProgress()
}

// Self-judge for subjective questions
const selfJudging = ref(false)
const selfJudged = ref(null)  // null | true | false

async function handleSelfJudge(isCorrect) {
  if (!currentQuestion.value || !store.session) return
  selfJudging.value = true
  try {
    const { default: client } = await import('../api/client')
    await client.post(
      `/practice/sessions/${store.session.id}/self-judge?question_id=${currentQuestion.value.id}&is_correct=${isCorrect}`
    )
    selfJudged.value = isCorrect
    store.lastResult = { ...store.lastResult, is_correct: isCorrect }
  } catch (e) {
    console.error('Self-judge failed', e)
  } finally {
    selfJudging.value = false
  }
}

function resetSelfJudge() {
  selfJudging.value = false
  selfJudged.value = null
}

async function toggleBookmark(questionId) {
  if (!questionId) return
  try {
    const { default: client } = await import('../api/client')
    await client.post(`/wrong-book/bookmark?question_id=${questionId}`)
    bookmarked.value = !bookmarked.value
  } catch (e) {
    console.error('Bookmark failed', e)
  }
}

async function saveProgress() {
  if (!store.session?.id) return
  try {
    const { default: client } = await import('../api/client')
    await client.put(`/practice/sessions/${store.session.id}/current-index`, {
      current_index: store.currentIndex
    })
  } catch (e) {
    // Non-critical — don't block the UI
    console.error('Failed to save progress', e)
  }
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

  // Save progress on page unload
  window.addEventListener('beforeunload', saveProgress)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('beforeunload', saveProgress)
  saveProgress()
})
</script>
