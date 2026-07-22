import { defineStore } from 'pinia'
import { ref, watch, computed } from 'vue'
import { emit } from '../utils/events'

// ── Helpers ──
function storageKey(userId) { return `chat_v2_${userId || 'anon'}` }
function activeKey(userId) { return `chat_active_${userId || 'anon'}` }

function loadConvos(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveConvos(userId, convos) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(convos.slice(-20)))
  } catch { /* quota */ }
}

// ── Backend API helpers ──
async function fetchConvosFromBackend() {
  const token = localStorage.getItem('token')
  if (!token) return []
  try {
    const resp = await fetch('http://43.139.179.58/api/v1/conversations', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!resp.ok) return []
    const data = await resp.json()
    // Convert backend format to frontend format
    return data.map(c => ({
      id: c.id,  // backend ID
      title: c.title,
      messages: c.messages || [],
      createdAt: c.created_at,
      _fromBackend: true,
    }))
  } catch { return [] }
}

async function saveConvoToBackend(convo) {
  const token = localStorage.getItem('token')
  if (!token) return
  try {
    const payload = {
      id: String(convo.id),
      title: convo.title || '新对话',
      messages: (convo.messages || [])
        .filter(m => m.role !== 'streaming' && !m._greeting)
        .map(m => ({ role: m.role, content: m.content }))
    }
    const resp = await fetch('http://43.139.179.58/api/v1/conversations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
    if (resp.ok) {
      const saved = await resp.json()
      // Update frontend convo ID to backend ID
      if (saved.id && convo.id !== saved.id) {
        convo.id = saved.id
        convo._fromBackend = true
        return saved.id
      }
    }
  } catch { /* offline — localStorage will catch it */ }
  return null
}

async function deleteConvoFromBackend(convoId) {
  const token = localStorage.getItem('token')
  if (!token) return
  try {
    await fetch(`http://43.139.179.58/api/v1/conversations/${convoId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
  } catch { /* ok */ }
}


export const useChatStore = defineStore('chat', () => {
  const userId = ref(null)
  const convos = ref([])
  const activeId = ref(null)
  const sending = ref(false)
  const open = ref(false)
  const fullScreen = ref(false)
  const greeted = ref(!!sessionStorage.getItem('agent_greeted'))  // whether AI has proactively greeted this session
  const streamingContent = ref('')
  const loading = ref(false)
  const syncing = ref(false)
  let abortController = null

  // ── Active conversation ──
  const activeConvo = computed(() => convos.value.find(c => c.id === activeId.value))
  const messages = computed({
    get: () => activeConvo.value?.messages || [],
    set: (val) => {
      const c = convos.value.find(c => c.id === activeId.value)
      if (c) c.messages = val
    }
  })

  // ── Init per-user — try backend first, fall back to localStorage ──
  async function initForUser(uid) {
    userId.value = uid || 'anon'
    loading.value = true

    // Try backend first
    const backendConvos = await fetchConvosFromBackend()

    if (backendConvos.length > 0) {
      // Merge: backend is the source of truth for conversations that exist there
      convos.value = backendConvos

      // Also load any localStorage-only convos not yet synced
      const localConvos = loadConvos(userId.value)
      const backendIds = new Set(backendConvos.map(c => String(c.id)))
      for (const lc of localConvos) {
        if (!backendIds.has(String(lc.id)) && !lc._fromBackend) {
          convos.value.unshift(lc)
        }
      }
    } else {
      // No backend data — use localStorage
      convos.value = loadConvos(userId.value)
    }

    // Restore active conversation
    const savedActive = localStorage.getItem(activeKey(userId.value))
    if (savedActive && convos.value.find(c => String(c.id) === savedActive)) {
      activeId.value = savedActive
    } else if (convos.value.length > 0) {
      activeId.value = convos.value[0].id
    } else {
      newConversation()
    }
    loading.value = false
  }

  // ── Auto-save ──
  watch(convos, (val) => {
    if (userId.value) saveConvos(userId.value, val)
  }, { deep: true })
  watch(activeId, (val) => {
    if (val && userId.value) localStorage.setItem(activeKey(userId.value), val)
  })

  // ── Conversation management ──
  function newConversation() {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
    const convo = {
      id,
      title: '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
    }
    convos.value.unshift(convo)
    activeId.value = id
    return id
  }

  function switchConversation(id) {
    if (convos.value.find(c => String(c.id) === String(id))) {
      activeId.value = id
    }
  }

  async function deleteConversation(id) {
    // Delete from backend if it's a backend conversation
    const convo = convos.value.find(c => String(c.id) === String(id))
    if (convo?._fromBackend) {
      await deleteConvoFromBackend(id)
    }

    convos.value = convos.value.filter(c => String(c.id) !== String(id))
    if (String(activeId.value) === String(id)) {
      activeId.value = convos.value[0]?.id || newConversation()
    }
  }

  function clearHistory() {
    convos.value = []
    newConversation()
  }

  // ── Auto-title from first user message ──
  function autoTitle() {
    const c = convos.value.find(c => String(c.id) === String(activeId.value))
    if (!c || c.title !== '新对话') return
    const firstUserMsg = c.messages.find(m => m.role === 'user')
    if (firstUserMsg) {
      c.title = firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '...' : '')
    }
  }

  function toggle() { open.value = !open.value }
  function toggleFullScreen() { fullScreen.value = !fullScreen.value }

  const greetingLoading = ref(false)

  async function maybeAutoGreet() {
    if (greeted.value || greetingLoading.value) return
    greeted.value = true
    greetingLoading.value = true
    try {
      const token = localStorage.getItem('token')
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 15000)  // 15s timeout
      const resp = await fetch('http://43.139.179.58/api/v1/agent/greeting', {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      clearTimeout(timeout)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      // Add an empty assistant message to stream into
      messages.value.push({ role: 'assistant', content: '' })
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        for (const line of buffer.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.chunk) {
                messages.value[messages.value.length - 1].content += d.chunk
              }
            } catch {}
          }
        }
        buffer = buffer.includes('\n') ? buffer.split('\n').pop() : ''
      }
    } catch (e) {
      if (e.name === 'AbortError') { /* timeout - silent */ }
    } finally {
      greetingLoading.value = false
    }
  }

  // ── Daily greeting ──
  const LAST_GREET = 'chat_last_greet'
  function maybeGreet() {
    const today = new Date().toDateString()
    const last = localStorage.getItem(LAST_GREET)
    if (last !== today && convos.value.length === 0) {
      newConversation()
      const c = convos.value.find(co => String(co.id) === String(activeId.value))
      if (c) {
        c.messages = [{
          role: 'assistant',
          content: '# 📅 新的一天！\n\n有什么学习计划？\n\n---\n\n> 试试问我：**「今天有什么要复习的？」** 或 **「我哪一章最薄弱？」**',
          _greeting: true,
        }]
      }
    }
    localStorage.setItem(LAST_GREET, today)
  }

  // ── Sync current conversation to backend ──
  async function syncToBackend() {
    if (syncing.value) return  // Prevent concurrent syncs
    const c = convos.value.find(co => String(co.id) === String(activeId.value))
    if (!c || !c.messages.length) return
    syncing.value = true
    try {
      const newId = await saveConvoToBackend(c)
      if (newId) {
        // Update activeId if backend gave us a new ID
        if (String(activeId.value) !== String(newId)) {
          const oldId = activeId.value
          activeId.value = newId
          localStorage.setItem(activeKey(userId.value), newId)
          // Update any pending references
          const idx = convos.value.findIndex(co => String(co.id) === String(oldId))
          if (idx >= 0) convos.value[idx].id = newId
        }
      }
    } finally {
      syncing.value = false
    }
  }

  // ── Stop / cancel current generation ──
  function stop() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    sending.value = false
    // Append partial content as message if any
    if (streamingContent.value) {
      const c = convos.value.find(co => String(co.id) === String(activeId.value))
      if (c) {
        c.messages.push({ role: 'assistant', content: streamingContent.value + '\n\n> ⏹ 已停止' })
      }
      streamingContent.value = ''
      syncToBackend()
    }
  }

  // ── Send ──
  async function send(text, model = 'deepseek') {
    if (!text.trim() || sending.value) return
    if (!activeId.value) newConversation()

    const c = convos.value.find(co => String(co.id) === String(activeId.value))
    if (!c) return
    c.messages.push({ role: 'user', content: text })
    autoTitle()

    sending.value = true
    streamingContent.value = ''

    // Create abort controller for this request
    abortController = new AbortController()

    const token = localStorage.getItem('token')
    if (!token) {
      c.messages.push({ role: 'assistant', content: '❌ 未登录' })
      sending.value = false
      abortController = null
      return
    }

    try {
      const resp = await fetch('http://43.139.179.58/api/v1/assistant/chat/stream', {
        method: 'POST',
        signal: abortController.signal,
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          messages: c.messages
            .filter(m => m.role !== 'streaming' && !m._greeting)
            .map(m => ({ role: m.role, content: m.content })),
          model: model,
        }),
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = '', full = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.chunk) { full += data.chunk; streamingContent.value = full }
              else if (data.tool_start) {
                // Insert a collapsible tool message
                c.messages.push({ role: 'tool', tool: data.tool, label: data.label, status: 'running', summary: '', full: '' })
              }
              else if (data.tool_end) {
                // Update the last tool message with result
                const last = c.messages[c.messages.length - 1]
                if (last?.role === 'tool' && last.tool === data.tool) {
                  last.status = data.error ? 'error' : 'done'
                  last.summary = data.summary
                  last.full = data.full || ''
                }
              }
              else if (data.text_done) { /* streaming finished, actions running */ }
              else if (data.action_progress) { /* handled by tool_start/tool_end now */ }
              else if (data.done) {
                let final = full
                if (data.actions?.length) final += '\n\n' + data.actions.filter(Boolean).join('\n')
                c.messages.push({ role: 'assistant', content: final || '(empty)' })
                streamingContent.value = ''
                if (data.actions?.length) emit('data-changed')
              }
              else if (data.error) {
                c.messages.push({ role: 'assistant', content: '❌ ' + friendlyError(data.error) })
                streamingContent.value = ''
              }
            } catch { /* skip malformed */ }
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        // User cancelled — stop() already handled the cleanup
        return
      }
      c.messages.push({ role: 'assistant', content: '❌ ' + friendlyError(e.message || 'Network error') })
      streamingContent.value = ''
    } finally {
      sending.value = false
      abortController = null
      // Sync even on error — preserve partial conversation
      syncToBackend()
    }
  }

  function friendlyError(msg) {
    const m = msg.toLowerCase()
    if (m.includes('authentication') || m.includes('401') || m.includes('403'))
      return 'API 密钥无效，请在账号设置中配置 DeepSeek API Key'
    if (m.includes('balance') || m.includes('insufficient') || m.includes('402'))
      return 'DeepSeek API 余额不足，请充值后重试'
    if (m.includes('timeout') || m.includes('connect'))
      return 'AI 服务连接超时，请检查网络后重试'
    return msg.slice(0, 200)
  }

  return {
    activeId, convos, activeConvo, messages,
    sending, open, fullScreen, streamingContent, loading,
    toggle, toggleFullScreen, send, stop, maybeGreet, maybeAutoGreet,
    newConversation, switchConversation, deleteConversation, clearHistory,
    initForUser, syncToBackend,
  }
})
