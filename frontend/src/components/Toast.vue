<template>
  <TransitionGroup name="toast" tag="div" class="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 pointer-events-none">
    <div v-for="t in toasts" :key="t.id"
      class="pointer-events-auto px-4 py-3 rounded-xl shadow-lg text-sm font-medium max-w-sm animate-slide-up flex items-center gap-2"
      :class="t.type === 'error' ? 'bg-[var(--error)] text-white' :
              t.type === 'success' ? 'bg-[var(--success)] text-white' :
              t.type === 'warning' ? 'bg-[var(--warning)] text-white' :
              'bg-[var(--ink-primary)] text-white'">
      <CheckCircle v-if="t.type === 'success'" :size="16" />
      <AlertCircle v-else-if="t.type === 'error'" :size="16" />
      <span class="flex-1">{{ t.message }}</span>
      <button @click="remove(t.id)" class="opacity-70 hover:opacity-100">&times;</button>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { ref } from 'vue'
import { CheckCircle, AlertCircle } from 'lucide-vue-next'

const toasts = ref([])
let nextId = 0

function show(message, type = 'info', duration = 4000) {
  const id = ++nextId
  toasts.value.push({ id, message, type })
  if (duration > 0) setTimeout(() => remove(id), duration)
}

function remove(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

function success(msg) { show(msg, 'success') }
function error(msg) { show(msg, 'error', 6000) }
function warning(msg) { show(msg, 'warning') }
function info(msg) { show(msg, 'info') }

defineExpose({ success, error, warning, info })

// Make available globally so any component can use it
if (typeof window !== 'undefined') window.__toast = { success, error, warning, info }
</script>

<style scoped>
.toast-enter-active { transition: all 0.3s ease-out; }
.toast-leave-active { transition: all 0.2s ease-in; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }

.animate-slide-up {
  animation: slideUp 0.3s ease-out;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
