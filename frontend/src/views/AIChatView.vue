<template>
  <div class="flex flex-col" style="height: calc(100vh - 56px)">
    <!-- Header -->
    <div class="ai-full-header flex items-center justify-between px-4 py-2 border-b border-[var(--border-light)] bg-[var(--surface-1)] flex-shrink-0">
      <div class="flex items-center gap-2 min-w-0">
        <Sparkles :size="16" class="text-[var(--accent-indigo)]" />
        <span class="text-sm font-medium truncate">{{ chatStore.activeConvo?.title || 'AI 助教' }}</span>
      </div>
      <div class="flex items-center gap-1 flex-shrink-0">
        <div class="relative">
          <button @click="showModelMenu = !showModelMenu"
            class="btn btn-ghost text-xs py-1 px-2 gap-1" title="切换模型">
            <Cpu :size="13" />
            <span>{{ currentModel.label }}</span>
            <ChevronDown :size="10" />
          </button>
          <div v-if="showModelMenu" class="absolute top-full right-0 mt-1 w-40 bg-[var(--surface-card)] border border-[var(--border-light)] rounded-lg shadow-xl z-50 py-1">
            <button v-for="m in models" :key="m.id" @click="selectModel(m); showModelMenu = false"
              class="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--surface-1)] flex items-center gap-2"
              :class="currentModel.id === m.id ? 'text-[var(--accent-indigo)] font-medium' : 'text-[var(--ink-secondary)]'">
              <span class="w-2 h-2 rounded-full" :style="{ opacity: (m.id === 'deepseek' || modelKeys[m.id]) ? 1 : 0.25 }" :class="m.id === 'deepseek' ? 'bg-[var(--accent-indigo)]' : m.id === 'kimi' ? 'bg-emerald-400' : m.id === 'doubao' ? 'bg-cyan-400' : 'bg-purple-400'" />
              {{ m.label }}
            </button>
          </div>
        </div>
        <button @click="chatStore.newConversation()" :disabled="chatStore.sending" class="btn btn-ghost text-xs py-1 px-2">新对话</button>
      </div>
    </div>

    <!-- Messages -->
    <div ref="msgContainer" class="flex-1 overflow-y-auto px-4 sm:px-8 py-4 space-y-4 max-w-3xl mx-auto w-full">
      <div v-if="chatStore.messages.length === 0 && !chatStore.streamingContent" class="py-20 text-center">
        <Sparkles :size="36" class="mx-auto text-[var(--ink-muted)] mb-4 opacity-30" />
        <p class="text-sm text-[var(--ink-muted)]">AI 学习助教 · {{ currentModel.label }}</p>
        <p class="text-xs text-[var(--ink-muted)] mt-1">上传图片/PDF/音频，或直接提问</p>
      </div>

      <div v-for="(msg, i) in chatStore.messages" :key="i">
        <div v-if="msg.role === 'tool'" class="flex justify-start mb-2">
          <div class="rounded-lg px-2.5 py-1 text-xs bg-[var(--surface-2)] text-[var(--ink-muted)]">{{ msg.label || msg.tool }}</div>
        </div>
        <div v-else class="flex mb-2" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
          <div class="max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed"
            :class="msg.role === 'user' ? 'bg-[var(--ink-primary)] text-white' : 'bg-[var(--surface-1)] text-[var(--ink-primary)]'">
            <div v-html="rendered(msg.content)" />
          </div>
        </div>
      </div>

      <div v-if="chatStore.streamingContent" class="flex justify-start mb-2">
        <div class="max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed bg-[var(--surface-1)]">
          <div v-html="rendered(chatStore.streamingContent)" />
          <span class="inline-block w-1.5 h-4 bg-[var(--ink-primary)] ml-0.5 animate-pulse align-middle" />
        </div>
      </div>

      <div v-if="chatStore.sending && !chatStore.streamingContent" class="flex justify-start">
        <div class="bg-[var(--surface-1)] rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm text-[var(--ink-muted)]">
          <Loader :size="14" class="animate-spin" /> 思考中...
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="border-t border-[var(--border-light)] px-4 sm:px-8 py-3 flex-shrink-0">
      <div class="max-w-3xl mx-auto">
        <!-- Files -->
        <div v-if="uploadedFiles.length" class="flex flex-wrap gap-1.5 mb-2">
          <div v-for="(uf, i) in uploadedFiles" :key="i" class="flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--surface-1)] border border-[var(--border-light)] text-xs">
            <img v-if="uf.preview" :src="uf.preview" class="w-5 h-5 rounded object-cover" />
            <span v-else class="text-[10px]">📎</span>
            <span class="text-[var(--ink-secondary)] truncate max-w-[100px]">{{ uf.name }}</span>
            <button @click="uploadedFiles.splice(i, 1)" class="text-[var(--ink-muted)] hover:text-[var(--error)]">&times;</button>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="triggerFileInput" :disabled="chatStore.sending || fileProcessing" class="btn btn-ghost p-2" title="添加文件"><Paperclip :size="16" /></button>
          <input ref="fileInput" type="file" @change="handleFile" class="hidden" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.bmp,.txt,.md,.mp3,.wav,.m4a,.ogg,.webm" />
          <input ref="inputRef" v-model="input" @keydown.enter="sendMsg" type="text" placeholder="问AI..."
            class="flex-1 bg-[var(--surface-0)] border border-[var(--border-light)] rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--accent-indigo)] transition-colors"
            :disabled="chatStore.sending" />
          <button v-if="chatStore.sending" @click="chatStore.stop()" class="btn bg-[var(--error)] text-white text-sm px-4">停止</button>
          <button v-else @click="sendMsg" :disabled="!input.trim() && !uploadedFiles.length" class="btn btn-primary text-sm px-4"><Send :size="16" /></button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { Sparkles, Send, Loader, Cpu, ChevronDown, Paperclip } from 'lucide-vue-next'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
