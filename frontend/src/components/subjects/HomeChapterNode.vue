<template>
  <div>
    <!-- This node -->
    <div class="chapter-row"
         :style="{ paddingLeft: depth * 12 + 8 + 'px' }">
      <div class="chapter-row__main">
        <button v-if="node.children?.length" @click="expanded = !expanded" class="chapter-row__expand">
          <ChevronDown v-if="expanded" :size="14" />
          <ChevronRight v-else :size="14" />
        </button>
        <span v-else class="w-5 flex-shrink-0" />

        <Folder v-if="!node.is_leaf && node.children?.length" :size="14" class="text-[var(--accent)] flex-shrink-0" />
        <FileText v-else-if="node.is_leaf" :size="14" class="text-[var(--ink-muted)] flex-shrink-0" />
        <Folder v-else :size="14" class="text-[var(--ink-muted)] flex-shrink-0" />

        <span class="flex-1 truncate text-sm font-medium text-[var(--ink-primary)]">{{ node.name }}</span>

        <span v-if="node.is_leaf" class="text-xs text-[var(--ink-muted)] flex-shrink-0 desktop-only">{{ node.question_count || 0 }}题</span>
        <span v-if="node.is_leaf && node.mastery" class="flex items-center gap-0.5 flex-shrink-0 ml-1">
          <span v-for="s in 5" :key="s" class="text-[10px]"
            :class="s <= (node.mastery.star_level || 0) ? 'text-[var(--warning)]' : 'text-[var(--border)]'">★</span>
        </span>

        <!-- Actions: desktop=inline, mobile=full-width below -->
        <span v-if="node.is_leaf" class="chapter-row__actions">
          <button @click="$emit('startLesson', node)" class="btn btn-outline text-xs py-1.5 px-3">讲义</button>
          <button @click="$emit('startPure', node)" class="btn btn-outline text-xs py-1.5 px-3">刷题</button>
        </span>
      </div>
    </div>

    <!-- Hints -->
    <div v-if="!node.children?.length && !node.is_leaf && depth > 0"
         class="text-xs text-[var(--ink-muted)] py-1"
         :style="{ paddingLeft: depth * 12 + 40 + 'px' }">暂无子章节</div>
    <div v-if="node.is_leaf && (!node.question_count && !node.mastery)"
         class="text-xs text-[var(--ink-muted)] py-1"
         :style="{ paddingLeft: depth * 12 + 40 + 'px' }">暂无题目 · 点击一课一练生成</div>

    <!-- Children -->
    <div v-if="expanded && node.children?.length">
      <HomeChapterNode v-for="child in node.children" :key="child.id"
        :node="child" :depth="depth + 1"
        @startLesson="$emit('startLesson', $event)"
        @startPure="$emit('startPure', $event)" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ChevronDown, ChevronRight, Folder, FileText } from 'lucide-vue-next'

defineProps({ node: Object, depth: { type: Number, default: 0 } })
defineEmits(['startLesson', 'startPure'])

const expanded = ref(true)
</script>

<style scoped>
.chapter-row {
  padding: 4px 8px;
  margin-bottom: 2px;
  border-radius: 8px;
  transition: background 0.15s;
}
.chapter-row:hover { background: var(--surface-1); }
.chapter-row__main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  flex-wrap: wrap;
}
.chapter-row__expand {
  width: 20px; height: 20px;
  display: flex; align-items: center; justify-content: center;
  border: none; background: none; color: var(--ink-muted);
  cursor: pointer; flex-shrink: 0;
}
.chapter-row__actions {
  display: flex;
  gap: 6px;
}

/* Desktop (>=640px): actions inline, never wrap */
@media (min-width: 640px) {
  .chapter-row__actions {
    margin-left: 8px;
    flex-shrink: 0;
  }
  .chapter-row__main { flex-wrap: nowrap; }
  .desktop-only { display: inline; }
}

/* Mobile (<640px): actions full-width on new line */
@media (max-width: 639px) {
  .chapter-row__actions {
    width: 100%;
    margin-top: 6px;
    padding-left: 25px;
  }
  .chapter-row__actions .btn { flex: 1; }
  .desktop-only { display: none; }
  .chapter-row { padding: 6px 4px; }
  .chapter-row__expand { width: 28px; height: 28px; }
}
</style>
