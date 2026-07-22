<template>
  <div class="max-w-xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-[var(--ink-primary)] flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center">
            <BookOpen :size="18" class="text-[var(--accent)]" />
          </div>
          背单词
        </h1>
        <p class="text-[var(--ink-muted)] text-sm ml-12">词根拆解 · 近反义词 · 搭配 · 乱序复习</p>
      </div>
      <button @click="showGenerate = !showGenerate" class="btn btn-outline text-xs py-1.5 px-3">
        <Plus :size="14" /> 生成新词
      </button>
    </div>

    <!-- Generate form -->
    <div v-if="showGenerate" class="card p-4 mb-4 space-y-3 animate-slide-down">
      <div class="flex gap-3 items-end">
        <div class="flex-1">
          <label class="text-xs text-[var(--ink-muted)] block mb-1">词库</label>
          <select v-model="genSubject" class="input text-sm py-1.5">
            <option>英语四六级</option>
            <option>考研英语</option>
            <option>雅思词汇</option>
            <option>托福词汇</option>
          </select>
        </div>
        <div class="w-20">
          <label class="text-xs text-[var(--ink-muted)] block mb-1">数量</label>
          <select v-model="genCount" class="input text-sm py-1.5">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
          </select>
        </div>
        <button @click="generateCards" :disabled="generating"
          class="btn btn-primary text-sm py-1.5 px-4">
          {{ generating ? '生成中...' : '生成' }}
        </button>
      </div>
      <p class="text-xs text-[var(--ink-muted)]">AI 将自动生成词根分析、近反义词和常见搭配</p>
    </div>

    <!-- ═══ REVIEW MODE ═══ -->
    <div v-if="reviewMode" class="space-y-6">
      <div class="flex items-center gap-3">
        <div class="flex-1 h-1.5 bg-[var(--border-light)] rounded-full overflow-hidden">
          <div class="h-full bg-[var(--accent)] rounded-full transition-all duration-500"
               :style="{ width: `${(reviewIdx / reviewItems.length) * 100}%` }" />
        </div>
        <span class="text-xs text-[var(--ink-muted)]">{{ reviewIdx }}/{{ reviewItems.length }}</span>
      </div>

      <div v-if="reviewDone" class="py-16 text-center animate-scale-in">
        <CheckCircle :size="48" class="mx-auto text-[var(--success)] mb-4" />
        <p class="text-lg font-medium text-[var(--ink-primary)]">复习完成!</p>
        <button @click="reviewMode = false" class="btn btn-primary mt-6 px-8">返回词库</button>
      </div>

      <!-- ═══ FLASHCARD ═══ -->
      <div v-else class="card animate-scale-in overflow-hidden">

        <!-- FRONT: Word only -->
        <div v-if="!revealed" class="p-8 sm:p-10 text-center">
          <p class="text-4xl sm:text-5xl font-bold text-[var(--ink-primary)] mb-4 tracking-wide">
            {{ currentReviewWord.word }}
          </p>
          <p v-if="currentReviewWord.pronunciation" class="text-base text-[var(--ink-muted)] mb-10">
            {{ currentReviewWord.pronunciation }}
          </p>
          <button @click="revealCard" class="btn btn-primary w-full py-3.5 text-base font-medium">
            点击查看释义
          </button>
        </div>

        <!-- BACK: Full card -->
        <div v-else class="animate-scale-in">
          <!-- Header -->
          <div class="p-6 sm:p-8 pb-4 text-center border-b border-[var(--border-light)]">
            <p class="text-3xl sm:text-4xl font-bold text-[var(--ink-primary)] mb-2 tracking-wide">
              {{ currentReviewWord.word }}
            </p>
            <p v-if="currentReviewWord.pronunciation" class="text-sm text-[var(--ink-muted)] mb-3">
              {{ currentReviewWord.pronunciation }}
            </p>
            <p class="text-xl font-semibold text-[var(--ink-primary)]">
              {{ currentReviewWord.definition }}
            </p>
          </div>

          <div class="p-6 sm:p-8 pt-5 space-y-4 text-sm">
            <!-- Example -->
            <div v-if="currentReviewWord.example_sentence" class="p-3 bg-[var(--surface-1)] rounded-lg">
              <span class="text-xs text-[var(--ink-muted)] block mb-1">例句</span>
              <span class="text-[var(--ink-secondary)] italic leading-relaxed">{{ currentReviewWord.example_sentence }}</span>
            </div>

            <!-- Root analysis -->
            <div v-if="currentReviewWord.root_analysis" class="p-3 bg-[var(--accent-indigo-soft)] rounded-lg">
              <span class="text-xs text-[var(--accent-indigo)] block mb-1 font-medium">词根词缀</span>
              <span class="text-[var(--ink-secondary)] leading-relaxed">{{ currentReviewWord.root_analysis }}</span>
            </div>

            <!-- Synonyms / Antonyms / Collocations row -->
            <div v-if="hasRelated" class="grid grid-cols-1 gap-3">
              <div v-if="synonymList.length" class="p-3 bg-[var(--success-soft)] rounded-lg">
                <span class="text-xs text-[var(--success)] block mb-1 font-medium">近义词</span>
                <span class="text-[var(--ink-secondary)]">{{ synonymList.join(' · ') }}</span>
              </div>
              <div v-if="antonymList.length" class="p-3 bg-[var(--error-soft)] rounded-lg">
                <span class="text-xs text-[var(--error)] block mb-1 font-medium">反义词</span>
                <span class="text-[var(--ink-secondary)]">{{ antonymList.join(' · ') }}</span>
              </div>
              <div v-if="collocationList.length" class="p-3 bg-[var(--warning-soft)] rounded-lg">
                <span class="text-xs text-[var(--warning)] block mb-1 font-medium">常见搭配</span>
                <span class="text-[var(--ink-secondary)]">{{ collocationList.join(' · ') }}</span>
              </div>
            </div>
          </div>

          <!-- Rating -->
          <div class="px-6 sm:px-8 pb-6 pt-2 border-t border-[var(--border-light)]">
            <p class="text-sm font-medium text-[var(--ink-secondary)] mb-3 text-center">你认识这个词吗？</p>
            <div class="flex gap-3">
              <button @click="rateReview(0)" :disabled="ratingBusy"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--error)] text-[var(--error)] font-medium
                       hover:bg-[var(--error-soft)] transition-colors text-sm disabled:opacity-50">
                {{ ratingBusy ? '提交中...' : '不认识' }}
              </button>
              <button @click="rateReview(3)" :disabled="ratingBusy"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--warning)] text-[var(--warning)] font-medium
                       hover:bg-[var(--warning-soft)] transition-colors text-sm disabled:opacity-50">
                {{ ratingBusy ? '提交中...' : '模糊' }}
              </button>
              <button @click="rateReview(5)" :disabled="ratingBusy"
                class="flex-1 py-3 rounded-lg border-2 border-[var(--success)] text-[var(--success)] font-medium
                       hover:bg-[var(--success-soft)] transition-colors text-sm disabled:opacity-50">
                {{ ratingBusy ? '提交中...' : '认识' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ WORD LIST ═══ -->
    <div v-else class="space-y-3">
      <div class="card p-4 flex items-center gap-4 mb-4">
        <div class="flex-1 text-center cursor-pointer hover:bg-[var(--surface-2)] rounded-lg py-2 transition-colors" @click="showFilter = showFilter === 'all' ? null : 'all'">
          <div class="text-xl font-bold text-[var(--ink-primary)]">{{ cards.length }}</div>
          <div class="text-xs text-[var(--ink-muted)]">总词汇</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <div class="flex-1 text-center cursor-pointer hover:bg-[var(--surface-2)] rounded-lg py-2 transition-colors" @click="showFilter = showFilter === 'due' ? null : 'due'">
          <div class="text-xl font-bold text-[var(--accent)]">{{ dueCount }}</div>
          <div class="text-xs text-[var(--ink-muted)]">待复习</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <div class="flex-1 text-center cursor-pointer hover:bg-[var(--surface-2)] rounded-lg py-2 transition-colors" @click="showFilter = showFilter === 'starred' ? null : 'starred'">
          <div class="text-xl font-bold text-[var(--warning)]">{{ starredCount }}</div>
          <div class="text-xs text-[var(--ink-muted)]">收藏</div>
        </div>
        <div class="w-px h-8 bg-[var(--border-light)]" />
        <button @click="startReview" :disabled="dueCount === 0"
          class="flex-1 py-2.5 rounded-lg font-medium text-sm transition-colors"
          :class="dueCount > 0
            ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]'
            : 'bg-[var(--surface-2)] text-[var(--ink-muted)] cursor-not-allowed'">
          {{ dueCount > 0 ? `开始复习 (${dueCount})` : '今日无复习' }}
        </button>
      </div>
      <div v-if="showFilter" class="text-xs text-center text-[var(--ink-muted)] mb-2">
        正在筛选：{{ {all:'全部',due:'待复习',starred:'收藏'}[showFilter] }} ·
        <button @click="showFilter = null" class="underline">清除筛选</button>
      </div>

      <div v-for="card in cards" :key="card.id" class="card p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-semibold text-[var(--ink-primary)]">{{ card.word }}</span>
              <span v-if="card.pronunciation" class="text-xs text-[var(--ink-muted)]">{{ card.pronunciation }}</span>
            </div>
            <div class="text-xs text-[var(--ink-muted)] mt-0.5 line-clamp-2">{{ card.definition }}</div>
            <div v-if="card.root_analysis" class="text-xs text-[var(--ink-muted)] mt-1 line-clamp-1 italic">
              {{ card.root_analysis }}
            </div>
          </div>
          <button @click="toggleStar(card)" class="btn btn-ghost text-xs p-1.5 flex-shrink-0"
            :class="starred.has(card.id) ? 'text-[var(--warning)]' : 'text-[var(--ink-muted)] hover:text-[var(--warning)]'">
            <Star :size="13" :fill="starred.has(card.id) ? 'currentColor' : 'none'" />
          </button>
          <button @click="deleteCard(card)" class="btn btn-ghost text-xs p-1.5 text-[var(--ink-muted)] hover:text-[var(--error)] flex-shrink-0">
            <Trash2 :size="13" />
          </button>
        </div>
      </div>

      <div v-if="cards.length === 0 && !generating" class="py-16 text-center">
        <BookOpen :size="40" class="mx-auto text-[var(--border)] mb-3" />
        <p class="text-[var(--ink-muted)]">还没有单词，点击「生成新词」开始</p>
        <p class="text-xs text-[var(--ink-muted)] mt-1">AI 将自动生成词根分析、近反义词和搭配</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { BookOpen, Plus, CheckCircle, Trash2, Star } from 'lucide-vue-next'
import client from '../api/client'

const cards = ref([])
const generating = ref(false)
const showGenerate = ref(false)
const genSubject = ref('英语四六级')
const genCount = ref(10)

const reviewMode = ref(false)
const reviewItems = ref([])
const reviewIdx = ref(0)
const revealed = ref(false)
const reviewDone = ref(false)
const ratingBusy = ref(false)
const dueCount = ref(0)
const starredCount = ref(0)
const showFilter = ref(null)
const starred = ref(new Set(JSON.parse(localStorage.getItem('vocab_stars') || '[]')))

function toggleStar(card) {
  const s = new Set(starred.value)
  if (s.has(card.id)) s.delete(card.id)
  else s.add(card.id)
  starred.value = s
  starredCount.value = s.size
  localStorage.setItem('vocab_stars', JSON.stringify([...s]))
}

const currentReviewWord = computed(() => {
  if (reviewIdx.value < reviewItems.value.length) return reviewItems.value[reviewIdx.value]
  return null
})

function parseJsonList(raw) {
  if (!raw) return []
  try { const arr = JSON.parse(raw); return Array.isArray(arr) ? arr : [] }
  catch { return [] }
}

const synonymList = computed(() => parseJsonList(currentReviewWord.value?.synonyms))
const antonymList = computed(() => parseJsonList(currentReviewWord.value?.antonyms))
const collocationList = computed(() => parseJsonList(currentReviewWord.value?.collocations))
const hasRelated = computed(() => synonymList.value.length || antonymList.value.length || collocationList.value.length)

async function loadCards() {
  try {
    const [cardRes, reviewRes] = await Promise.all([
      client.get('/vocab'),
      client.get('/vocab/review-today')
    ])
    cards.value = cardRes.data
    dueCount.value = reviewRes.data.length
    starredCount.value = starred.value.size
  } catch { dueCount.value = 0 }
}

async function generateCards() {
  generating.value = true
  try {
    await client.post('/vocab/generate', { subject_name: genSubject.value, count: genCount.value })
    showGenerate.value = false
    await loadCards()
  } catch (e) {
    alert('生成失败：' + (e.response?.data?.detail || e.message))
  } finally { generating.value = false }
}

async function deleteCard(card) {
  if (!confirm(`确定删除「${card.word}」吗？此操作不可撤销。`)) return
  try { await client.delete(`/vocab/${card.id}`); cards.value = cards.value.filter(c => c.id !== card.id) }
  catch { alert('删除失败') }
  // Refresh due count after deletion
  try { const res = await client.get('/vocab/review-today'); dueCount.value = res.data.length }
  catch { dueCount.value = Math.max(0, dueCount.value - 1) }
}

async function startReview() {
  try {
    const res = await client.get('/vocab/review-today')
    reviewItems.value = res.data
    if (reviewItems.value.length === 0) { alert('今日无待复习'); return }
    reviewIdx.value = 0; revealed.value = false; reviewDone.value = false; reviewMode.value = true
  } catch { alert('加载失败') }
}

function revealCard() { revealed.value = true }

async function rateReview(quality) {
  const item = currentReviewWord.value
  if (!item || ratingBusy.value) return
  ratingBusy.value = true
  try {
    await client.post('/vocab/review', { vocab_card_id: item.vocab_card_id, quality })
    if (reviewIdx.value < reviewItems.value.length - 1) {
      reviewIdx.value++
      revealed.value = false
    } else {
      reviewDone.value = true
      dueCount.value = 0
    }
  } catch (e) {
    console.error('Review submit failed:', e)
    alert('提交失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  } finally {
    ratingBusy.value = false
  }
}

onMounted(loadCards)
</script>
