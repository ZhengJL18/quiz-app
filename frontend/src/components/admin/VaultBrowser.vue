<template>
  <div class="flex flex-col lg:flex-row gap-4" style="height: calc(100vh - 220px)">
    <!-- Left: File Tree -->
    <div class="w-full lg:w-72 flex-shrink-0 card overflow-hidden flex flex-col min-h-0">
      <!-- User selector + refresh -->
      <div class="px-3 py-2.5 border-b border-[var(--border-light)] flex items-center gap-2">
        <select v-model="selectedUserId" @change="loadTree" class="flex-1 text-xs bg-[var(--surface-0)] border border-[var(--border-light)] rounded-md px-2 py-1.5 outline-none">
          <option :value="null" disabled>选择用户...</option>
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }}</option>
        </select>
        <button @click="loadTree" class="btn btn-ghost p-1" title="刷新">
          <RefreshCw :size="14" :class="treeLoading ? 'animate-spin' : ''" />
        </button>
      </div>
      <!-- Tree -->
      <div class="flex-1 overflow-y-auto overscroll-contain p-1" style="min-height:0">
        <div v-if="treeLoading" class="p-8 text-center text-xs text-[var(--ink-muted)]">
          <Loader :size="16" class="animate-spin mx-auto mb-2" /> 加载中...
        </div>
        <div v-else-if="!selectedUserId" class="p-8 text-center text-xs text-[var(--ink-muted)]">
          请选择一个用户
        </div>
        <div v-else-if="tree.length === 0" class="p-8 text-center text-xs text-[var(--ink-muted)]">
          该用户无文件
        </div>
        <TreeNode
          v-for="node in tree" :key="node.name"
          :node="node" :depth="0"
          :selectedPath="selectedPath"
          @select="selectFile"
        />
      </div>
    </div>

    <!-- Right: File Preview -->
    <div class="flex-1 card overflow-hidden flex flex-col min-h-0">
      <div class="px-4 py-2.5 border-b border-[var(--border-light)] flex items-center justify-between">
        <div class="flex items-center gap-2 min-w-0">
          <FileText :size="14" class="text-[var(--ink-muted)] flex-shrink-0" />
          <span class="text-xs font-medium text-[var(--ink-primary)] truncate">{{ selectedPath || '未选择文件' }}</span>
        </div>
        <div v-if="selectedPath" class="flex items-center gap-1">
          <button v-if="!editing" @click="startEdit" class="btn btn-ghost p-1 text-[var(--ink-muted)] hover:text-[var(--accent-indigo)]" title="编辑">
            <Pencil :size="14" />
          </button>
          <button v-else @click="saveEdit" :disabled="saving" class="btn btn-ghost p-1 text-[var(--success)]" title="保存">
            <Save v-if="!saving" :size="14" />
            <Loader v-else :size="14" class="animate-spin" />
          </button>
          <button v-if="editing" @click="cancelEdit" class="btn btn-ghost p-1 text-[var(--ink-muted)]" title="取消">
            <XIcon :size="14" />
          </button>
          <button @click="deleteFile" class="btn btn-ghost p-1 text-[var(--ink-muted)] hover:text-[var(--error)]" title="删除">
            <Trash2 :size="14" />
          </button>
        </div>
      </div>
      <div class="flex-1 overflow-y-auto min-h-0">
        <div v-if="fileLoading" class="py-12 text-center text-xs text-[var(--ink-muted)]">
          <Loader :size="16" class="animate-spin mx-auto mb-2" /> 加载中...
        </div>
        <div v-else-if="!selectedPath" class="py-16 text-center text-[var(--ink-muted)]">
          <Folder :size="40" class="mx-auto mb-3 opacity-20" />
          <p class="text-xs">选择左侧文件以预览</p>
        </div>
        <!-- Edit mode -->
        <textarea v-else-if="editing" v-model="editContent"
          class="w-full h-full min-h-[300px] p-4 sm:p-6 resize-none border-none outline-none text-sm font-mono leading-relaxed bg-[var(--surface-0)] text-[var(--ink-primary)]"
          placeholder="编辑文件内容..." />
        <!-- Preview mode -->
        <article v-else class="p-4 sm:p-6 note-preview text-sm leading-relaxed" v-html="renderedContent" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { FileText, Folder, RefreshCw, Loader, Trash2, Pencil, Save, X as XIcon } from 'lucide-vue-next'
import { renderMarkdown } from '../../composables/useKaTeX'
import TreeNode from './TreeNode.vue'
import client from '../../api/client'

const users = ref([])
const selectedUserId = ref(null)
const tree = ref([])
const treeLoading = ref(false)
const selectedPath = ref('')
const fileContent = ref('')
const fileLoading = ref(false)
const editing = ref(false)
const editContent = ref('')
const saving = ref(false)

const renderedContent = computed(() => {
  try { return renderMarkdown(fileContent.value) }
  catch { return '<p>渲染失败</p>' }
})

onMounted(async () => {
  try { const res = await client.get('/admin/vault/users'); users.value = res.data }
  catch { /* not admin */ }
})

async function loadTree() {
  if (!selectedUserId.value) return
  treeLoading.value = true
  try {
    const res = await client.get(`/admin/vault/${selectedUserId.value}`)
    tree.value = res.data.tree || []
  } catch { tree.value = [] }
  finally { treeLoading.value = false }
}

async function selectFile(node) {
  if (node.type !== 'file') return
  editing.value = false
  editContent.value = ''
  selectedPath.value = node.path || node.name
  fileLoading.value = true
  try {
    const res = await client.get(`/admin/vault/${selectedUserId.value}/file`, { params: { path: selectedPath.value } })
    fileContent.value = res.data.content || ''
  } catch { fileContent.value = '(读取失败)' }
  finally { fileLoading.value = false }
}

function startEdit() {
  editing.value = true
  editContent.value = fileContent.value
}

function cancelEdit() {
  editing.value = false
  editContent.value = ''
}

async function saveEdit() {
  if (!selectedUserId.value || !selectedPath.value || saving.value) return
  saving.value = true
  try {
    await client.put(`/admin/vault/${selectedUserId.value}/file`, { content: editContent.value }, { params: { path: selectedPath.value } })
    fileContent.value = editContent.value
    editing.value = false
    window.__toast?.success('已保存')
  } catch (e) {
    window.__toast?.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteFile() {
  if (!selectedPath.value || !confirm(`删除 ${selectedPath.value}？`)) return
  try {
    await client.delete(`/admin/vault/${selectedUserId.value}/file`, { params: { path: selectedPath.value } })
    selectedPath.value = ''
    fileContent.value = ''
    loadTree()
  } catch { alert('删除失败') }
}
</script>
