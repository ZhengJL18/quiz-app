<template>
  <div class="max-w-4xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-6 flex items-center gap-3">
      <router-link to="/admin" class="btn btn-ghost text-sm py-1.5 px-3">
        <ArrowLeft :size="16" /> 返回
      </router-link>
      <div>
        <h1 class="text-xl font-bold text-[var(--ink-primary)]">{{ userName }} 的数据</h1>
        <p class="text-xs text-[var(--ink-muted)]">只读模式 · 无法答题</p>
      </div>
    </div>

    <div v-if="loading" class="py-20 text-center">
      <Loader :size="24" class="animate-spin mx-auto text-[var(--ink-muted)]" />
    </div>

    <template v-else>
      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div class="card p-4 text-center">
          <div class="text-xl font-bold text-[var(--ink-primary)]">{{ stats.subjects }}</div>
          <div class="text-xs text-[var(--ink-muted)]">科目</div>
        </div>
        <div class="card p-4 text-center">
          <div class="text-xl font-bold text-[var(--accent)]">{{ stats.chapters }}</div>
          <div class="text-xs text-[var(--ink-muted)]">章节</div>
        </div>
        <div class="card p-4 text-center">
          <div class="text-xl font-bold text-[var(--accent-indigo)]">{{ stats.questions }}</div>
          <div class="text-xs text-[var(--ink-muted)]">题目</div>
        </div>
        <div class="card p-4 text-center">
          <div class="text-xl font-bold text-[var(--error)]">{{ stats.wrongEntries }}</div>
          <div class="text-xs text-[var(--ink-muted)]">错题</div>
        </div>
      </div>

      <!-- Subjects & Chapters -->
      <div class="space-y-3">
        <div v-for="subj in subjects" :key="subj.id" class="card overflow-hidden">
          <div class="px-5 py-3 bg-[var(--surface-1)] flex items-center gap-3">
            <Folder :size="16" class="text-[var(--ink-muted)]" />
            <span class="font-medium text-[var(--ink-primary)]">{{ subj.name }}</span>
            <span class="text-xs text-[var(--ink-muted)]">{{ subj.description }}</span>
          </div>
          <div v-if="subj.chapters?.length" class="divide-y divide-[var(--border-light)]/50">
            <div v-for="ch in flatChapters(subj.chapters)" :key="ch.id"
              class="px-5 py-2.5 flex items-center gap-3 text-sm hover:bg-[var(--surface-1)] transition-colors"
              :style="{ paddingLeft: (ch.level * 20 + 20) + 'px' }">
              <FileText :size="14" class="text-[var(--ink-muted)] flex-shrink-0" />
              <span class="flex-1 truncate text-[var(--ink-secondary)]">{{ ch.name }}</span>
              <MasteryStars v-if="ch.mastery" :star-level="ch.mastery.star_level" :score="ch.mastery.mastery_score" />
              <span class="text-xs text-[var(--ink-muted)]">{{ ch.question_count || 0 }}题</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Loader, Folder, FileText } from 'lucide-vue-next'
import client from '../api/client'
import MasteryStars from '../components/subjects/MasteryStars.vue'

const route = useRoute()
const userId = computed(() => route.params.userId)
const userName = ref('')
const loading = ref(true)
const subjects = ref([])
const stats = ref({ subjects: 0, chapters: 0, questions: 0, wrongEntries: 0 })

function flatChapters(nodes) {
  let flat = []
  for (const n of nodes) {
    flat.push(n)
    if (n.children) flat = flat.concat(flatChapters(n.children))
  }
  return flat
}

onMounted(async () => {
  try {
    const res = await client.get(`/admin/user/${userId.value}`)
    const d = res.data
    userName.value = d.username
    subjects.value = d.subjects
    stats.value = d.stats
  } catch { /* access denied */ }
  finally { loading.value = false }
})
</script>
