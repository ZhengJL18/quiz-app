<template>
  <span v-if="starLevel === 0" class="inline-flex items-center gap-1 text-xs text-[var(--ink-muted)] font-medium">
    <div class="w-1.5 h-1.5 rounded-full bg-[var(--ink-muted)] animate-pulse" />
    评估中
  </span>
  <span v-else class="inline-flex items-center" :title="`掌握度 ${Math.round(score)} 分`">
    <span
      v-for="i in 5"
      :key="i"
      class="text-sm transition-all duration-300"
      :class="i <= starLevel ? 'text-[var(--warning)]' : 'text-[var(--border)]'"
      :style="{ animationDelay: `${(i - 1) * 0.06}s` }"
    >
      {{ i <= starLevel ? '★' : '☆' }}
    </span>
  </span>
</template>

<script setup>
defineProps({
  starLevel: { type: Number, default: 0 },
  score: { type: Number, default: 0 },
})
</script>
