<template>
  <div class="tree-node">
    <!-- ═══ ROW ═══ -->
    <div
      class="tree-row group"
      :class="{ 'is-leaf': node.is_leaf, 'is-editing': editing, 'drag-over': dragOver }"
      :style="{ paddingLeft: depth * 18 + 4 + 'px' }"
      draggable="true"
      @dblclick="startEdit"
      @dragstart="onDragStart"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
      @dragend="onDragEnd"
    >
      <!-- Guide lines -->
      <span v-if="depth > 0" class="tree-guide" />

      <!-- Toggle / spacer -->
      <button
        v-if="node.children?.length"
        @click="expanded = !expanded"
        class="tree-toggle"
      >
        <component :is="expanded ? ChevronDown : ChevronRight" :size="15" />
      </button>
      <span v-else class="tree-toggle invisible">
        <ChevronRight :size="15" />
      </span>

      <!-- Icon -->
      <component
        :is="node.is_leaf ? FileText : (expanded && node.children?.length ? FolderOpen : Folder)"
        :size="15"
        class="tree-icon"
        :class="{
          'text-[var(--accent)]': !node.is_leaf && node.children?.length,
          'text-[var(--ink-muted)]': node.is_leaf || !node.children?.length
        }"
      />

      <!-- Name (edit mode) -->
      <input
        v-if="editing"
        ref="editInput"
        v-model="editName"
        class="tree-input"
        @keydown.enter="saveEdit"
        @keydown.escape="cancelEdit"
        @blur="saveEdit"
      />

      <!-- Name (display mode) -->
      <span v-else class="tree-name" @click="expanded = !expanded">
        {{ node.name }}
        <span class="tree-badge" v-if="node.question_count">
          {{ node.question_count }} 题
        </span>
      </span>

      <!-- Action buttons (hover) -->
      <span class="tree-actions">
        <button
          @click.stop="startAddChild(Math.max(node.level + 1, 3))"
          class="tree-btn tree-btn-add" title="新建课时"
        >
          <FilePlus :size="13" />
        </button>
        <button
          @click.stop="startAddChild(node.level + 1)"
          class="tree-btn tree-btn-add" title="新建文件夹"
        >
          <FolderPlus :size="13" />
        </button>
        <button @click.stop="startEdit" class="tree-btn" title="重命名">
          <Pencil :size="13" />
        </button>
        <button @click.stop="deleteNode" class="tree-btn tree-btn-danger" title="删除">
          <Trash2 :size="13" />
        </button>
      </span>
    </div>

    <!-- ═══ INLINE ADD FORM ═══ -->
    <div v-if="showAdd" class="tree-add-form" :style="{ paddingLeft: (depth + 1) * 18 + 28 + 'px' }">
      <input
        ref="addInput"
        v-model="newChildName"
        class="tree-input"
        :placeholder="newChildLevel > (node.level + 1) ? '新课时名称...' : '新文件夹名称...'"
        @keydown.enter="createChild"
        @keydown.escape="showAdd = false; newChildName = ''"
      />
      <span class="text-[10px] text-[var(--ink-muted)] whitespace-nowrap ml-1">
        Enter 确认 · Esc 取消
      </span>
    </div>

    <!-- ═══ CHILDREN ═══ -->
    <div v-if="expanded && node.children?.length" class="tree-children">
      <ChapterTreeNode
        v-for="child in node.children" :key="child.id"
        :node="child" :depth="depth + 1" :subject-id="subjectId"
        @refresh="$emit('refresh')"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ChevronRight, ChevronDown, FileText, Folder, FolderOpen, FilePlus, FolderPlus, Pencil, Trash2 } from 'lucide-vue-next'
import client from '../../api/client'

const props = defineProps({ node: Object, subjectId: Number, depth: { type: Number, default: 0 } })
const emit = defineEmits(['refresh'])

const expanded = ref(props.depth < 2)
const editing = ref(false)
const editName = ref('')
const editInput = ref(null)
const showAdd = ref(false)
const addInput = ref(null)
const newChildName = ref('')
const newChildLevel = ref(3)
const busy = ref(false)

const canAddChild = props.node.is_leaf === false
const dragOver = ref(false)

// ── Drag & Drop ──
function onDragStart(e) {
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(props.node.id))
  e.target.classList.add('dragging')
}

function onDragOver(e) {
  if (e.dataTransfer.types.includes('text/plain')) {
    e.dataTransfer.dropEffect = 'move'
    dragOver.value = true
  }
}

function onDragLeave() { dragOver.value = false }

async function onDrop(e) {
  dragOver.value = false
  const draggedId = parseInt(e.dataTransfer.getData('text/plain'))
  if (!draggedId || draggedId === props.node.id) return
  // If dropping on a FOLDER (non-leaf) → reparent INTO that folder
  // If dropping on a LEAF → reorder at same level as the leaf
  const newParent = props.node.is_leaf ? (props.node.parent_chapter_id || null) : props.node.id
  const newOrder = props.node.is_leaf ? (props.node.order_index || 0) + 1 : (props.node.children?.length || 0) + 1
  try {
    await client.put(`/chapters/${draggedId}`, {
      parent_chapter_id: newParent,
      order_index: newOrder,
    })
    emit('refresh')
  } catch (e) { /* ignore */ }
}

