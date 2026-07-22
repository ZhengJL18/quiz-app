<template>
  <div class="w-64 border-r border-[var(--border-light)] flex flex-col bg-[var(--surface-0)] overflow-hidden hidden sm:flex">
    <div class="px-3 py-2 border-b border-[var(--border-light)] text-xs font-semibold text-[var(--ink-muted)] flex items-center justify-between">
      <span>素材库 ({{ materials.length }})</span>
      <button @click="refresh" class="btn btn-ghost p-1">
        <RefreshCw :size="12" />
      </button>
    </div>
    <div class="flex-1 overflow-y-auto p-2 space-y-1.5">
      <div v-if="materials.length === 0" class="text-xs text-[var(--ink-muted)] text-center py-8">
        暂无素材<br/>在AI助教处点击「摘录」<br/>或从页面选择内容摘取
      </div>
      <div
        v-for="m in materials"
        :key="m.id"
        draggable="true"
        @dragstart="onDragStart($event, m)"
        class="group p-2 rounded border border-[var(--border-light)] bg-white hover:shadow-sm cursor-grab active:cursor-grabbing transition-all text-xs relative"
        :style="{ borderLeftColor: tagColor(m.color_tag), borderLeftWidth: '3px' }"
      >
        <div class="flex items-start gap-1">
          <div class="flex-1 line-clamp-3 text-[var(--ink-primary)]" v-html="renderMarkdown(m.content)" />
          <div class="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 flex-shrink-0">
            <button @click="copyMaterial(m)" class="btn btn-ghost p-0.5 text-[var(--ink-muted)] hover:text-[var(--accent-indigo)]" title="复制">
              <Copy :size="12" />
            </button>
            <button @click="$emit('delete', m.id)" class="btn btn-ghost p-0.5 text-[var(--ink-muted)] hover:text-[var(--error)]" title="删除">
              <X :size="12" />
            </button>
          </div>
        </div>
        <div v-if="m.source_label" class="mt-1 text-[10px] text-[var(--ink-muted)] truncate">
          {{ m.source_label }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RefreshCw, X, Copy } from 'lucide-vue-next'
import { renderMarkdown } from '../../composables/useKaTeX'
import client from '../../api/client'

defineEmits(['drag-start', 'delete'])

const materials = ref([])

onMounted(refresh)
async function refresh() {
  try {
    const res = await client.get('/notes/materials')
    materials.value = res.data
  } catch (e) { console.error('Failed to load materials', e) }
}

function copyMaterial(m) {
  // Extract plain text from HTML content
  const div = document.createElement('div')
  div.innerHTML = m.content
  const text = div.textContent || div.innerText || m.content
  navigator.clipboard.writeText(text).then(() => {
    window.__toast?.success('已复制')
  }).catch(() => {
    window.__toast?.warning('复制失败，请手动选择')
  })
}

function onDragStart(e, material) {
  e.dataTransfer.setData('text/plain', material.content)
  e.dataTransfer.effectAllowed = 'copy'
}

function tagColor(tag) {
  const colors = {
    default: 'var(--border)',
    red: '#ef4444', orange: '#f97316', yellow: '#eab308',
    green: '#22c55e', blue: '#3b82f6', purple: '#a855f7',
  }
  return colors[tag] || colors.default
}

// Expose refresh for parent
defineExpose({ refresh })
</script>
