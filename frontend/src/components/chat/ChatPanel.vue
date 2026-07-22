<template>
  <!-- Floating AI Window -->
  <Teleport to="body">
    <div v-if="chatStore.open && $route.path !== '/ai'" class="ai-float" :class="{ 'ai-float--fs': isFullScreen }"
      :style="floatStyle"
      @mousedown="bringToFront">
      <!-- Header (drag handle) -->
      <div class="ai-float__header" @mousedown.prevent="startDrag" @touchstart.prevent="startDragTouch">
        <div class="flex items-center gap-1.5 min-w-0">
          <Sparkles :size="15" class="text-[var(--accent-indigo)] flex-shrink-0" />
          <span class="text-xs font-medium truncate">{{ chatStore.activeConvo?.title || 'AI 助教' }}</span>
        </div>
        <div class="flex items-center gap-0.5 flex-shrink-0">
          <!-- Model selector -->
          <div class="relative">
            <button @click="showModelMenu = !showModelMenu"
              class="ai-float__btn text-[10px] font-medium gap-0.5 px-1.5 w-auto" title="切换模型">
              <Cpu :size="12" />
              <span>{{ currentModel.label }}</span>
              <ChevronDown :size="10" :class="showModelMenu ? 'rotate-180' : ''" />
            </button>
            <div v-if="showModelMenu" class="absolute top-full right-0 mt-1 w-40 bg-[var(--surface-card)] border border-[var(--border-light)] rounded-lg shadow-xl z-50 py-1">
              <button v-for="m in models" :key="m.id" @click="selectModel(m); showModelMenu = false"
                class="w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--surface-1)] flex items-center gap-2"
                :class="currentModel.id === m.id ? 'text-[var(--accent-indigo)] font-medium' : 'text-[var(--ink-secondary)]'">
                <span class="w-2 h-2 rounded-full" :class="m.id === 'deepseek' ? 'bg-[var(--accent-indigo)]' : m.id === 'kimi' ? 'bg-emerald-400' : m.id === 'doubao' ? 'bg-cyan-400' : 'bg-purple-400'"
                  :style="{ opacity: (m.id === 'deepseek' || modelKeys[m.id]) ? 1 : 0.25 }" />
                {{ m.label }}
                <span v-if="m.id !== 'deepseek' && !modelKeys[m.id]" class="text-[9px] text-[var(--ink-muted)] ml-auto">未配</span>
              </button>
            </div>
          </div>
          <button @click="chatStore.newConversation()" :disabled="chatStore.sending"
            class="ai-float__btn" title="新对话">
            <Plus :size="13" />
          </button>
          <button @click="showConvoList = !showConvoList"
            class="ai-float__btn relative" title="历史">
            <MessageSquare :size="13" />
          </button>
          <button @click="isFullScreen = !isFullScreen" class="ai-float__btn" title="全屏">
            <Minimize2 v-if="isFullScreen" :size="13" />
            <Maximize2 v-else :size="13" />
          </button>
          <button @click="chatStore.toggle()" class="ai-float__btn ai-float__close" title="关闭">
            <X :size="14" />
          </button>
        </div>
      </div>

      <!-- Conversation list -->
      <div v-if="showConvoList" class="ai-float__convos">
        <div v-if="chatStore.loading" class="p-4 text-center text-xs text-[var(--ink-muted)]">
          <Loader :size="12" class="inline animate-spin mr-1" /> 加载中...
        </div>
        <div v-else-if="chatStore.convos.length === 0" class="p-4 text-center text-xs text-[var(--ink-muted)]">
          暂无历史对话
        </div>
        <div v-for="c in chatStore.convos" :key="c.id"
          @click="chatStore.switchConversation(c.id); showConvoList = false"
          class="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-[var(--surface-1)]"
          :class="String(c.id) === String(chatStore.activeId) ? 'bg-[var(--surface-1)] font-medium' : 'text-[var(--ink-secondary)]'">
          <MessageSquare :size="12" class="flex-shrink-0" />
          <span class="flex-1 truncate">{{ c.title }}</span>
          <button @click.stop="chatStore.deleteConversation(c.id)" class="text-[var(--ink-muted)] hover:text-[var(--error)] p-0.5">
            <X :size="10" />
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div ref="msgContainer" class="ai-float__messages">
        <div v-if="chatStore.messages.length === 0 && !chatStore.streamingContent" class="py-12 text-center">
          <Sparkles :size="28" class="mx-auto text-[var(--ink-muted)] mb-3 opacity-40" />
          <p class="text-xs text-[var(--ink-muted)]">AI 学习助教 · {{ currentModel.label }}</p>
        </div>

        <div v-for="(msg, i) in chatStore.messages" :key="i">
          <!-- Tool call -->
          <div v-if="msg.role === 'tool'" class="flex justify-start mb-2">
            <div class="max-w-[88%] rounded-lg px-2.5 py-1 text-[11px] cursor-pointer select-none bg-[var(--surface-2)] text-[var(--ink-muted)]"
              :class="msg.status === 'error' ? '!bg-[var(--error-soft)] !text-[var(--error)]' : ''"
              @click="msg._expanded = !msg._expanded">
              <div class="flex items-center gap-1">
                <Loader v-if="msg.status === 'running'" :size="10" class="animate-spin" />
                <Wrench v-else :size="10" />
                <span class="truncate">{{ msg.label || msg.tool }}</span>
                <span v-if="msg.status === 'running'" class="opacity-60">...</span>
              </div>
            </div>
          </div>
          <div v-else class="flex flex-col mb-2" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
            <div class="max-w-[88%] rounded-xl px-3 py-2 text-[13px] leading-relaxed"
              :class="msg.role === 'user' ? 'bg-[var(--ink-primary)] text-white' : 'bg-[var(--surface-1)] text-[var(--ink-primary)]'">
              <!-- Card mode -->
              <div v-if="msg._cardMode && msg.role === 'assistant'" class="struct-card-mini">
                <div v-for="(section, si) in parseCardSections(msg.content)" :key="si" class="mb-2 last:mb-0">
                  <div class="text-xs font-semibold text-[var(--accent-indigo)] mb-0.5">{{ section.emoji }} {{ section.label }}</div>
                  <div class="text-xs text-[var(--ink-secondary)]" v-html="rendered(section.body)" />
                </div>
              </div>
              <!-- Normal mode -->
              <div v-else v-html="rendered(msg.content)" />
            </div>
            <!-- Card toggle button (only for assistant messages with structure) -->
            <button v-if="msg.role === 'assistant' && hasCardStructure(msg.content) && !msg._greeting"
              @click="msg._cardMode = !msg._cardMode"
              class="mt-1 text-[10px] px-2 py-0.5 rounded-full border border-[var(--border-light)] text-[var(--ink-muted)] hover:text-[var(--accent-indigo)] hover:border-[var(--accent-indigo)] transition-colors">
              {{ msg._cardMode ? '📝 原文' : '📋 卡片视图' }}
            </button>
          </div>
        </div>

        <div v-if="chatStore.streamingContent" class="flex justify-start mb-2">
          <div class="max-w-[88%] rounded-xl px-3 py-2 text-[13px] leading-relaxed bg-[var(--surface-1)]">
            <div v-html="rendered(chatStore.streamingContent)" />
            <span class="inline-block w-1.5 h-4 bg-[var(--ink-primary)] ml-0.5 animate-pulse align-middle" />
          </div>
        </div>

        <div v-if="chatStore.sending && !chatStore.streamingContent" class="flex justify-start">
          <div class="bg-[var(--surface-1)] rounded-xl px-3 py-2 flex items-center gap-2 text-xs text-[var(--ink-muted)]">
            <Loader :size="12" class="animate-spin" /> 思考中...
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="ai-float__input">
        <!-- Attached files chips -->
        <div v-if="uploadedFiles.length" class="flex flex-wrap gap-1.5 mb-2">
          <div v-for="(uf, i) in uploadedFiles" :key="i"
            class="flex items-center gap-1 px-2 py-1 rounded-md bg-[var(--surface-1)] border border-[var(--border-light)] text-xs">
            <img v-if="uf.preview" :src="uf.preview" class="w-5 h-5 rounded object-cover" />
            <span v-else class="text-[10px]">📎</span>
            <span class="text-[var(--ink-secondary)] truncate max-w-[100px]">{{ uf.name }}</span>
            <button @click="uploadedFiles.splice(i, 1)" class="text-[var(--ink-muted)] hover:text-[var(--error)]">&times;</button>
          </div>
        </div>
        <!-- Processing indicator -->
        <div v-if="fileProcessing" class="flex items-center gap-2 mb-2 px-1 text-xs text-[var(--ink-muted)]">
          <Loader :size="12" class="animate-spin" /> 处理中...
        </div>
        <div class="flex gap-1.5">
          <!-- File attach button -->
          <button @click="triggerFileInput" :disabled="chatStore.sending || fileProcessing"
            class="px-2 py-1.5 rounded-lg border border-[var(--border-light)] text-[var(--ink-muted)] hover:text-[var(--accent-indigo)] hover:border-[var(--accent-indigo)] transition-colors"
            title="添加文件">
            <Paperclip :size="15" />
          </button>
          <input ref="fileInput" type="file" @change="handleFile" class="hidden"
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.bmp,.txt,.md,.py,.cpp,.c,.java,.js,.ts,.html,.css,.json,.xml,.yaml,.yml,.mp3,.wav,.m4a,.ogg,.webm" />
          <input ref="inputRef" v-model="input" @keydown.enter="sendMsg" type="text"
            placeholder="问AI... 可上传图片/PDF/代码"
            class="flex-1 bg-[var(--surface-0)] border border-[var(--border-light)] rounded-lg px-3 py-1.5 text-[13px] outline-none focus:border-[var(--accent-indigo)] transition-colors"
            :disabled="chatStore.sending" />
          <button v-if="chatStore.sending" @click="chatStore.stop()"
            class="px-3 py-1.5 rounded-lg bg-[var(--error)] text-white text-xs font-medium">
            停止
          </button>
          <button v-else @click="sendMsg" :disabled="!input.trim()"
            class="px-3 py-1.5 rounded-lg bg-[var(--ink-primary)] text-white text-xs font-medium disabled:opacity-40">
            <Send :size="13" />
          </button>
        </div>
      </div>

      <!-- Resize handle -->
      <div v-if="!isFullScreen" class="ai-float__resize" @mousedown.prevent="startResize" />
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { Sparkles, X, Loader, Send, Plus, MessageSquare, StopCircle, Maximize2, Minimize2, Wrench, Cpu, ChevronDown, Paperclip } from 'lucide-vue-next'
import { useChatStore } from '../../stores/chat'
import { useAuthStore } from '../../stores/auth'
import { renderMarkdown } from '../../composables/useKaTeX'

