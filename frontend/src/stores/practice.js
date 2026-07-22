import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '../api/client'

export const usePracticeStore = defineStore('practice', () => {
  const session = ref(null)
  const questions = ref([])
  const currentIndex = ref(0)
  const mode = ref('') // 'lesson' | 'pure'
  const lessonContent = ref('')
  const phase = ref('lesson') // 'lesson' | 'question' | 'feedback' | 'done'
  const streaming = ref(false)  // true while lesson content is still arriving
  const explanationStreaming = ref(false)  // true while AI explanation is streaming
  const lastResult = ref(null)
  const editingLesson = ref(false)
  const lessonDraft = ref('')
  let currentAbortController = null

  async function startLesson(chapterId) {
    // Abort any existing stream
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }

    mode.value = 'lesson'
    phase.value = 'lesson'
    currentIndex.value = 0
    lastResult.value = null
    lessonContent.value = ''
    streaming.value = true
    editingLesson.value = false
    lessonDraft.value = ''

    // 1. Create session FIRST (fast — returns immediately, no AI blocking)
    const res = await client.post('/study/lesson-practice', { chapter_id: chapterId, question_count: 8 })
    session.value = { id: res.data.session_id, chapter_id: chapterId }
    questions.value = res.data.questions

    // 2. If content already cached, use it immediately
    if (res.data.lesson_content) {
      lessonContent.value = res.data.lesson_content
      streaming.value = false
      return res.data
    }

    // 3. Content not cached — connect SSE for real-time streaming (non-blocking)
    const token = localStorage.getItem('token')
    const sseUrl = `/api/v1/study/lesson-stream?chapter_id=${chapterId}`

    currentAbortController = new AbortController()

    fetch(sseUrl, {
      headers: { Authorization: `Bearer ${token}` },
      signal: currentAbortController.signal,
    })
      .then(async (resp) => {
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.chunk) {
                  lessonContent.value += data.chunk
                } else if (data.done) {
                  if (data.content) lessonContent.value = data.content
                  streaming.value = false
                } else if (data.error) {
                  lessonContent.value = '# 讲义生成失败\n\n> ' + data.error
                  streaming.value = false
                }
              } catch { /* skip malformed */ }
            }
          }
        }
        streaming.value = false
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        lessonContent.value = '# 讲义生成失败\n\n> 无法连接 AI 服务，请稍后重试。'
        streaming.value = false
      })

    return res.data
  }

  function startEditLesson() {
    lessonDraft.value = lessonContent.value
    editingLesson.value = true
  }

  function cancelEditLesson() {
    lessonDraft.value = ''
    editingLesson.value = false
  }

  async function saveLessonEdit() {
    lessonContent.value = lessonDraft.value
    editingLesson.value = false
    // Save edited content to backend
    if (session.value?.chapter_id) {
      try {
        await client.put(`/study/chapter-lesson/${session.value.chapter_id}`, {
          content: lessonDraft.value
        })
      } catch (e) {
        console.error('Failed to save lesson edit', e)
      }
    }
  }

  async function regenerateLesson() {
    if (!session.value?.chapter_id) return
    // Clear cached content on backend
    try {
      await client.delete(`/study/chapter-lesson/${session.value.chapter_id}`)
    } catch (e) {
      console.error('Failed to clear lesson cache', e)
    }
    // Restart the lesson (will trigger fresh generation)
    lessonContent.value = ''
    streaming.value = true
    const token = localStorage.getItem('token')
    const sseUrl = `/api/v1/study/lesson-stream?chapter_id=${session.value.chapter_id}`

    if (currentAbortController) {
      currentAbortController.abort()
    }
    currentAbortController = new AbortController()

    fetch(sseUrl, {
      headers: { Authorization: `Bearer ${token}` },
      signal: currentAbortController.signal,
    })
      .then(async (resp) => {
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                if (data.chunk) {
                  lessonContent.value += data.chunk
                } else if (data.done) {
                  if (data.content) lessonContent.value = data.content
                  streaming.value = false
                } else if (data.error) {
                  lessonContent.value = '# 讲义生成失败\n\n> ' + data.error
                  streaming.value = false
                }
              } catch { /* skip */ }
            }
          }
        }
        streaming.value = false
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        lessonContent.value = '# 讲义生成失败\n\n> 无法连接 AI 服务，请稍后重试。'
        streaming.value = false
      })
  }

  async function startExam(subjectId = null) {
    const res = await client.post('/practice/exam', { subject_id: subjectId, count: 20 })
    session.value = { id: res.data.session_id }
    questions.value = res.data.questions
    mode.value = 'exam'
    phase.value = 'question'
    currentIndex.value = 0
    lastResult.value = null
    return res.data
  }

  async function startPure(subjectId, chapterId = null) {
    const res = await client.post('/practice/pure', { subject_id: subjectId, chapter_id: chapterId, count: 3 })
    session.value = { id: res.data.session_id }
    questions.value = res.data.questions
    mode.value = 'pure'
    phase.value = 'question'
    currentIndex.value = 0
    lastResult.value = null
    return res.data
  }

  async function submitAnswer(questionId, userAnswer, timeSpent) {
    if (!session.value) return
    const res = await client.post(`/practice/sessions/${session.value.id}/submit`, {
      question_id: questionId,
      user_answer: userAnswer,
      time_spent_seconds: timeSpent,
    })
    lastResult.value = res.data
    phase.value = 'feedback'
    // For subjective questions, auto-start streaming explanation
    if (res.data.grading_mode === 'self') {
      streamExplanation(questionId)
    }
    return res.data
  }

  async function streamExplanation(questionId) {
    if (!session.value) return
    const token = localStorage.getItem('token')
    const url = `/api/v1/practice/sessions/${session.value.id}/explanation-stream?question_id=${questionId}`

    explanationStreaming.value = true
    lastResult.value = { ...lastResult.value, explanation: '' }

    try {
      const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.chunk) {
                lastResult.value = { ...lastResult.value, explanation: (lastResult.value.explanation || '') + data.chunk }
              } else if (data.done) {
                explanationStreaming.value = false
              } else if (data.error) {
                lastResult.value = { ...lastResult.value, explanation: '> ⚠️ 解析生成失败：' + data.error }
                explanationStreaming.value = false
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        lastResult.value = { ...lastResult.value, explanation: '> ❌ 无法连接 AI 服务' }
      }
    } finally {
      explanationStreaming.value = false
    }
  }

  function nextQuestion() {
    if (mode.value === 'lesson' && currentIndex.value >= questions.value.length - 1) {
      finishSession()
      return
    }
    currentIndex.value++
    phase.value = 'question'
    lastResult.value = null
  }

  async function finishSession() {
    phase.value = 'done'
    // Fire-and-forget: reflect to Agent vault
    if (session.value?.id) {
      try {
        await client.post(`/agent/reflect`, { session_id: session.value.id })
      } catch (e) { /* non-critical */ }
    }
  }

  async function fetchMoreQuestions() {
    // Fetch another batch of random questions for pure practice
    if (!session.value) return
    try {
      const subjectId = questions.value[0]?.subject_id
      const res = await client.post('/practice/pure', {
        subject_id: subjectId,
        count: 3
      })
      // Replace the session ID with the new one
      session.value.id = res.data.session_id
      questions.value = res.data.questions
      currentIndex.value = 0
      phase.value = 'question'
      lastResult.value = null
    } catch (e) {
      console.error('Failed to fetch more questions', e)
    }
  }

  async function loadSession(sessionId) {
    const res = await client.get(`/practice/sessions/${sessionId}`)
    const data = res.data
    session.value = { id: data.id, chapter_id: data.chapter_id }
    mode.value = data.mode
    lessonContent.value = data.lesson_content || ''
    questions.value = data.questions || []
    currentIndex.value = data.current_index || 0
    phase.value = data.mode === 'lesson' ? 'lesson' : 'question'
    streaming.value = false
    lastResult.value = null
    return data
  }

  function endSession() {
    phase.value = 'done'
  }

  return {
    session, questions, currentIndex, mode, lessonContent, phase, streaming, explanationStreaming, lastResult,
    editingLesson, lessonDraft,
    startLesson, startExam, startPure, submitAnswer, nextQuestion, fetchMoreQuestions, loadSession, endSession,
    startEditLesson, cancelEditLesson, saveLessonEdit, regenerateLesson,
  }
})
