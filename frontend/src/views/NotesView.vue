<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--border-light)]">
      <div class="flex items-center gap-3">
        <button @click="$router.back()" class="btn btn-ghost p-1">
          <ArrowLeft :size="18" />
        </button>
        <input
          v-model="noteTitle"
          @blur="saveTitle"
          class="text-lg font-semibold bg-transparent border-none outline-none text-[var(--ink-primary)] min-w-0"
          placeholder="无标题笔记"
        />
      </div>
      <div class="flex items-center gap-2">
        <!-- Save button -->
        <button @click="saveNow" :disabled="saving" class="btn btn-outline text-xs py-1 px-3 gap-1" title="保存">
          <Save v-if="!saving" :size="14" />
          <Loader v-else :size="14" class="animate-spin" />
          <span class="hidden sm:inline">{{ dirty ? '保存' : '已保存' }}</span>
        </button>
        <!-- Edit/Preview toggle -->
        <button @click="previewMode = !previewMode" class="btn text-xs py-1 px-3 gap-1"
          :class="previewMode ? 'btn-primary' : 'btn-outline'">
          <Eye v-if="!previewMode" :size="14" />
          <FileText v-else :size="14" />
          <span class="hidden sm:inline">{{ previewMode ? '编辑' : '预览' }}</span>
        </button>
        <button @click="aiWrite" :disabled="aiBusy" class="btn btn-outline text-xs py-1 px-3">
          <Sparkles :size="14" />
          <span class="hidden sm:inline ml-1">AI 编写</span>
        </button>
        <button @click="deleteNote" class="btn btn-ghost text-xs py-1 px-2 text-[var(--error)]">
          <Trash2 :size="14" />
        </button>
      </div>
    </div>

    <div class="flex-1 flex overflow-hidden">
      <!-- Material Library Sidebar -->
      <MaterialLibrary
        @drag-start="onDragStart"
        @delete="deleteMaterial"
      />

      <!-- Editor / Preview Area -->
      <div class="note-editor-area flex-1 flex flex-col overflow-hidden">
        <!-- EDIT MODE -->
        <textarea
          v-if="!previewMode"
          ref="editorRef"
          v-model="noteContent"
          @input="markDirty"
          class="flex-1 w-full p-6 sm:p-8 resize-none border-none outline-none text-[15px] leading-relaxed font-mono bg-[var(--surface-0)] text-[var(--ink-primary)]"
          placeholder="开始写笔记... 支持 Markdown 和 LaTeX ($...$ 或 $$...$$)

从左侧素材库拖入内容，或点击右上角 AI 编写"
          @drop="onDrop"
          @dragover.prevent
        />
        <!-- AI streaming indicator -->
        <div v-if="aiBusy && !previewMode" class="px-6 py-2 text-xs text-[var(--ink-muted)] flex items-center gap-2 bg-[var(--surface-1)]">
          <Loader :size="14" class="animate-spin" />
          AI 正在编写...
        </div>

        <!-- PREVIEW MODE -->
        <div v-else-if="previewMode" class="flex-1 overflow-y-auto">
          <div v-if="!noteContent.trim()" class="p-16 text-center text-[var(--ink-muted)]">
            <FileText :size="40" class="mx-auto mb-3 opacity-30" />
            <p>暂无内容，点击「编辑」开始写作</p>
          </div>
          <article
            v-else
            class="prose prose-slate max-w-3xl mx-auto px-6 sm:px-10 py-8 note-preview"
            v-html="renderedContent"
          />
        </div>
      </div>
    </div>

    <!-- Quick AI instruction dialog -->
    <Teleport to="body">
      <div v-if="showAiDialog" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" @click.self="showAiDialog=false">
        <div class="card p-6 w-full max-w-md space-y-4">
          <h3 class="font-semibold text-lg">AI 编写笔记</h3>
          <textarea v-model="aiInstruction" rows="3" class="input w-full resize-y"
            placeholder="例如：根据素材库整理成结构化笔记、补充例题、翻译成英文..." />
          <div class="flex gap-2 justify-end">
            <button @click="showAiDialog=false" class="btn btn-ghost">取消</button>
            <button @click="doAiWrite" :disabled="!aiInstruction.trim()" class="btn btn-primary">
              开始生成
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ArrowLeft, Sparkles, Trash2, Loader, Eye, FileText, Save } from 'lucide-vue-next'
import MaterialLibrary from '../components/notes/MaterialLibrary.vue'
import { renderMarkdown } from '../composables/useKaTeX'
import client from '../api/client'

const route = useRoute()
const router = useRouter()

const noteId = ref(null)
const noteTitle = ref('')
const noteContent = ref('')
const aiBusy = ref(false)
const showAiDialog = ref(false)
const aiInstruction = ref('')
const previewMode = ref(false)
const dirty = ref(false)
const saving = ref(false)
const loaded = ref(false)
let saveTimer = null

const renderedContent = computed(() => {
  try { return renderMarkdown(noteContent.value) }
  catch { return '<p>渲染出错</p>' }
})

onMounted(async () => {
  // Wait for route to fully resolve (transition may delay it)
  await nextTick()
  const id = parseInt(route.params.id)
  if (!isNaN(id)) noteId.value = id
  if (noteId.value) {
    try {
      const res = await client.get(`/notes/${noteId.value}`)
      noteTitle.value = res.data.title || '无标题笔记'
      noteContent.value = res.data.content || ''
    } catch (e) {
      console.error('Load note failed', e)
    }
  }
  loaded.value = true
})

