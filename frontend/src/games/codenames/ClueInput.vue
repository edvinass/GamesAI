<script setup lang="ts">
import { computed, ref } from 'vue'
import { getBoardWords, validateClueWord } from './clueValidation'

const props = defineProps<{
  boardWords: string[]
}>()

const emit = defineEmits<{
  submit: [word: string, number: number]
}>()

const clueWord = ref('')
const clueNumber = ref(1)
const justSubmitted = ref(false)

const boardWordSet = computed(() => getBoardWords(props.boardWords))

const validationError = computed(() => {
  if (!clueWord.value.trim()) return null
  return validateClueWord(clueWord.value, boardWordSet.value)
})

function submit() {
  if (!clueWord.value.trim() || validationError.value) return
  emit('submit', clueWord.value.trim(), clueNumber.value)
  clueWord.value = ''
  justSubmitted.value = true
  setTimeout(() => (justSubmitted.value = false), 600)
}
</script>

<template>
  <div class="clue-input card" :class="{ submitted: justSubmitted }">
    <h4>✨ Your clue</h4>
    <div class="row">
      <input v-model="clueWord" placeholder="One word…" maxlength="30" @keyup.enter="submit" />
      <input v-model.number="clueNumber" type="number" min="0" max="9" class="number-input" aria-label="Clue number" />
      <button class="btn-primary submit-btn" :disabled="Boolean(validationError) || !clueWord.trim()" @click="submit">
        Give Clue
      </button>
    </div>
    <Transition name="error-shake">
      <p v-if="validationError" class="error">{{ validationError }}</p>
    </Transition>
  </div>
</template>

<style scoped>
.clue-input {
  width: 100%;
  padding: 1rem 1.25rem;
  border: 1px solid rgba(91, 156, 255, 0.25);
  background: linear-gradient(135deg, rgba(91, 156, 255, 0.08) 0%, var(--surface) 100%);
  animation: glowPulse 3s ease-in-out infinite;
}

.clue-input.submitted {
  animation: celebrate 0.5s var(--ease-bounce);
}

.clue-input h4 {
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.row {
  display: flex;
  gap: 0.5rem;
}

.row input {
  flex: 1;
}

.number-input {
  flex: 0 0 56px !important;
  text-align: center;
  font-weight: 700;
  font-size: 1.1rem;
}

.submit-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.error {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: var(--error);
}

.error-shake-enter-active {
  animation: shake 0.4s;
}

@media (max-width: 500px) {
  .row {
    flex-wrap: wrap;
  }

  .submit-btn {
    width: 100%;
  }
}
</style>
