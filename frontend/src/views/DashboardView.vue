<template>
  <div class="max-w-4xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center">
          <BarChart3 :size="18" class="text-[var(--accent-indigo)]" />
        </div>
        学习统计
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">每日学习数据与趋势</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <template v-else>
      <!-- ═══ Daily Cards ═══ -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div class="card p-4 text-center">
          <div class="text-2xl font-bold text-[var(--ink-primary)]">{{ daily.total_attempts }}</div>
          <div class="text-xs text-[var(--ink-muted)] mt-1">今日做题</div>
        </div>
        <div class="card p-4 text-center">
          <div class="text-2xl font-bold" :class="daily.accuracy_rate >= 70 ? 'text-[var(--success)]' : 'text-[var(--warning)]'">
            {{ daily.accuracy_rate }}%
          </div>
          <div class="text-xs text-[var(--ink-muted)] mt-1">正确率</div>
        </div>
        <div class="card p-4 text-center">
          <div class="text-2xl font-bold text-[var(--accent-indigo)]">{{ formatTime(daily.total_seconds) }}</div>
          <div class="text-xs text-[var(--ink-muted)] mt-1">学习时长</div>
        </div>
        <div class="card p-4 text-center" :class="daily.streak_days > 0 ? 'border-[var(--warning)]/50' : ''">
          <div class="text-2xl font-bold text-[var(--warning)] flex items-center justify-center gap-1">
            {{ daily.streak_days }}
            <span v-if="daily.streak_days > 0" class="text-sm">🔥</span>
          </div>
          <div class="text-xs text-[var(--ink-muted)] mt-1">连续天数</div>
        </div>
      </div>

      <!-- ═══ Review counts ═══ -->
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="card p-4 flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center">
            <RefreshCw :size="18" class="text-[var(--accent)]" />
          </div>
          <div>
            <div class="text-lg font-bold text-[var(--ink-primary)]">{{ daily.srs_reviews }}</div>
            <div class="text-xs text-[var(--ink-muted)]">今日复习错题</div>
          </div>
        </div>
        <div class="card p-4 flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-[var(--accent-indigo-soft)] flex items-center justify-center">
            <BookOpen :size="18" class="text-[var(--accent-indigo)]" />
          </div>
          <div>
            <div class="text-lg font-bold text-[var(--ink-primary)]">{{ daily.vocab_reviews }}</div>
            <div class="text-xs text-[var(--ink-muted)]">今日复习单词</div>
          </div>
        </div>
      </div>

      <!-- ═══ Trend Chart ═══ -->
      <div class="card p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold text-sm text-[var(--ink-secondary)]">近 {{ trend.days }} 天趋势</h2>
          <div class="flex gap-1">
            <button v-for="d in [7,14,30]" :key="d" @click="loadTrend(d)"
              class="text-xs px-2 py-1 rounded"
              :class="trend.days === d ? 'bg-[var(--ink-primary)] text-white' : 'text-[var(--ink-muted)] hover:bg-[var(--surface-2)]'">
              {{ d }}天
            </button>
          </div>
        </div>
        <!-- Simple bar chart -->
        <div class="flex items-end gap-1 h-32">
          <div v-for="point in trend.data" :key="point.date" class="flex-1 flex flex-col items-center gap-1 min-w-0">
            <div class="w-full bg-[var(--accent-indigo)] rounded-t opacity-80 hover:opacity-100 transition-opacity"
                 :style="{ height: maxBarHeight(point.total) + '%' }"
                 :title="`${point.date}: ${point.total}题, ${point.accuracy}%`" />
            <span class="text-[9px] text-[var(--ink-muted)] truncate w-full text-center">
              {{ point.date.slice(5) }}
            </span>
          </div>
        </div>
        <div class="flex justify-between mt-2 text-xs text-[var(--ink-muted)]">
          <span>{{ trend.data[0]?.total || 0 }} 题/日 (最高)</span>
          <span>正确率 {{ trendAccuracyAvg }}%</span>
        </div>
      </div>

      <!-- ═══ Subject Distribution ═══ -->
      <div class="card p-5">
        <h2 class="font-semibold text-sm text-[var(--ink-secondary)] mb-4">科目分布</h2>
        <div v-if="subjects.length === 0" class="text-sm text-center text-[var(--ink-muted)] py-4">
          暂无练习数据
        </div>
        <div v-else class="space-y-3">
          <div v-for="s in subjects" :key="s.subject_id" class="flex items-center gap-3">
            <span class="text-sm text-[var(--ink-primary)] w-24 truncate">{{ s.subject_name }}</span>
            <div class="flex-1 h-4 bg-[var(--surface-2)] rounded-full overflow-hidden">
              <div class="h-full bg-[var(--accent-indigo)] rounded-full transition-all"
                   :style="{ width: subjectPercent(s) + '%' }" />
            </div>
            <span class="text-xs text-[var(--ink-muted)] w-16 text-right">{{ s.attempts }} 题</span>
            <span class="text-xs w-12 text-right" :class="s.accuracy >= 70 ? 'text-[var(--success)]' : 'text-[var(--warning)]'">
              {{ s.accuracy }}%
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { BarChart3, Loader, RefreshCw, BookOpen } from 'lucide-vue-next'
import client from '../api/client'

const loading = ref(true)
const daily = ref({ total_attempts: 0, correct_count: 0, accuracy_rate: 0, total_seconds: 0, sessions: 0, srs_reviews: 0, vocab_reviews: 0, streak_days: 0 })
const trend = ref({ days: 7, data: [] })
const subjects = ref([])

function formatTime(s) {
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}分`
  const h = Math.floor(m / 60)
  return `${h}时${m % 60}分`
}

function maxBarHeight(total) {
  const max = Math.max(...trend.value.data.map(d => d.total), 1)
  return Math.max((total / max) * 100, 4)
}

const trendAccuracyAvg = computed(() => {
  if (!trend.value.data.length) return 0
  const avg = trend.value.data.reduce((s, d) => s + d.accuracy, 0) / trend.value.data.length
  return Math.round(avg)
})

const totalSubjectAttempts = computed(() => subjects.value.reduce((s, x) => s + x.attempts, 0) || 1)
function subjectPercent(s) { return Math.round(s.attempts / totalSubjectAttempts.value * 100) }

async function loadTrend(days) {
  const res = await client.get('/stats/trends', { params: { days } })
  trend.value = res.data
}

onMounted(async () => {
  try {
    const [d, t, s] = await Promise.all([
      client.get('/stats/daily'),
      client.get('/stats/trends', { params: { days: 7 } }),
      client.get('/stats/subjects'),
    ])
    daily.value = d.data
    trend.value = t.data
    subjects.value = s.data
  } catch (e) {
    console.error('Stats load failed', e)
  } finally {
    loading.value = false
  }
})
</script>
