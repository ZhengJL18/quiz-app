<template>
  <div class="struct-card rounded-xl overflow-hidden border border-[var(--border-light)] bg-[var(--surface-card)] shadow-sm">
    <!-- Topic header -->
    <div v-if="data.topic" class="px-4 py-2.5 bg-[var(--accent-indigo-soft)] border-b border-[var(--border-light)]">
      <div class="flex items-center gap-2">
        <BookOpen :size="14" class="text-[var(--accent-indigo)]" />
        <span class="text-xs font-semibold text-[var(--accent-indigo)]">{{ data.topic }}</span>
      </div>
    </div>

    <div class="p-4 space-y-3 text-sm">
      <!-- What is this -->
      <div v-if="data.what_is_this || data.understanding" class="struct-row">
        <span class="struct-label">📌 理解</span>
        <span class="text-[var(--ink-primary)]">{{ data.what_is_this || data.understanding }}</span>
      </div>

      <!-- Formula -->
      <div v-if="data.formula || data.latex" class="struct-row">
        <span class="struct-label">📐 公式</span>
        <span class="text-[var(--ink-primary)] font-mono" v-html="rendered(data.formula || data.latex)" />
      </div>

      <!-- Steps -->
      <div v-if="data.steps && data.steps.length" class="struct-block">
        <span class="struct-label block mb-1.5">🧠 步骤</span>
        <div v-for="(s, i) in data.steps" :key="i" class="flex gap-2 mb-1">
          <span class="text-[var(--accent-indigo)] font-bold text-xs mt-0.5 flex-shrink-0">{{ i + 1 }}.</span>
          <span class="text-[var(--ink-primary)]">{{ s }}</span>
        </div>
      </div>

      <!-- Key idea / Intuition -->
      <div v-if="data.key_idea || data.intuition" class="struct-row">
        <span class="struct-label">💡 {{ data.intuition ? '直觉' : '思路' }}</span>
        <span class="text-[var(--ink-primary)]">{{ data.key_idea || data.intuition }}</span>
      </div>

      <!-- Common mistakes -->
      <div v-if="data.mistakes || (data.common_traps && data.common_traps.length)" class="struct-block">
        <span class="struct-label block mb-1.5">⚠️ 易错</span>
        <template v-if="data.common_traps">
          <div v-for="(t, i) in data.common_traps" :key="i" class="text-[var(--ink-secondary)] text-xs mb-0.5">
            · {{ t }}
          </div>
        </template>
        <span v-else class="text-[var(--ink-secondary)] text-xs">{{ data.mistakes }}</span>
      </div>

      <!-- Similar problems -->
      <div v-if="data.similar_problems && data.similar_problems.length" class="struct-block">
        <span class="struct-label block mb-1">🔄 同类题</span>
        <div v-for="(p, i) in data.similar_problems" :key="i" class="text-xs text-[var(--ink-muted)] font-mono mb-0.5">
          {{ p }}
        </div>
      </div>

      <!-- Summary -->
      <div v-if="data.summary" class="pt-2 border-t border-[var(--border-light)]">
        <span class="text-xs text-[var(--ink-muted)]">{{ data.summary }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { BookOpen } from 'lucide-vue-next'
import { renderMarkdown } from '../../composables/useKaTeX'

defineProps({ data: { type: Object, default: () => ({}) } })

function rendered(text) { return renderMarkdown(text || '') }
</script>