function markDirty() {
  dirty.value = true
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => saveNow(), 1000)
}

// Save before navigating away (critical fix!)
onBeforeRouteLeave((to, from, next) => {
  if (dirty.value && noteId.value) {
    saveNow().finally(() => next())
  } else {
    next()
  }
})

// Also save on page unload
onBeforeUnmount(() => {
  if (dirty.value && noteId.value) saveNow()
})

function saveTitle() {
  if (!noteId.value) return
  client.put(`/notes/${noteId.value}`, { title: noteTitle.value }).catch(() => {})
}

async function saveNow() {
  if (!noteId.value || saving.value) return
  saving.value = true
  try {
    await client.put(`/notes/${noteId.value}`, { title: noteTitle.value, content: noteContent.value })
    dirty.value = false
    setTimeout(() => { if (!dirty.value) saving.value = false }, 600)
  } catch (e) {
    console.error('Save failed', e)
    saving.value = false
  }
}

watch(noteContent, () => {
  if (noteId.value && loaded.value) markDirty()
})

async function deleteNote() {
  if (!noteId.value || !confirm('删除此笔记？')) return
  try {
    await client.delete(`/notes/${noteId.value}`)
    router.push('/notes')
  } catch (e) { console.error(e) }
}

function aiWrite() {
  if (!noteId.value) {
    createNoteThenAi()
    return
  }
  showAiDialog.value = true
}

async function createNoteThenAi() {
  try {
    const res = await client.post('/notes', { title: noteTitle.value || '无标题笔记', content: noteContent.value })
    noteId.value = res.data.id
    router.replace(`/notes/${res.data.id}`)
    showAiDialog.value = true
  } catch (e) { console.error(e) }
}

async function doAiWrite() {
  if (!aiInstruction.value.trim() || !noteId.value) return
  showAiDialog.value = false
  aiBusy.value = true
  previewMode.value = false
  noteContent.value = ''
  try {
    const token = localStorage.getItem('token')
    const resp = await fetch(`http://43.139.179.58/api/v1/notes/ai-write`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ note_id: noteId.value, instruction: aiInstruction.value }),
    })
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      for (const line of buffer.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6))
            if (d.chunk) noteContent.value += d.chunk
            else if (d.error) noteContent.value = '> ❌ ' + d.error
          } catch {}
        }
      }
      buffer = buffer.includes('\n') ? buffer.split('\n').pop() : ''
    }
    dirty.value = true
    saveNow()
  } catch (e) {
    noteContent.value = '> ❌ AI 写入失败: ' + e.message
  } finally {
    aiBusy.value = false
    aiInstruction.value = ''
  }
}

function onDrop(e) {
  const data = e.dataTransfer.getData('text/plain')
  if (!data) return
  const textarea = e.target
  const start = textarea.selectionStart
  noteContent.value = noteContent.value.slice(0, start) + data + '\n\n' + noteContent.value.slice(start)
  markDirty()
}

function onDragStart(e, material) {
  e.dataTransfer.setData('text/plain', material.content)
}

async function deleteMaterial(id) {
  try {
    await client.delete(`/notes/materials/${id}`)
  } catch (e) { console.error(e) }
}
</script>

<style scoped>
/* ── Note preview: eye-friendly reading ── */
.note-preview {
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', system-ui, -apple-system, sans-serif;
  font-size: 16px;
  line-height: 1.85;
  color: var(--ink-primary);
  word-break: break-word;
  letter-spacing: 0.01em;
}

.note-preview :deep(h1),
.note-preview :deep(h2),
.note-preview :deep(h3) {
  font-family: inherit;
  margin-top: 1.8em;
  margin-bottom: 0.6em;
  line-height: 1.4;
}

.note-preview :deep(h1) { font-size: 1.6em; }
.note-preview :deep(h2) { font-size: 1.3em; }
.note-preview :deep(h3) { font-size: 1.15em; }

.note-preview :deep(p) {
  margin-bottom: 1em;
}

.note-preview :deep(strong) {
  color: var(--ink-primary);
}

.note-preview :deep(blockquote) {
  border-left: 3px solid var(--accent-indigo);
  background: var(--accent-indigo-soft);
  padding: 0.6em 1em;
  margin: 1em 0;
  border-radius: 0 6px 6px 0;
  font-style: normal;
  color: var(--ink-secondary);
}

.note-preview :deep(code) {
  background: var(--surface-2);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.note-preview :deep(pre) {
  background: var(--surface-2);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1em 0;
}

.note-preview :deep(pre code) {
  background: none;
  padding: 0;
}

.note-preview :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}

.note-preview :deep(th),
.note-preview :deep(td) {
  border: 1px solid var(--border-light);
  padding: 0.5em 0.8em;
  text-align: left;
}

.note-preview :deep(th) {
  background: var(--surface-2);
  font-weight: 600;
}

.note-preview :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-light);
  margin: 2em 0;
}

.note-preview :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.note-preview :deep(a) {
  color: var(--accent-indigo);
  text-decoration: underline;
}

@media (max-width: 640px) {
  .note-preview {
    font-size: 15px;
    line-height: 1.75;
    padding: 0 16px;
  }
}
</style>
