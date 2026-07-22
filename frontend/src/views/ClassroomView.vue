<template>
  <div class="max-w-5xl mx-auto px-4 py-6 animate-fade-in-up">
    <h1 class="text-xl font-bold text-[var(--ink-primary)] mb-1 flex items-center gap-2">
      <Headphones :size="20" class="text-[var(--accent-indigo)]" /> 听课模式
    </h1>
    <p class="text-xs text-[var(--ink-muted)] mb-6">录音 · 笔记 · 拍照 → 一键生成课堂笔记</p>

    <div class="classroom-grid grid grid-cols-1 lg:grid-cols-2 gap-4" :style="{ paddingBottom: keyboardPad + 'px' }">
      <!-- Card 1+2: 录音 + 转写文本 -->
      <div class="card p-5 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-[var(--ink-primary)] flex items-center gap-1.5">
            <span class="w-6 h-6 rounded-md bg-[var(--error-soft)] flex items-center justify-center">
              <Mic :size="13" class="text-[var(--error)]" />
            </span> 录音
          </h3>
          <span v-if="recordingTime" class="text-xs font-mono text-[var(--error)] animate-pulse">{{ recordingTime }}</span>
        </div>
        <div class="flex gap-2 mb-3">
          <button v-if="!recording" @click="startRecording" class="btn btn-outline text-xs flex-1 gap-1 recording-btn"
            :disabled="generating">
            <Mic :size="15" /> 开始录音
          </button>
          <button v-else @click="stopRecording" class="btn text-xs flex-1 gap-1 bg-[var(--error)] text-white recording-btn">
            <Square :size="15" /> 停止 ({{ formatTime(elapsed) }})
          </button>
          <button @click="triggerAudioUpload" class="btn btn-ghost recording-btn-icon" title="上传录音">
            <Upload :size="16" />
          </button>
          <input ref="audioInput" type="file" accept="audio/*" @change="handleAudioUpload" class="hidden" />
        </div>
        <!-- Transcript -->
        <div class="flex-1">
          <textarea v-model="transcript" ref="transcriptRef" placeholder="录音转写结果会出现在这里。你也可以手动输入或粘贴..."
            class="w-full flex-1 min-h-[120px] sm:min-h-[200px] p-3 resize-y border border-[var(--border-light)] rounded-lg text-sm leading-relaxed bg-[var(--surface-0)] outline-none focus:border-[var(--accent-indigo)] transition-colors"
            :disabled="generating" />
        </div>
        <div v-if="transcribing" class="mt-2 text-xs text-[var(--ink-muted)] flex items-center gap-1">
          <Loader :size="12" class="animate-spin" /> 转写中...
        </div>
      </div>

      <!-- Card 3: 图片 -->
      <div class="card p-5 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-[var(--ink-primary)] flex items-center gap-1.5">
            <span class="w-6 h-6 rounded-md bg-[var(--accent-indigo-soft)] flex items-center justify-center">
              <Image :size="13" class="text-[var(--accent-indigo)]" />
            </span> 课堂图片 ({{ images.length }}/10)
          </h3>
          <div class="flex gap-1">
            <button @click="triggerImageUpload" class="btn btn-ghost recording-btn-icon" :disabled="images.length >= 10 || generating" title="上传图片">
              <Upload :size="16" />
            </button>
            <button @click="triggerCamera" class="btn btn-ghost recording-btn-icon" :disabled="images.length >= 10 || generating" title="拍照">
              <Camera :size="16" />
            </button>
            <input ref="imageInput" type="file" accept="image/*" multiple @change="handleImages" class="hidden" />
            <input ref="cameraInput" type="file" accept="image/*" capture="environment" @change="handleImages" class="hidden" />
          </div>
        </div>
        <!-- Image grid -->
        <div v-if="images.length === 0" class="flex-1 flex items-center justify-center border-2 border-dashed border-[var(--border-light)] rounded-lg p-8">
          <p class="text-xs text-[var(--ink-muted)] text-center">
            点击 📷 拍照 或 📤 上传<br/>
            黑板照片、PPT截图、手写笔记
          </p>
        </div>
        <div v-else class="flex-1 overflow-y-auto">
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <div v-for="(img, i) in images" :key="i" class="relative group">
              <img :src="img.preview" class="w-full h-24 object-cover rounded-lg border border-[var(--border-light)]" />
              <button @click="images.splice(i, 1)" class="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/50 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-sm">
                &times;
              </button>
            </div>
            <button v-if="images.length < 10" @click="triggerImageUpload"
              class="h-24 rounded-lg border-2 border-dashed border-[var(--border-light)] flex items-center justify-center text-[var(--ink-muted)] hover:border-[var(--accent-indigo)] transition-colors">
              <Plus :size="20" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Card 4: 一键生成（移动端 sticky 底部） -->
    <div ref="generateRef" class="mt-4 card p-5" :class="{'mobile-sticky-bottom': isMobile}" :style="{ paddingBottom: isMobile ? 'calc(0.75rem + env(safe-area-inset-bottom, 0px))' : '' }">
      <div class="flex items-center gap-4">
        <div class="flex-1 min-w-0">
          <h3 class="text-sm font-semibold text-[var(--ink-primary)]">🔮 一键生成课堂笔记</h3>
          <p class="text-xs text-[var(--ink-muted)] mt-1 truncate">
            {{ hasContent ? `已有：${transcript ? '录音转写 ' : ''}${images.length ? images.length + '张图片 ' : ''}` : '请先添加录音或图片' }}
          </p>
        </div>
        <button @click="generateNotes" :disabled="!hasContent || generating"
          class="btn btn-primary text-sm py-2.5 px-6 gap-2 shadow-lg flex-shrink-0"
          :class="generating ? 'opacity-60' : ''">
          <Sparkles v-if="!generating" :size="16" />
          <Loader v-else :size="16" class="animate-spin" />
          {{ generating ? '生成中...' : '生成笔记' }}
        </button>
      </div>
      <!-- Result -->
      <div v-if="result" class="mt-4 p-4 bg-[var(--surface-1)] rounded-lg">
        <article class="note-preview text-sm leading-relaxed" v-html="renderedResult" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Headphones, Mic, Square, Upload, Camera, Plus, Sparkles, Loader, Image } from 'lucide-vue-next'
