<template>
  <div class="max-w-3xl mx-auto px-4 py-8 animate-fade-in-up">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--ink-primary)] flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-[var(--surface-2)] flex items-center justify-center">
          <Settings :size="18" class="text-[var(--ink-secondary)]" />
        </div>
        设置
      </h1>
      <p class="text-[var(--ink-muted)] text-sm ml-12">API 密钥 · 科目管理 · 章节编辑</p>
    </div>

    <!-- ── API KEYS ── -->
    <div class="card p-5 mb-4">
      <h2 class="font-semibold text-[var(--ink-primary)] mb-3">AI 模型密钥</h2>
      <p class="text-xs text-[var(--ink-muted)] mb-4">配置各 AI 模型的 API Key。DeepSeek 为必填，其余可选。密钥加密存储，仅自己可见。</p>
      <div class="space-y-3">
        <div v-for="m in modelKeys" :key="m.id" class="flex items-center gap-3">
          <span class="w-20 text-sm font-medium text-[var(--ink-primary)] flex-shrink-0">
            <span class="w-2 h-2 rounded-full inline-block mr-1.5" :class="m.color" />
            {{ m.label }}
          </span>
          <input :type="m.show ? 'text' : 'password'" v-model="m.value" :placeholder="m.placeholder"
            class="input text-sm flex-1 font-mono" />
          <button @click="m.show = !m.show" class="btn btn-ghost p-1 text-xs" title="显示/隐藏">
            <Eye v-if="!m.show" :size="14" />
            <EyeOff v-else :size="14" />
          </button>
          <button @click="saveModelKey(m)" :disabled="m.saving" class="btn btn-outline text-xs py-1 px-3 flex-shrink-0">
            <Save v-if="!m.saving" :size="12" />
            <Loader v-else :size="12" class="animate-spin" />
            <span class="ml-1">保存</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── SUBJECTS ── -->
    <div class="card p-5 mb-4">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-[var(--ink-primary)]">科目</h2>
        <button @click="showAddSubject = true" class="btn btn-primary text-xs py-1.5 px-3">
          <Plus :size="14" /> 新增
        </button>
      </div>
      <div v-if="showAddSubject" class="mb-4 p-4 bg-[var(--surface-1)] rounded-lg space-y-3">
        <input v-model="newSubject.name" placeholder="科目名称" class="input text-sm" />
        <input v-model="newSubject.description" placeholder="描述" class="input text-sm" />
        <input v-model="newSubject.prompt_style" placeholder="出题风格提示（可选）" class="input text-sm" />
        <div class="flex gap-2">
          <button @click="createSubject" :disabled="!newSubject.name || saving" class="btn btn-primary text-xs py-1.5">确认新增</button>
          <button @click="showAddSubject = false; resetSubjectForm()" class="btn btn-ghost text-xs py-1.5">取消</button>
        </div>
      </div>
      <div class="space-y-1">
        <div v-for="subj in subjects" :key="subj.id" class="flex items-center gap-2 px-3 py-2 rounded hover:bg-[var(--surface-1)] transition-colors text-sm">
          <span class="flex-1 truncate font-medium">{{ subj.name }}</span>
          <span class="text-xs text-[var(--ink-muted)] mr-2">{{ subj.prompt_style || '默认风格' }}</span>
          <button @click="startEditSubject(subj)" class="btn btn-ghost text-xs p-1"><Pencil :size="12" /></button>
          <button @click="deleteSubject(subj)" class="btn btn-ghost text-xs p-1 text-[var(--ink-muted)] hover:text-[var(--error)]"><Trash2 :size="12" /></button>
        </div>
      </div>
      <div v-if="editingSubject" class="mt-3 p-4 bg-[var(--surface-1)] rounded-lg space-y-3">
        <input v-model="editingSubject.name" placeholder="科目名称" class="input text-sm" />
        <input v-model="editingSubject.description" placeholder="描述" class="input text-sm" />
        <input v-model="editingSubject.prompt_style" placeholder="出题风格提示" class="input text-sm" />
        <div class="flex gap-2">
          <button @click="saveSubject" :disabled="saving" class="btn btn-primary text-xs py-1.5">保存</button>
          <button @click="editingSubject = null" class="btn btn-ghost text-xs py-1.5">取消</button>
        </div>
      </div>
    </div>

    <!-- ── CHAPTERS TREE ── -->
    <div class="card p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-[var(--ink-primary)]">章节目录</h2>
        <select v-model="selectedSubjectId" @change="loadChapterTree" class="input text-xs py-1.5 w-auto">
          <option :value="null" disabled>选择科目</option>
          <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <!-- Tree -->
      <div v-if="chapterTree.length > 0" class="space-y-0.5 max-h-[60vh] overflow-y-auto">
        <ChapterTreeNode
          v-for="node in chapterTree" :key="node.id"
          :node="node"
          :subject-id="selectedSubjectId"
          @refresh="loadChapterTree"
        />
      </div>
      <div v-else-if="selectedSubjectId" class="py-8 text-center text-sm text-[var(--ink-muted)]">
        该科目暂无章节，点击下方添加
      </div>
      <div v-else class="py-8 text-center text-sm text-[var(--ink-muted)]">
        请先选择一个科目
      </div>

      <!-- Empty state -->
      <div v-if="selectedSubjectId && chapterTree.length === 0 && !showAddRoot" class="py-6 text-center">
        <p class="text-sm text-[var(--ink-muted)] mb-3">此科目暂无章节</p>
        <button @click="startAddRoot" class="btn btn-outline text-xs py-1.5">
          <Plus :size="14" /> 添加章节
        </button>
      </div>
      <!-- Inline add form -->
      <div v-if="showAddRoot" class="tree-add-form mt-2">
        <input
          ref="rootInput"
          v-model="newChapter.name"
          class="tree-input"
          placeholder="新章节名称..."
          @keydown.enter="createRootChapter"
          @keydown.escape="showAddRoot = false; newChapter.name = ''"
        />
        <span class="text-[10px] text-[var(--ink-muted)] whitespace-nowrap ml-1">Enter 确认</span>
      </div>
      <!-- Bottom add button -->
      <div v-if="selectedSubjectId && chapterTree.length > 0 && !showAddRoot" class="mt-2">
        <button @click="startAddRoot" class="tree-row w-full text-[var(--ink-muted)] hover:text-[var(--ink-primary)]">
          <Plus :size="14" />
          <span class="tree-name">添加章节...</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { Settings, Plus, Pencil, Trash2, Folder, Save, Eye, EyeOff, Loader } from 'lucide-vue-next'
