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

const boardWordSet = computed(() => getBoardWords(props.boardWords))

const validationError = computed(() => {
  if (!clueWord.value.trim()) return null
  return validateClueWord(clueWord.value, boardWordSet.value)
})

function submit() {
  if (!clueWord.value.trim() || validationError.value) return
  emit('submit', clueWord.value.trim(), clueNumber.value)
  clueWord.value = ''
}
</script>

<template>
  <div class="clue-input card">
    <h4>Your clue</h4>
    <div class="row">
      <input v-model="clueWord" placeholder="Clue word" maxlength="30" @keyup.enter="submit" />
      <input v-model.number="clueNumber" type="number" min="0" max="9" class="number-input" />
      <button class="btn-primary" :disabled="Boolean(validationError)" @click="submit">Give Clue</button>
    </div>
    <p v-if="validationError" class="error">{{ validationError }}</p>
  </div>
</template>

<style scoped>
.clue-input {
  width: 100%;
  max-width: 500px;
  padding: 1rem;
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
  flex: 0 0 60px !important;
  text-align: center;
}

.error {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: var(--danger, #e74c3c);
}

@media (max-width: 500px) {
  .row {
    flex-wrap: wrap;
  }
}
</style>