import { renderMarkdown } from '../composables/useKaTeX'

const chatStore = useChatStore()
const authStore = useAuthStore()

const input = ref('')
const inputRef = ref(null)
const msgContainer = ref(null)
const fileInput = ref(null)
const fileProcessing = ref(false)
const uploadedFiles = ref([])
const showModelMenu = ref(false)

const models = [
  { id: 'deepseek', label: 'DeepSeek' }, { id: 'kimi', label: 'Kimi' },
  { id: 'doubao', label: '豆包' }, { id: 'qwen', label: '千问' },
]
const currentModel = ref(models.find(m => m.id === (localStorage.getItem('ai_model') || 'deepseek')) || models[0])
const modelKeys = ref({})

function selectModel(m) {
  currentModel.value = m; localStorage.setItem('ai_model', m.id)
  if (m.id !== 'deepseek' && !modelKeys.value[m.id]) window.__toast?.warning(`${m.label} API Key 未配置`)
}

async function loadModelKeyStatus() {
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch('http://43.139.179.58/api/v1/agent/model-keys', { headers: { Authorization: `Bearer ${token}` } })
    if (resp.ok) modelKeys.value = await resp.json()
  } catch {}
}

function rendered(text) { return renderMarkdown(text || '') }

function triggerFileInput() { fileInput.value?.click() }

async function handleFile(e) {
  const file = e.target.files?.[0]; if (!file) return
  fileProcessing.value = true
  let preview = ''
  if (file.type.startsWith('image/')) {
    preview = await new Promise(resolve => { const r = new FileReader(); r.onload = () => resolve(r.result); r.readAsDataURL(file) })
  }
  try {
    const token = localStorage.getItem('token'); const form = new FormData(); form.append('file', file)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/process-file', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
    if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail) }
    const data = await resp.json()
    uploadedFiles.value.push({ name: file.name, text: data.text, preview })
  } catch (e) { window.__toast?.error(e.message?.slice(0, 60) || '处理失败') }
  finally { fileProcessing.value = false; if (fileInput.value) fileInput.value.value = '' }
}

async function sendMsg() {
  const text = input.value.trim()
  if ((!text && !uploadedFiles.value.length) || chatStore.sending) return
  let fullText = text
  if (uploadedFiles.value.length) {
    const fileTexts = uploadedFiles.value.map(uf => uf.text).filter(Boolean).join('\n\n')
    fullText = fileTexts + (text ? '\n\n---\n' + text : '')
  }
  input.value = ''; uploadedFiles.value = []
  await chatStore.send(fullText, currentModel.value.id)
  await nextTick()
  if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
}

watch(() => chatStore.messages.length + (chatStore.streamingContent || '').length, async () => {
  await nextTick()
  if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
})

watch(() => authStore.user?.id, async (uid) => {
  if (uid) { await chatStore.initForUser(uid); chatStore.maybeGreet(); loadModelKeyStatus() }
}, { immediate: true })
</script>
