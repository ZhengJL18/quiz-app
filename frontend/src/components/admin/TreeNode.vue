<template>
  <div>
    <!-- Directory -->
    <div v-if="node.type === 'dir'" @click="expanded = !expanded"
      class="flex items-center gap-1.5 py-1 px-1.5 rounded cursor-pointer hover:bg-[var(--surface-1)] text-xs transition-colors select-none"
      :style="{ paddingLeft: (depth * 16 + 4) + 'px' }">
      <ChevronRight :size="12" class="text-[var(--ink-muted)] flex-shrink-0 transition-transform" :class="expanded ? 'rotate-90' : ''" />
      <Folder :size="13" class="text-[var(--warning)] flex-shrink-0" />
      <span class="text-[var(--ink-primary)] truncate">{{ node.name }}</span>
    </div>
    <!-- Children -->
    <div v-if="node.type === 'dir' && expanded">
      <TreeNode
        v-for="child in node.children" :key="child.name"
        :node="child" :depth="depth + 1"
        :selectedPath="selectedPath"
        :parentPath="parentPath ? parentPath + '/' + node.name : node.name"
        @select="(n) => $emit('select', n)"
      />
    </div>

    <!-- File -->
    <div v-else-if="node.type === 'file'" @click="handleClick"
      class="flex items-center gap-1.5 py-1 px-1.5 rounded cursor-pointer hover:bg-[var(--surface-1)] text-xs transition-colors"
      :style="{ paddingLeft: (depth * 16 + 20) + 'px' }"
      :class="isSelected ? 'bg-[var(--accent-indigo-soft)] text-[var(--accent-indigo)] font-medium' : 'text-[var(--ink-secondary)]'">
      <FileText :size="13" class="flex-shrink-0" :class="isSelected ? 'text-[var(--accent-indigo)]' : 'text-[var(--ink-muted)]'" />
      <span class="truncate flex-1">{{ node.name }}</span>
      <span v-if="node.size" class="text-[10px] text-[var(--ink-muted)] flex-shrink-0 ml-1">{{ formatSize(node.size) }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Folder, FileText, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  selectedPath: { type: String, default: '' },
  parentPath: { type: String, default: '' },
})

const emit = defineEmits(['select'])

const expanded = ref(props.depth < 1)

const fullPath = computed(() => {
  return props.parentPath ? props.parentPath + '/' + props.node.name : props.node.name
})

const isSelected = computed(() => {
  return props.selectedPath === fullPath.value
})

function handleClick() {
  emit('select', { ...props.node, path: fullPath.value })
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}
</script>