const chatStore = useChatStore()
const authStore = useAuthStore()

// ── Model selection ──
const models = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'kimi', label: 'Kimi' },
  { id: 'doubao', label: '豆包' },
  { id: 'qwen', label: '千问' },
]
const currentModel = ref(models.find(m => m.id === (localStorage.getItem('ai_model') || 'deepseek')) || models[0])
const showModelMenu = ref(false)
const modelKeys = ref({})  // Which optional keys are configured

async function loadModelKeyStatus() {
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch('http://43.139.179.58/api/v1/agent/model-keys', { headers: { Authorization: `Bearer ${token}` } })
    if (resp.ok) modelKeys.value = await resp.json()
  } catch { /* ok */ }
}

function selectModel(m) {
  currentModel.value = m
  localStorage.setItem('ai_model', m.id)
  // Warn if key not configured
  if (m.id !== 'deepseek' && !modelKeys.value[m.id]) {
    window.__toast?.warning(`${m.label} 的 API Key 未配置。请在设置中配置后使用。`)
  }
}

// ── Floating window state ──
const STORAGE_KEY = 'ai_float_state'
const isMobile = ref(window.innerWidth < 640)
const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
// Mobile default: 90vw x 70vh centered; Desktop default: 420w x 520h, top-right
const floatX = ref(saved.x ?? (isMobile.value ? Math.round(window.innerWidth * 0.05) : window.innerWidth - 440))
const floatY = ref(saved.y ?? (isMobile.value ? Math.round(window.innerHeight * 0.15) : window.innerHeight - 580))
const floatW = ref(saved.w ?? (isMobile.value ? Math.round(window.innerWidth * 0.9) : 420))
const floatH = ref(saved.h ?? (isMobile.value ? Math.round(window.innerHeight * 0.7) : 520))
const isFullScreen = ref(false)
const zIndex = ref(100)
let zCounter = 100

