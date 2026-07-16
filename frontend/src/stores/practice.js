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
  const lastResult = ref(null)

  async function startLesson(chapterId) {
    const res = await client.post('/study/lesson-practice', { chapter_id: chapterId, question_count: 8 })
    session.value = { id: res.data.session_id, chapter_id: chapterId }
    questions.value = res.data.questions
    lessonContent.value = res.data.lesson_content
    mode.value = 'lesson'
    phase.value = 'lesson'
    currentIndex.value = 0
    lastResult.value = null
    return res.data
  }

  async function startPure(subjectId, chapterId = null) {
    const res = await client.post('/practice/pure', { subject_id: subjectId, chapter_id: chapterId, count: 1 })
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
    return res.data
  }

  function nextQuestion() {
    if (mode.value === 'lesson' && currentIndex.value >= questions.value.length - 1) {
      phase.value = 'done'
      return
    }
    currentIndex.value++
    phase.value = 'question'
    lastResult.value = null
  }

  async function fetchMoreQuestion() {
    lastResult.value = null
    phase.value = 'question'
    return null
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
    lastResult.value = null
    return data
  }

  function endSession() {
    phase.value = 'done'
  }

  return {
    session, questions, currentIndex, mode, lessonContent, phase, lastResult,
    startLesson, startPure, submitAnswer, nextQuestion, fetchMoreQuestion, loadSession, endSession,
  }
})