function onDragEnd(e) { e.target.classList.remove('dragging'); dragOver.value = false }

async function startEdit() {
  if (busy.value) return
  editName.value = props.node.name
  editing.value = true
  await nextTick()
  editInput.value?.focus()
  editInput.value?.select()
}

function cancelEdit() { editing.value = false }

async function saveEdit() {
  if (!editing.value || busy.value) return
  const name = editName.value.trim()
  if (!name || name === props.node.name) { editing.value = false; return }
  busy.value = true
  try {
    await client.put(`/chapters/${props.node.id}`, { name })
    editing.value = false; emit('refresh')
  } catch (e) { alert('保存失败：' + (e.response?.data?.detail || e.message)) }
  finally { busy.value = false }
}

async function deleteNode() {
  if (!confirm(`确定删除「${props.node.name}」及其所有子章节吗？`)) return
  busy.value = true
  try { await client.delete(`/chapters/${props.node.id}`); emit('refresh') }
  catch (e) { alert('删除失败：' + (e.response?.data?.detail || e.message)) }
  finally { busy.value = false }
}

async function startAddChild(level) {
  newChildName.value = ''
  newChildLevel.value = level
  showAdd.value = true
  await nextTick()
  addInput.value?.focus()
}

async function createChild() {
  const name = newChildName.value.trim()
  if (!name || busy.value) return
  busy.value = true
  try {
    await client.post('/chapters', {
      subject_id: props.subjectId,
      name,
      level: newChildLevel.value,
      parent_chapter_id: props.node.id,
      order_index: (props.node.children?.length || 0) + 1,
      is_leaf: newChildLevel.value >= 3,
    })
    showAdd.value = false; newChildName.value = ''
    emit('refresh')
  } catch (e) { alert('创建失败：' + (e.response?.data?.detail || e.message)) }
  finally { busy.value = false }
}
</script>

<style scoped>
/* ═══ Tree Node ═══ */
.tree-node {
  user-select: none;
}

.tree-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  margin: 1px 0;
  border-radius: 5px;
  cursor: pointer;
  position: relative;
  min-height: 28px;
}

.tree-row:hover {
  background: var(--surface-1);
}

.tree-row.is-leaf {
  cursor: default;
}

/* ── Guide lines ── */
.tree-guide {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border-light);
}

/* ── Toggle ── */
.tree-toggle {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--ink-muted);
  border-radius: 3px;
}

.tree-toggle:hover {
  background: var(--surface-2);
}

/* ── Icon ── */
.tree-icon {
  flex-shrink: 0;
  margin: 0 2px;
}

/* ── Name ── */
.tree-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--ink-primary);
  line-height: 1.4;
}

.tree-row:hover .tree-name {
  color: var(--ink-primary);
}

/* ── Badge ── */
.tree-badge {
  font-size: 10px;
  color: var(--ink-muted);
  margin-left: 6px;
  background: var(--surface-2);
  padding: 0 5px;
  border-radius: 3px;
}

/* ── Input ── */
.tree-input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--accent-indigo);
  background: var(--surface-0);
  color: var(--ink-primary);
  border-radius: 3px;
  padding: 1px 6px;
  font-size: 13px;
  line-height: 1.5;
  outline: none;
}

/* ── Actions ── */
.tree-actions {
  display: flex;
  align-items: center;
  gap: 1px;
  opacity: 0;
  transition: opacity 0.1s;
  flex-shrink: 0;
}

.tree-row:hover .tree-actions,
.tree-row.is-editing .tree-actions {
  opacity: 1;
}

.tree-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--ink-muted);
  transition: all 0.1s;
}

.tree-btn:hover {
  background: var(--surface-2);
  color: var(--ink-primary);
}

.tree-btn-danger:hover {
  background: var(--error-soft);
  color: var(--error);
}

.tree-btn-add:hover {
  background: var(--accent-indigo-soft);
  color: var(--accent-indigo);
}

/* ── Add form (inline) ── */
.tree-add-form {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  margin: 2px 0;
  background: var(--surface-1);
  border-radius: 5px;
  border: 1px dashed var(--border);
}

/* ── Children ── */
.tree-children {
  position: relative;
}

/* ── Drag & Drop ── */
.tree-row.dragging {
  opacity: 0.4;
}

.tree-row.drag-over {
  background: var(--accent-indigo-soft) !important;
  outline: 2px dashed var(--accent-indigo);
  outline-offset: -2px;
  border-radius: 5px;
}

.tree-row[draggable="true"] {
  cursor: grab;
}

.tree-row[draggable="true"]:active {
  cursor: grabbing;
}
</style>