window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 768
  if (!isFullScreen.value) {
    floatX.value = Math.min(floatX.value, window.innerWidth - 100)
    floatY.value = Math.min(floatY.value, window.innerHeight - 60)
    floatW.value = Math.min(floatW.value, window.innerWidth - 20)
  }
})

function bringToFront() {
  zIndex.value = ++zCounter
}

function saveFloatState() {
  if (!isFullScreen.value) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ x: floatX.value, y: floatY.value, w: floatW.value, h: floatH.value }))
  }
}

const floatStyle = computed(() => {
  if (isFullScreen.value) return { zIndex: zIndex.value }
  return {
    left: floatX.value + 'px', top: floatY.value + 'px',
    width: floatW.value + 'px', height: floatH.value + 'px',
    zIndex: zIndex.value,
  }
})

// ── Drag ──
let dragState = null
function startDrag(e) {
  if (isFullScreen.value) return
  dragState = { sx: e.clientX, sy: e.clientY, ox: floatX.value, oy: floatY.value }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}
function onDrag(e) {
  if (!dragState) return
  floatX.value = Math.max(0, Math.min(window.innerWidth - 100, dragState.ox + e.clientX - dragState.sx))
  floatY.value = Math.max(0, Math.min(window.innerHeight - 60, dragState.oy + e.clientY - dragState.sy))
}
function stopDrag() {
  dragState = null
  saveFloatState()
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDragTouch)
  document.removeEventListener('touchend', stopDragTouch)
}

