<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div class="card w-full max-w-md p-6 space-y-5 animate-scale-in">
        <!-- Step indicator -->
        <div class="flex items-center gap-2 mb-2">
          <div v-for="s in 3" :key="s"
            class="flex-1 h-1 rounded-full transition-all"
            :class="s <= step ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'" />
        </div>

        <!-- Step 1: Subjects -->
        <div v-if="step === 1" class="space-y-4">
          <h2 class="text-xl font-bold text-[var(--ink-primary)]">欢迎来到三一 🎓</h2>
          <p class="text-sm text-[var(--ink-muted)]">告诉我你最近在学什么，我来帮你</p>
          <div class="space-y-2">
            <div v-for="(s, i) in subjects" :key="i" class="flex items-center gap-2">
              <input v-model="subjects[i]" :placeholder="`科目 ${i+1}，如高等数学`"
                class="input flex-1 text-sm" @keydown.enter="addSubject" />
              <button v-if="subjects.length > 1" @click="subjects.splice(i,1)" class="btn btn-ghost p-1 text-[var(--ink-muted)]">✕</button>
            </div>
            <button @click="addSubject" class="btn btn-ghost text-xs text-[var(--accent)]">+ 添加科目</button>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button @click="skip" class="btn btn-ghost text-sm">跳过</button>
            <button @click="nextStep" :disabled="!subjects[0]" class="btn btn-primary text-sm">下一步</button>
          </div>
        </div>

        <!-- Step 2: Goal -->
        <div v-if="step === 2" class="space-y-4">
          <h2 class="text-xl font-bold text-[var(--ink-primary)]">你的目标是什么？</h2>
          <p class="text-sm text-[var(--ink-muted)]">有目标，学习才有方向</p>
          <textarea v-model="goal" rows="2" class="input w-full text-sm resize-none"
            placeholder="如：高数期末90分 / 考研上岸 / 过四级"
            @keydown.ctrl.enter="nextStep" />
          <div class="flex justify-end gap-2 pt-2">
            <button @click="prevStep" class="btn btn-ghost text-sm">上一步</button>
            <button @click="nextStep" class="btn btn-primary text-sm" :disabled="!goal.trim()">下一步</button>
          </div>
        </div>

        <!-- Step 3: Learning Style -->
        <div v-if="step === 3" class="space-y-4">
          <h2 class="text-xl font-bold text-[var(--ink-primary)]">你喜欢怎么学？</h2>
          <p class="text-sm text-[var(--ink-muted)]">我会用你喜欢的方式教你</p>
          <div class="space-y-2">
            <button v-for="opt in styleOptions" :key="opt.value"
              @click="learningStyle = opt.value"
              class="w-full text-left p-3 rounded-lg border transition-all text-sm"
              :class="learningStyle === opt.value
                ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                : 'border-[var(--border-light)] hover:border-[var(--ink-muted)]'">
              <div class="font-medium text-[var(--ink-primary)]">{{ opt.label }}</div>
              <div class="text-xs text-[var(--ink-muted)] mt-0.5">{{ opt.desc }}</div>
            </button>
          </div>
          <div class="flex justify-end gap-2 pt-2">
            <button @click="prevStep" class="btn btn-ghost text-sm">上一步</button>
            <button @click="finish" :disabled="submitting" class="btn btn-primary text-sm">
              {{ submitting ? '设置中...' : '开始学习' }}
            </button>
          </div>
        </div>

        <!-- Error -->
        <p v-if="error" class="text-xs text-[var(--error)]">{{ error }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import client from '../api/client'

const emit = defineEmits(['done'])
const visible = ref(!localStorage.getItem('onboarded'))
const dismissed = ref(false)
const step = ref(1)
const subjects = ref([''])
const goal = ref('')
const learningStyle = ref('')
const submitting = ref(false)
const error = ref('')

const styleOptions = [
  { value: 'examples_first', label: '先看例子，再学原理', desc: '喜欢从具体例题入手，再理解抽象概念' },
  { value: 'theory_first', label: '先学原理，再做题', desc: '喜欢先搞清楚定义和定理，再通过练习巩固' },
  { value: 'practice_heavy', label: '直接刷题，错了再学', desc: '觉得做题是最好的学习方式，边错边学' },
  { value: 'not_sure', label: '不太确定', desc: '你帮我判断最适合我的方式' },
]

function addSubject() { subjects.value.push('') }
function nextStep() { step.value++ }
function prevStep() { step.value-- }
function skip() { localStorage.setItem('onboarded', 'true'); visible.value = false; emit('done') }

async function finish() {
  submitting.value = true
  error.value = ''
  try {
    await client.post('/agent/onboard', {
      subjects: subjects.value.filter(s => s.trim()),
      goal: goal.value.trim(),
      learning_style: learningStyle.value,
    })
  } catch (e) {
    error.value = '设置保存失败，但你可以稍后在设置中修改（已跳过引导）'
  } finally {
    submitting.value = false
    localStorage.setItem('onboarded', 'true')
    visible.value = false
    emit('done')
  }
}
</script>
