<template>
  <button
    class="w-full text-left px-4 py-3.5 rounded-lg border transition-all duration-200 group relative overflow-hidden"
    :class="optionClasses"
    :disabled="disabled"
    @click="$emit('select', value)"
  >
    <div class="flex items-start gap-3">
      <!-- Selection indicator -->
      <div
        class="flex-shrink-0 w-6 h-6 mt-0.5 rounded-full border-2 flex items-center justify-center transition-all duration-200"
        :class="indicatorClasses"
      >
        <svg v-if="isSelected && !showResult" class="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <svg v-else-if="showResult && isCorrect" class="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <svg v-else-if="showResult && isSelected && !isCorrect" class="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </div>

      <!-- Label -->
      <div class="flex-1 min-w-0">
        <span class="text-sm font-medium mr-2" :class="labelClasses">{{ labelKey }}.</span>
        <span class="text-sm" :class="textClasses">{{ label }}</span>
      </div>

      <!-- Result icon -->
      <div v-if="showResult && isCorrect" class="flex-shrink-0">
        <svg class="w-5 h-5 text-[var(--success)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      </div>
    </div>
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: String, required: true },
  label: { type: String, required: true },
  labelKey: { type: String, default: '' },
  isSelected: { type: Boolean, default: false },
  isCorrect: { type: Boolean, default: false },
  showResult: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

defineEmits(['select'])

const optionClasses = computed(() => {
  if (props.showResult) {
    if (props.isCorrect) return 'border-[var(--success)] bg-[var(--success-soft)] cursor-default'
    if (props.isSelected && !props.isCorrect) return 'border-[var(--error)] bg-[var(--error-soft)] animate-shake cursor-default'
    return 'border-[var(--border-light)] bg-white/50 cursor-default opacity-60'
  }
  if (props.isSelected) return 'border-[var(--ink-primary)] bg-[var(--surface-1)] shadow-sm'
  return 'border-[var(--border-light)] bg-white hover:border-[var(--ink-primary)] hover:bg-[var(--surface-1)] cursor-pointer'
})

const indicatorClasses = computed(() => {
  if (props.showResult) {
    if (props.isCorrect) return 'border-[var(--success)] bg-[var(--success)]'
    if (props.isSelected && !props.isCorrect) return 'border-[var(--error)] bg-[var(--error)]'
    return 'border-[var(--border)] bg-transparent'
  }
  if (props.isSelected) return 'border-[var(--ink-primary)] bg-[var(--ink-primary)]'
  return 'border-[var(--border)] bg-transparent group-hover:border-[var(--ink-muted)]'
})

const labelClasses = computed(() => {
  if (props.showResult && props.isCorrect) return 'text-[var(--success)]'
  if (props.showResult && props.isSelected && !props.isCorrect) return 'text-[var(--error)]'
  return 'text-[var(--ink-muted)]'
})

const textClasses = computed(() => {
  if (props.showResult) {
    if (props.isCorrect) return 'text-[var(--ink-primary)]'
    if (props.isSelected && !props.isCorrect) return 'text-[var(--error)]'
    return 'text-[var(--ink-muted)]'
  }
  return 'text-[var(--ink-primary)]'
})
</script>