// Touch drag (mobile)
function startDragTouch(e) {
  if (isFullScreen.value || !e.touches.length) return
  const t = e.touches[0]
  dragState = { sx: t.clientX, sy: t.clientY, ox: floatX.value, oy: floatY.value }
  document.addEventListener('touchmove', onDragTouch, { passive: false })
  document.addEventListener('touchend', stopDragTouch)
}
function onDragTouch(e) {
  if (!dragState || !e.touches.length) return
  e.preventDefault()
  const t = e.touches[0]
  floatX.value = Math.max(0, Math.min(window.innerWidth - 100, dragState.ox + t.clientX - dragState.sx))
  floatY.value = Math.max(0, Math.min(window.innerHeight - 60, dragState.oy + t.clientY - dragState.sy))
}
function stopDragTouch() {
  dragState = null
  saveFloatState()
  document.removeEventListener('touchmove', onDragTouch)
  document.removeEventListener('touchend', stopDragTouch)
}

// ── Resize ──
let resizeState = null
function startResize(e) {
  if (isFullScreen.value) return
  resizeState = { sx: e.clientX, sy: e.clientY, ow: floatW.value, oh: floatH.value }
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}
function onResize(e) {
  if (!resizeState) return
  floatW.value = Math.max(320, Math.min(window.innerWidth - floatX.value, resizeState.ow + e.clientX - resizeState.sx))
  floatH.value = Math.max(400, Math.min(window.innerHeight - floatY.value, resizeState.oh + e.clientY - resizeState.sy))
}
function stopResize() {
  resizeState = null
  saveFloatState()
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

// ── Greeting ──
let hasOpened = false
watch(() => chatStore.open, (isOpen) => {
  if (isOpen && !hasOpened) {
    hasOpened = true
    chatStore.maybeAutoGreet()
    bringToFront()
  }
})

// ── Pre-fill input (called from selection toolbar) ──
const input = ref('')
const inputRef = ref(null)
function prefillAndOpen(text) {
  if (!chatStore.open) chatStore.open = true
  bringToFront()
  input.value = text
  nextTick(() => inputRef.value?.focus())
}

// Expose for global access
if (typeof window !== 'undefined') {
  window.__askAI = (text) => prefillAndOpen(text)
}

const msgContainer = ref(null)
const showConvoList = ref(false)

watch(() => authStore.user?.id, async (uid) => {
  if (uid) {
    await chatStore.initForUser(uid)
    chatStore.maybeGreet()
    loadModelKeyStatus()
  }
}, { immediate: true })

function rendered(text) { return renderMarkdown(text || '') }

// Card structure detection
const CARD_MARKERS = ['📌', '📐', '🧠', '💡', '⚠️', '🔄']
const MARKER_LABELS = { '📌': '理解', '📐': '公式', '🧠': '步骤', '💡': '思路', '⚠️': '易错', '🔄': '同类题' }

function hasCardStructure(content) {
  try { return typeof content === 'string' && CARD_MARKERS.some(m => content.includes(m)) }
  catch { return false }
}

function parseCardSections(content) {
  try {
    if (!content || typeof content !== 'string') return []
    const sections = []
    const lines = content.split('\n')
    let current = null
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      // Match lines like "📌 **理解**：text" or "📌 理解：text"
      const m = trimmed.match(/^([📌📐🧠💡⚠️🔄])\s*(?:\*\*?)?(.+?)(?:\*?\*)?\s*[:：]\s*(.*)/)
      if (m) {
        if (current) sections.push(current)
        const label = MARKER_LABELS[m[1]] || m[2].replace(/\*+/g, '').trim()
        current = { emoji: m[1], label, body: m[3] || '' }
      } else if (current) {
        current.body += '\n' + trimmed
      }
    }
    if (current) sections.push(current)
    return sections.length > 0 ? sections : []
  } catch { return [] }
}

// ── File upload ──
const fileInput = ref(null)
const fileProcessing = ref(false)
const uploadedFiles = ref([])  // { name, text, preview }

function triggerFileInput() { fileInput.value?.click() }