import { renderMarkdown } from '../composables/useKaTeX'

// ── Recording ──
const recording = ref(false)
const elapsed = ref(0)
const recordingTime = ref('')
let mediaRecorder = null
let audioChunks = []
let recordingTimer = null

function formatTime(s) {
  const m = Math.floor(s / 60); const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    audioChunks = []
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop())
      processRecording()
    }
    mediaRecorder.start()
    recording.value = true
    elapsed.value = 0
    recordingTimer = setInterval(() => { elapsed.value++; recordingTime.value = formatTime(elapsed.value) }, 1000)
    recordingTime.value = '0:00'
  } catch { window.__toast?.error('无法访问麦克风') }
}

function stopRecording() {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.stop(); recording.value = false
    clearInterval(recordingTimer)
  }
}

// ── Upload ──
const transcribing = ref(false)
const transcript = ref('')
const images = ref([])
const generating = ref(false)
const result = ref('')
const audioInput = ref(null); const imageInput = ref(null); const cameraInput = ref(null)
const transcriptRef = ref(null)
const generateRef = ref(null)

// ── Mobile responsiveness & keyboard avoidance ──
const isMobile = ref(window.innerWidth < 640)
const keyboardPad = ref(0)

function updateViewport() {
  isMobile.value = window.innerWidth < 640
  if (typeof visualViewport !== 'undefined') {
    const diff = window.innerHeight - visualViewport.height
    keyboardPad.value = Math.max(0, diff > 100 ? diff - 20 : 0)
  }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  if (typeof visualViewport !== 'undefined') {
    visualViewport.addEventListener('resize', updateViewport)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateViewport)
  if (typeof visualViewport !== 'undefined') {
    visualViewport.removeEventListener('resize', updateViewport)
  }
})

