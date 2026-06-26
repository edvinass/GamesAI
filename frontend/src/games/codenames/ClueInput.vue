<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [word: string, number: number]
}>()

const clueWord = ref('')
const clueNumber = ref(1)

function submit() {
  if (!clueWord.value.trim()) return
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
      <button class="btn-primary" @click="submit">Give Clue</button>
    </div>
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

@media (max-width: 500px) {
  .row {
    flex-wrap: wrap;
  }
}
</style>