import client from '../api/client'
import ChapterTreeNode from '../components/settings/ChapterTreeNode.vue'

// ── API Keys ──
const modelKeys = ref([
  { id: 'deepseek', label: 'DeepSeek', value: '', show: false, saving: false, placeholder: 'sk-...', color: 'bg-[var(--accent-indigo)]' },
  { id: 'kimi', label: 'Kimi', value: '', show: false, saving: false, placeholder: 'sk-...', color: 'bg-emerald-400' },
  { id: 'doubao', label: '豆包', value: '', show: false, saving: false, placeholder: '输入豆包 API Key', color: 'bg-cyan-400' },
  { id: 'qwen', label: '千问', value: '', show: false, saving: false, placeholder: 'sk-...', color: 'bg-purple-400' },
  { id: 'tencent_asr_id', label: 'ASR SecretId', value: '', show: false, saving: false, placeholder: '腾讯云 SecretId', color: 'bg-orange-400' },
  { id: 'tencent_asr_key', label: 'ASR SecretKey', value: '', show: false, saving: false, placeholder: '腾讯云 SecretKey', color: 'bg-orange-400' },
])

async function loadModelKeys() {
  try {
    const res = await client.get('/agent/model-keys')
    for (const m of modelKeys.value) {
      if (m.id === 'deepseek') continue  // DeepSeek key stored separately
      m.value = res.data[m.id] ? '(已配置)' : ''
    }
  } catch { /* ok */ }
}

async function saveModelKey(m) {
  m.saving = true
  try {
    await client.put('/agent/model-keys', { provider: m.id, api_key: m.value || null })
    m.value = m.value ? '(已配置)' : ''
    window.__toast?.success(`${m.label} 密钥已保存`)
  } catch {
    window.__toast?.error('保存失败')
  } finally { m.saving = false }
}

// ── State ──
const subjects = ref([])
const chapterTree = ref([])
const selectedSubjectId = ref(null)
const saving = ref(false)

// Subject form
const showAddSubject = ref(false)
const editingSubject = ref(null)
const newSubject = ref({ name: '', description: '', prompt_style: '' })

// Chapter form
const showAddRoot = ref(false)
const newChapter = ref({ name: '', level: 3 })

function resetSubjectForm() { newSubject.value = { name: '', description: '', prompt_style: '' } }
function resetChapterForm() { newChapter.value = { name: '', level: 3 } }

// ── Subject CRUD ──
async function loadSubjects() {
  try { const res = await client.get('/subjects'); subjects.value = res.data } catch {/* ok */}
}

async function createSubject() {
  saving.value = true
  try {
    await client.post('/subjects', newSubject.value)
    showAddSubject.value = false; resetSubjectForm(); await loadSubjects()
  } catch (e) { alert('创建失败：' + (e.response?.data?.detail || e.message)) }
  finally { saving.value = false }
}

async function deleteSubject(subj) {
  if (!confirm(`确定删除「${subj.name}」吗？此操作不可撤销。`)) return
  try {
    await client.delete(`/subjects/${subj.id}`)
    subjects.value = subjects.value.filter(s => s.id !== subj.id)
    if (selectedSubjectId.value === subj.id) { selectedSubjectId.value = null; chapterTree.value = [] }
  } catch (e) { alert('删除失败：' + (e.response?.data?.detail || e.message)) }
}

function startEditSubject(subj) { editingSubject.value = { ...subj } }

async function saveSubject() {
  saving.value = true
  try {
    await client.put(`/subjects/${editingSubject.value.id}`, editingSubject.value)
    const idx = subjects.value.findIndex(s => s.id === editingSubject.value.id)
    if (idx >= 0) subjects.value[idx] = editingSubject.value
    editingSubject.value = null
  } catch (e) { alert('保存失败：' + (e.response?.data?.detail || e.message)) }
  finally { saving.value = false }
}

// ── Chapter Tree ──
async function loadChapterTree() {
  if (!selectedSubjectId.value) return
  try {
    const res = await client.get(`/subjects/${selectedSubjectId.value}/chapters`)
    chapterTree.value = res.data
  } catch { chapterTree.value = [] }
}

const rootInput = ref(null)
async function startAddRoot() {
  showAddRoot.value = true
  resetChapterForm()
  await nextTick()
  rootInput.value?.focus()
}

async function createRootChapter() {
  saving.value = true
  try {
    await client.post('/chapters', {
      subject_id: selectedSubjectId.value,
      name: newChapter.value.name,
      level: newChapter.value.level,
      order_index: chapterTree.value.length + 1,
      is_leaf: newChapter.value.level === 3,
    })
    showAddRoot.value = false; resetChapterForm(); await loadChapterTree()
  } catch (e) { alert('创建失败：' + (e.response?.data?.detail || e.message)) }
  finally { saving.value = false }
}

onMounted(() => { loadSubjects(); loadModelKeys() })
</script>
