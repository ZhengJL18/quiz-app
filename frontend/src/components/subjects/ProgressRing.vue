<template>
  <div class="inline-flex items-center gap-2">
    <svg class="transform -rotate-90" :width="size" :height="size" viewBox="0 0 36 36">
      <!-- Background circle -->
      <circle
        cx="18" cy="18" r="15.5"
        fill="none"
        :stroke="trackColor"
        stroke-width="3"
      />
      <!-- Progress arc -->
      <circle
        cx="18" cy="18" r="15.5"
        fill="none"
        :stroke="progressColor"
        stroke-width="3"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        class="transition-all duration-700 ease-out"
        :style="{ transitionDuration: `${animated ? 700 : 0}ms` }"
      />
    </svg>
    <div v-if="showLabel" class="flex flex-col leading-tight">
      <span class="text-lg font-semibold" :style="{ color: progressColor }">{{ Math.round(percent) }}%</span>
      <span class="text-xs text-[var(--ink-muted)]">{{ label }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  percent: { type: Number, default: 0 },
  size: { type: Number, default: 40 },
  trackColor: { type: String, default: 'var(--border-light)' },
  progressColor: { type: String, default: 'var(--accent)' },
  label: { type: String, default: '' },
  showLabel: { type: Boolean, default: false },
  animated: { type: Boolean, default: true },
})

const circumference = 2 * Math.PI * 15.5
const dashOffset = computed(() => circumference * (1 - Math.min(props.percent, 100) / 100))
</script>
