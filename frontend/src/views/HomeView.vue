<template>
  <div class="max-w-4xl mx-auto px-4 py-8 animate-fade-in-up">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1">学习中心</h1>
      <p class="text-[var(--ink-muted)] text-sm">选择科目与章节，开始练习</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--ink-primary)]">{{ totalQuestions }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">题库</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--accent)]">{{ totalChapters }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">章节</div>
      </div>
      <div class="card card-interactive p-4 text-center">
        <div class="text-2xl font-bold text-[var(--warning)]">{{ masteredPercent }}%</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">掌握率</div>
      </div>
      <!-- Mock exam CTA -->
      <button @click="startExam()" :disabled="practicing"
        class="card card-interactive p-4 flex items-center justify-center gap-2 bg-[var(--accent-indigo-soft)] border-[var(--accent-indigo)]/20 hover:border-[var(--accent-indigo)]">
        <ClipboardList :size="20" class="text-[var(--accent-indigo)]" />
        <div class="text-left">
          <div class="text-sm font-semibold text-[var(--accent-indigo)]">模拟考</div>
          <div class="text-xs text-[var(--ink-muted)]">随机20题·不限时</div>
        </div>
      </button>
    </div>

    <!-- Subject tabs -->
    <div class="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-none">
      <button
        v-for="subject in subjects"
        :key="subject.id"
        @click="selectSubject(subject)"
        class="flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200"
        :class="selectedSubject?.id === subject.id
          ? 'bg-[var(--ink-primary)] text-white shadow-md'
          : 'bg-[var(--surface-0)] text-[var(--ink-secondary)] border border-[var(--border-light)] hover:border-[var(--ink-primary)] hover:text-[var(--ink-primary)]'"
      >
        {{ subject.name }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
      <p class="text-[var(--ink-muted)] text-sm mt-3">加载章节数据...</p>
    </div>

    <!-- Empty -->
    <div v-else-if="!selectedSubject" class="py-20 text-center">
      <BookOpen :size="40" class="mx-auto text-[var(--border)]" />
      <p class="text-[var(--ink-muted)] mt-3">请选择一个科目开始学习</p>
    </div>

    <!-- Daily Plan Card -->
    <div v-if="dailyPlanLoading" class="card p-4 mb-4 border-[var(--accent)]/20 bg-[var(--accent-soft)]">
      <div class="flex items-center gap-3">
        <Loader :size="16" class="animate-spin text-[var(--accent)]" />
        <span class="text-sm text-[var(--ink-muted)]">AI 正在为你生成今日学习建议...</span>
      </div>
    </div>
    <div v-else-if="dailyPlan" class="card p-4 mb-4 border-[var(--accent)]/20 bg-[var(--accent-soft)] relative">
      <div class="flex gap-3">
        <div class="w-8 h-8 rounded-lg bg-[var(--accent)]/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Sparkles :size="16" class="text-[var(--accent)]" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-xs text-[var(--ink-muted)] mb-1">今日学习建议</div>
          <div class="text-sm text-[var(--ink-primary)] leading-relaxed" v-html="renderedDailyPlan" />
          <div class="daily-plan-actions flex gap-0.5 mt-2 sm:absolute sm:top-3 sm:right-3 sm:mt-0">
            <button @click="loadDailyPlan(true)" :disabled="dailyPlanLoading" class="btn-icon" title="刷新">
              <RefreshCw :size="14" :class="dailyPlanLoading ? 'animate-spin' : ''" />
            </button>
            <button @click="dailyPlan=''" class="btn-icon" title="关闭">
              <X :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Review hint -->
    <div v-if="reviewCount > 0" class="mb-3 flex items-center gap-2 text-xs text-[var(--ink-muted)]">
      <RefreshCw :size="12" />
      <span>{{ reviewCount }} 道错题待复习</span>
      <router-link to="/review" class="text-[var(--accent)] hover:underline ml-1">去复习 →</router-link>
      <button @click="reviewCount = 0" class="text-[var(--ink-muted)] hover:text-[var(--ink-primary)] ml-2">✕</button>
    </div>

    <!-- Chapter tree -->
    <div class="space-y-3 stagger">
      <div
        v-for="ch1 in chapterTree"
        :key="ch1.id"
        class="card overflow-hidden"
      >
        <!-- Level 1: Chapter -->
        <button
          @click="toggleChapter(ch1)"
          class="w-full flex items-center gap-3 px-5 py-4 hover:bg-[var(--surface-1)] transition-colors text-left group"
        >
          <div class="w-8 h-8 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center flex-shrink-0">
            <Folder :size="16" class="text-[var(--accent-indigo)]" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-medium text-[var(--ink-primary)] truncate">{{ ch1.name }}</div>
            <div class="text-xs text-[var(--ink-muted)]">{{ ch1.children?.length || 0 }} 节</div>
          </div>
          <ChevronDown
            :size="18"
            class="text-[var(--ink-muted)] transition-transform duration-300 flex-shrink-0"
            :class="{ 'rotate-180': expandedChapters.has(ch1.id) }"
          />
        </button>

        <!-- Recursive chapter tree (supports unlimited depth) -->
        <transition name="expand">
          <div v-if="expandedChapters.has(ch1.id)" class="border-t border-[var(--border-light)]">
            <HomeChapterNode
              v-for="child in ch1.children" :key="child.id"
              :node="child" :depth="1"
              @startLesson="startLesson"
              @startPure="startPure"
            />
            <div v-if="!ch1.children?.length" class="px-5 py-8 text-center text-sm text-[var(--ink-muted)]">
              暂无章节内容
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>

  <!-- Loading overlay for AI question generation -->
  <Teleport to="body">
    <div v-if="practicing" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div class="card p-8 text-center space-y-4 animate-scale-in">
        <Loader :size="32" class="animate-spin mx-auto text-[var(--accent)]" />
        <p class="text-lg font-semibold text-[var(--ink-primary)]">AI 正在生成题目...</p>
        <p class="text-sm text-[var(--ink-muted)]">正在为你量身定制练习，预计需要 5-10 秒</p>
      </div>
    </div>
  </Teleport>

  <!-- Onboarding Wizard (shown on first visit) -->
  <OnboardingWizard v-if="showOnboarding" @done="showOnboarding = false" />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, Folder, FileText, ChevronDown, ChevronRight, Play, Zap, Loader, ClipboardList, RefreshCw, Sparkles, X } from 'lucide-vue-next'