async function handleFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  fileProcessing.value = true

  // Create preview for images
  let preview = ''
  if (file.type.startsWith('image/')) {
    preview = await new Promise(resolve => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.readAsDataURL(file)
    })
  }

  try {
    const token = localStorage.getItem('token')
    const form = new FormData()
    form.append('file', file)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/process-file', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    })
    if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail || '处理失败') }
    const data = await resp.json()
    uploadedFiles.value.push({ name: file.name, text: data.text, preview })
    window.__toast?.success('已添加')
  } catch (e) {
    window.__toast?.error(e.message?.slice(0, 60) || '处理失败')
  } finally {
    fileProcessing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function sendMsg() {
  const text = input.value.trim()
  if ((!text && uploadedFiles.value.length === 0) || chatStore.sending) return

  // Build message with attached files
  let fullText = text
  if (uploadedFiles.value.length) {
    const fileTexts = uploadedFiles.value.map(uf => uf.text).filter(Boolean).join('\n\n')
    fullText = fileTexts + (text ? '\n\n---\n' + text : '')
  }

  input.value = ''
  uploadedFiles.value = []
  await chatStore.send(fullText, currentModel.value.id)
  await nextTick()
  if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
}

watch(
  () => chatStore.messages.length + (chatStore.streamingContent || '').length,
  async () => {
    await nextTick()
    if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
)

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDragTouch)
  document.removeEventListener('touchend', stopDragTouch)
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
.ai-float {
  position: fixed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface-card);
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.18), 0 1px 3px rgba(0,0,0,0.08);
  overflow: hidden;
  border: 1px solid var(--border-light);
  transition: border-radius 0.2s;
}
.ai-float--fs {
  top: 0 !important; left: 0 !important;
  width: 100vw !important; height: 100vh !important;
  border-radius: 0;
  border: none;
  z-index: 9999;
}
.ai-float__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface-1);
  cursor: grab;
  user-select: none;
  flex-shrink: 0;
}
.ai-float__header:active { cursor: grabbing; }
.ai-float__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: 6px;
  color: var(--ink-muted);
  background: none;
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.ai-float__btn:hover { background: var(--surface-2); color: var(--ink-primary); }
.ai-float__btn:disabled { opacity: 0.4; cursor: default; }
.ai-float__convos {
  border-bottom: 1px solid var(--border-light);
  max-height: 180px;
  overflow-y: auto;
  overscroll-behavior: contain;
  flex-shrink: 0;
}
.ai-float__messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 10px 12px;
}
.ai-float__input {
  padding: 8px 12px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}
.ai-float__resize {
  position: absolute;
  bottom: 0; right: 0;
  width: 16px; height: 16px;
  cursor: nwse-resize;
  background: linear-gradient(135deg, transparent 50%, var(--border-light) 50%, transparent 54%);
  opacity: 0;
  transition: opacity 0.2s;
}
.ai-float:hover .ai-float__resize { opacity: 1; }

/* Prevent clipped HTML from rendering huge */
.ai-float__messages :deep(h1) { font-size: 1.15em !important; margin: 0.5em 0; }
.ai-float__messages :deep(h2) { font-size: 1.1em !important; }
.ai-float__messages :deep(h3) { font-size: 1.05em !important; }
.ai-float__messages :deep(*) { max-font-size: 15px; }
.ai-float__messages :deep([style*='font-size']) { font-size: inherit !important; }

.struct-card-mini {
  padding: 2px 0;
}

/* ── Mobile optimizations ── */
@media (max-width: 639px) {
  .ai-float {
    border-radius: 16px 16px 0 0 !important;
    min-width: 100vw !important;
  }
  .ai-float__header {
    padding: 12px 14px;  /* taller drag handle */
    min-height: 48px;
  }
  .ai-float__btn {
    width: 36px; height: 36px;
  }
  .ai-float__btn svg {
    width: 16px;
    height: 16px;
  }
  /* Close button: extra large for easy tap */
  .ai-float__close {
    width: 42px;
    height: 42px;
    margin-left: 2px;
  }
  .ai-float__close svg {
    width: 20px;
    height: 20px;
  }
  .ai-float__resize {
    width: 28px; height: 28px;
  }
  .ai-float__input {
    padding: 10px 14px;
    padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  }
  .ai-float__input input {
    font-size: 16px !important; /* prevent iOS zoom */
  }
  .ai-float__messages {
    padding: 8px 14px;
  }
}

@media (max-width: 380px) {
  .ai-float__header { padding: 10px 10px; min-height: 44px; }
  .ai-float__messages { padding: 6px 10px; }
  .ai-float__input { padding: 6px 10px; padding-bottom: calc(6px + env(safe-area-inset-bottom, 0px)); }
}
</style>