const hasContent = computed(() => transcript.value.trim() || images.value.length > 0)
const renderedResult = computed(() => {
  try { return renderMarkdown(result.value) } catch { return '<p>渲染失败</p>' }
})

function triggerAudioUpload() { audioInput.value?.click() }
function triggerImageUpload() { imageInput.value?.click() }
function triggerCamera() { cameraInput.value?.click() }

async function handleAudioUpload(e) {
  const file = e.target.files?.[0]; if (!file) return
  transcribing.value = true
  try {
    const token = localStorage.getItem('token')
    const form = new FormData(); form.append('file', file)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/process-file', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
    const data = await resp.json()
    if (resp.ok) transcript.value = (transcript.value ? transcript.value + '\n\n' : '') + data.text
    else window.__toast?.error(data.detail || '转写失败')
  } catch { window.__toast?.error('上传失败') }
  finally { transcribing.value = false; if (audioInput.value) audioInput.value.value = '' }
}

async function processRecording() {
  if (!audioChunks.length) return
  transcribing.value = true
  const blob = new Blob(audioChunks, { type: 'audio/webm' })
  const file = new File([blob], 'recording.webm', { type: 'audio/webm' })
  try {
    const token = localStorage.getItem('token')
    const form = new FormData(); form.append('file', file)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/process-file', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
    const data = await resp.json()
    if (resp.ok) transcript.value = (transcript.value ? transcript.value + '\n\n' : '') + data.text
    else window.__toast?.error(data.detail || '转写失败')
  } catch { window.__toast?.error('处理失败') }
  finally { transcribing.value = false }
}

async function handleImages(e) {
  const files = Array.from(e.target.files || [])
  for (const file of files) {
    if (images.value.length >= 10) break
    const preview = await new Promise(resolve => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.readAsDataURL(file)
    })
    images.value.push({ file, preview })
  }
  if (imageInput.value) imageInput.value.value = ''
  if (cameraInput.value) cameraInput.value.value = ''
}

async function generateNotes() {
  if (!hasContent.value || generating.value) return
  generating.value = true; result.value = ''
  try {
    const token = localStorage.getItem('token')
    const form = new FormData()
    form.append('transcript', transcript.value)
    form.append('notes', '')
    form.append('course_name', '课堂笔记')
    for (const img of images.value) form.append('images', img.file)
    const resp = await fetch('http://43.139.179.58/api/v1/agent/generate-class-notes', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    })
    if (!resp.ok) { const err = await resp.json(); throw new Error(err.detail) }
    const reader = resp.body.getReader(); const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break; buf += decoder.decode(value, { stream: true })
      for (const line of buf.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            if (d.chunk) result.value += d.chunk
            else if (d.error) result.value = '> ❌ ' + d.error
          } catch {}
        }
      }
      buf = buf.includes('\n') ? buf.split('\n').pop() : ''
    }
  } catch (e) { result.value = '> ❌ 生成失败: ' + (e.message || '未知错误') }
  finally { generating.value = false }
}
</script>

<style scoped>
/* ── Recording buttons: 44px+ touch targets on mobile ── */
.recording-btn {
  min-height: 44px;
  padding: 0.5rem 1rem;
}
.recording-btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
  border-radius: var(--radius-md);
  color: var(--ink-secondary);
  background: transparent;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.recording-btn-icon:hover {
  border-color: var(--ink-primary);
  color: var(--ink-primary);
  background: var(--surface-1);
}
.recording-btn-icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

/* ── Mobile sticky bottom generator ── */
.mobile-sticky-bottom {
  position: sticky;
  bottom: 0;
  z-index: 20;
  margin-top: 1rem;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
  border-bottom: none;
  background: var(--surface-card);
}

/* ── Mobile overrides ── */
@media (max-width: 640px) {
  .recording-btn {
    padding: 0.625rem 0.875rem;
  }
  .mobile-sticky-bottom {
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    padding-top: 1rem;
  }
  /* Image delete button always visible on touch devices */
  .relative.group .absolute.top-1.right-1 {
    opacity: 1;
    width: 28px;
    height: 28px;
  }
}
</style>