import client from '../api/client'
import { usePracticeStore } from '../stores/practice'
import { renderMarkdown } from '../composables/useKaTeX'
import HomeChapterNode from '../components/subjects/HomeChapterNode.vue'
import OnboardingWizard from '../components/OnboardingWizard.vue'

const showOnboarding = ref(!localStorage.getItem('onboarded'))
import MasteryStars from '../components/subjects/MasteryStars.vue'

const router = useRouter()
const practiceStore = usePracticeStore()

const subjects = ref([])
const selectedSubject = ref(null)
const chapterTree = ref([])
const expandedChapters = ref(new Set())
const loading = ref(false)
const practicing = ref(false)

// Computed stats — recursively walk tree (handles any nesting depth)
function countLeafNodes(nodes) {
  let count = 0
  for (const n of nodes) {
    if (n.is_leaf) count++
    if (n.children) count += countLeafNodes(n.children)
  }
  return count
}
function sumQuestions(nodes) {
  let sum = 0
  for (const n of nodes) {
    if (n.is_leaf) sum += n.question_count || 0
    if (n.children) sum += sumQuestions(n.children)
  }
  return sum
}
function calcMastery(nodes) {
  let total = 0, mastered = 0
  for (const n of nodes) {
    if (n.is_leaf && n.mastery) {
      total++
      if (n.mastery.star_level >= 3) mastered++
    }
    if (n.children) {
      const [t, m] = calcMastery(n.children)
      total += t; mastered += m
    }
  }
  return [total, mastered]
}

const totalChapters = computed(() => countLeafNodes(chapterTree.value))
const totalQuestions = computed(() => sumQuestions(chapterTree.value))
const masteredPercent = computed(() => {
  const [t, m] = calcMastery(chapterTree.value)
  return t > 0 ? Math.round((m / t) * 100) : 0
})

const reviewCount = ref(0)
const dailyPlan = ref('')
const dailyPlanLoading = ref(false)
const renderedDailyPlan = computed(() => renderMarkdown(dailyPlan.value))
const PLAN_CACHE_KEY = 'daily_plan_cache'

