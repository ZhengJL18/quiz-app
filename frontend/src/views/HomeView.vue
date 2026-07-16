<template>
  <div class="max-w-4xl mx-auto px-4 py-8 animate-fade-in-up">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] mb-1">学习中心</h1>
      <p class="text-[var(--ink-muted)] text-sm">选择科目与章节，开始练习</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--ink-primary)]">{{ subjects.length }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">科目</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--accent)]">{{ totalChapters }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">章节</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--accent-indigo)]">{{ totalQuestions }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">题目</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-[var(--warning)]">{{ masteredPercent }}%</div>
        <div class="text-xs text-[var(--ink-muted)] mt-1">掌握率</div>
      </div>
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
          : 'bg-white text-[var(--ink-secondary)] border border-[var(--border-light)] hover:border-[var(--ink-primary)] hover:text-[var(--ink-primary)]'"
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

    <!-- Chapter tree -->
    <div v-else class="space-y-3 stagger">
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

        <!-- Level 2 & 3: Sections & Lessons -->
        <transition name="expand">
          <div v-if="expandedChapters.has(ch1.id)" class="border-t border-[var(--border-light)]">
            <div v-for="ch2 in ch1.children" :key="ch2.id">
              <!-- Level 2: Section header -->
              <div class="px-5 py-2.5 bg-[var(--surface-1)] flex items-center gap-2">
                <div class="w-1 h-4 rounded-full bg-[var(--accent-indigo)]" />
                <span class="text-sm font-medium text-[var(--ink-secondary)]">{{ ch2.name }}</span>
                <span class="text-xs text-[var(--ink-muted)]">{{ ch2.children?.length || 0 }} 课时</span>
              </div>

              <!-- Level 3: Lessons -->
              <div v-for="ch3 in ch2.children" :key="ch3.id"
                class="flex items-center gap-3 px-5 py-3 hover:bg-[var(--surface-1)] transition-colors border-t border-[var(--border-light)]/50"
              >
                <!-- Icon -->
                <div class="w-7 h-7 rounded-md bg-[var(--surface-2)] flex items-center justify-center flex-shrink-0">
                  <FileText :size="14" class="text-[var(--ink-muted)]" />
                </div>

                <!-- Name + Stars -->
                <div class="flex-1 min-w-0 flex items-center gap-2">
                  <span class="text-sm text-[var(--ink-primary)] truncate">{{ ch3.name }}</span>
                  <MasteryStars
                    :star-level="ch3.mastery?.star_level || 0"
                    :score="ch3.mastery?.mastery_score || 0"
                  />
                </div>

                <!-- Actions -->
                <div class="flex items-center gap-1.5 flex-shrink-0">
                  <button
                    @click="startLesson(ch3)"
                    :disabled="practicing"
                    class="px-3 py-1.5 text-xs font-medium rounded-md bg-[var(--ink-primary)] text-white
                           hover:bg-[#2a2a3e] transition-colors disabled:opacity-40 flex items-center gap-1"
                  >
                    <Play :size="12" />
                    一课一练
                  </button>
                  <button
                    @click="startPure(ch3)"
                    :disabled="practicing"
                    class="px-3 py-1.5 text-xs font-medium rounded-md border border-[var(--border)] text-[var(--ink-secondary)]
                           hover:border-[var(--ink-primary)] hover:text-[var(--ink-primary)] hover:bg-[var(--surface-1)]
                           transition-all disabled:opacity-40 flex items-center gap-1"
                  >
                    <Zap :size="12" />
                    刷题
                  </button>
                </div>
              </div>

              <!-- Empty lesson list -->
              <div v-if="!ch2.children?.length" class="px-5 py-4 text-center text-xs text-[var(--ink-muted)]">
                暂无线时内容
              </div>
            </div>

            <!-- Empty section list -->
            <div v-if="!ch1.children?.length" class="px-5 py-8 text-center text-sm text-[var(--ink-muted)]">
              暂无章节内容
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, Folder, FileText, ChevronDown, Play, Zap, Loader } from 'lucide-vue-next'
import client from '../api/client'
import { usePracticeStore } from '../stores/practice'
import MasteryStars from '../components/subjects/MasteryStars.vue'

const router = useRouter()
const practiceStore = usePracticeStore()

const subjects = ref([])
const selectedSubject = ref(null)
const chapterTree = ref([])
const expandedChapters = ref(new Set())
const loading = ref(false)
const practicing = ref(false)

// Computed stats
const totalChapters = computed(() => {
  let count = 0
  for (const ch1 of chapterTree.value) {
    for (const ch2 of (ch1.children || [])) {
      count += (ch2.children || []).length
    }
  }
  return count
})

const totalQuestions = computed(() => {
  let count = 0
  for (const ch1 of chapterTree.value) {
    for (const ch2 of (ch1.children || [])) {
      for (const ch3 of (ch2.children || [])) {
        count += ch3.question_count || 0
      }
    }
  }
  return count
})

const masteredPercent = computed(() => {
  let total = 0, mastered = 0
  for (const ch1 of chapterTree.value) {
    for (const ch2 of (ch1.children || [])) {
      for (const ch3 of (ch2.children || [])) {
        if (ch3.mastery) {
          total++
          if (ch3.mastery.star_level >= 3) mastered++
        }
      }
    }
  }
  return total > 0 ? Math.round((mastered / total) * 100) : 0
})

onMounted(async () => {
  try {
    const res = await client.get('/subjects')
    subjects.value = res.data
    if (subjects.value.length > 0) {
      selectSubject(subjects.value[0])
    }
  } catch (e) {
    console.error('Failed to load subjects', e)
  }
})

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