function getCachedPlan() {
  try {
    const cached = JSON.parse(localStorage.getItem(PLAN_CACHE_KEY) || '{}')
    const today = new Date().toDateString()
    if (cached.date === today && cached.plan) return cached.plan
    // Check 2-hour window
    if (cached.ts && (Date.now() - cached.ts) < 2 * 60 * 60 * 1000 && cached.plan) return cached.plan
  } catch {}
  return null
}

function cachePlan(plan) {
  try {
    localStorage.setItem(PLAN_CACHE_KEY, JSON.stringify({
      date: new Date().toDateString(), ts: Date.now(), plan
    }))
  } catch {}
}

async function loadReviewCount() {
  try {
    const res = await client.get('/srs/review-today')
    reviewCount.value = res.data.length
  } catch { reviewCount.value = 0 }
}

async function loadDailyPlan(force = false) {
  // Check cache first
  if (!force) {
    const cached = getCachedPlan()
    if (cached) { dailyPlan.value = cached; return }
  }
  if (dailyPlanLoading.value) return
  dailyPlanLoading.value = true
  try {
    const token = localStorage.getItem('token')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/daily-plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: '{}', signal: controller.signal,
    })
    clearTimeout(timeout)
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = '', plan = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      for (const line of buffer.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            if (d.chunk) plan += d.chunk
            else if (d.done) { dailyPlan.value = d.plan || plan; cachePlan(dailyPlan.value) }
            else if (d.error) { /* silent */ }
          } catch {}
        }
      }
      buffer = buffer.includes('\n') ? buffer.split('\n').pop() : ''
    }
  } catch (e) {
    if (e.name !== 'AbortError') { /* non-critical */ }
  } finally { dailyPlanLoading.value = false }
}

onMounted(async () => {
  try {
    const res = await client.get('/subjects')
    subjects.value = res.data
    if (subjects.value.length > 0) {
      selectSubject(subjects.value[0])
      // 已有科目的用户不弹引导
      if (!localStorage.getItem('onboarded')) {
        localStorage.setItem('onboarded', 'true')
        showOnboarding.value = false
      }
    }
  } catch (e) {
    console.error('Failed to load subjects', e)
  }
  loadReviewCount()
  loadDailyPlan()
  // Listen for AI assistant data changes
  import('../utils/events').then(({ on }) => {
    unsubscribe = on('data-changed', () => {
      if (selectedSubject.value) selectSubject(selectedSubject.value)
    })
  })
})

let unsubscribe = null
onUnmounted(() => { if (unsubscribe) unsubscribe() })

async function selectSubject(subject) {
  selectedSubject.value = subject
  expandedChapters.value = new Set()
  loading.value = true
  try {
    const res = await client.get(`/subjects/${subject.id}/chapters`)
    chapterTree.value = res.data
    // Auto-expand all chapters
    for (const ch of chapterTree.value) {
      expandedChapters.value.add(ch.id)
    }
  } catch (e) {
    console.error('Failed to load chapters', e)
  } finally {
    loading.value = false
  }
}

function toggleChapter(ch) {
  if (expandedChapters.value.has(ch.id)) {
    expandedChapters.value.delete(ch.id)
  } else {
    expandedChapters.value.add(ch.id)
  }
}

async function startLesson(ch3) {
  practicing.value = true
  try {
    await practiceStore.startLesson(ch3.id)
    router.push(`/practice/${practiceStore.session.id}`)
  } catch (e) {
    console.error('Failed to start lesson', e)
  } finally {
    practicing.value = false
  }
}

async function startExam() {
  practicing.value = true
  try {
    await practiceStore.startExam(selectedSubject.value?.id || null)
    router.push(`/practice/${practiceStore.session.id}`)
  } catch (e) {
    console.error('Failed to start exam', e)
  } finally {
    practicing.value = false
  }
}

async function startPure(ch3) {
  practicing.value = true
  try {
    await practiceStore.startPure(selectedSubject.value.id, ch3.id)
    router.push(`/practice/${practiceStore.session.id}`)
  } catch (e) {
    console.error('Failed to start pure practice', e)
  } finally {
    practicing.value = false
  }
}
</script>

<style scoped>
.scrollbar-none::-webkit-scrollbar { display: none; }
.scrollbar-none { -ms-overflow-style: none; scrollbar-width: none; }

/* Expand animation */
.expand-enter-active {
  transition: all 0.3s var(--ease-out);
  overflow: hidden;
}
.expand-leave-active {
  transition: all 0.2s var(--ease-in-out);
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}
</style>
