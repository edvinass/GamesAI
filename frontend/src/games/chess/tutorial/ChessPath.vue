<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { lessons, lessonMark, sections } from './course'
import OscarBubble from './OscarBubble.vue'
import {
  emptyProgress,
  isCleared,
  isUnlocked,
  loadProgress,
  saveProgress,
  skipMatch,
  weakestLesson,
} from './progress'

const router = useRouter()
const progress = ref(loadProgress())

const groups = computed(() =>
  sections.map((section) => ({
    ...section,
    nodes: lessons
      .map((lesson, index) => ({ lesson, index }))
      .filter((node) => node.lesson.sectionId === section.id),
  })),
)

const nextUp = computed(() => {
  const open = lessons.findIndex(
    (lesson, index) => isUnlocked(progress.value, index) && !isCleared(progress.value, lesson),
  )
  if (open >= 0) return lessons[open]
  return null
})

const finished = computed(() => lessons.every((lesson) => isCleared(progress.value, lesson)))
const practice = computed(() => weakestLesson(progress.value))
const coach = computed(() => {
  if (finished.value) return 'You finished the path. Replay any lesson, or sit down for a real game.'
  if (!nextUp.value) return 'Pick a lesson.'
  return `${nextUp.value.title}. ${nextUp.value.summary}`
})

function openLesson(index: number) {
  if (!isUnlocked(progress.value, index)) return
  router.push(`/chess/learn/${lessons[index].id}`)
}

function resetProgress() {
  progress.value = emptyProgress()
  saveProgress(progress.value)
}

function skip(id: string) {
  progress.value = skipMatch(progress.value, id)
  saveProgress(progress.value)
}
</script>

<template>
  <div class="path-page">
    <header class="top">
      <button type="button" class="btn-secondary back" @click="router.push('/')">Home</button>
      <div>
        <p class="kicker">Chess course</p>
        <h1>Learn chess</h1>
      </div>
      <p class="xp">{{ progress.xp }} XP</p>
    </header>

    <OscarBubble :mood="finished ? 'happy' : 'idle'" :text="coach" />

    <button
      v-if="nextUp"
      type="button"
      class="btn-primary continue"
      @click="router.push(`/chess/learn/${nextUp.id}`)"
    >
      Continue · {{ nextUp.title }}
    </button>
    <p v-else class="done-note">Path complete.</p>

    <button
      v-if="practice"
      type="button"
      class="practice"
      @click="router.push(`/chess/learn/${practice.id}`)"
    >
      Practice {{ practice.title }} again. Best score is {{ progress.stars[practice.id] }}
      {{ progress.stars[practice.id] === 1 ? 'star' : 'stars' }}.
    </button>

    <div v-for="group in groups" :key="group.id" class="section">
      <header class="section-head">
        <p>Section {{ group.index }}</p>
        <h2>{{ group.title }}</h2>
        <span>{{ group.summary }}</span>
      </header>
      <ol class="trail">
        <li
          v-for="node in group.nodes"
          :key="node.lesson.id"
          :style="{ '--nudge': node.index % 2 === 0 ? '-72px' : '72px' }"
        >
          <button
            type="button"
            class="node"
            :class="{
              locked: !isUnlocked(progress, node.index),
              current: nextUp?.id === node.lesson.id,
              cleared: isCleared(progress, node.lesson),
            }"
            :disabled="!isUnlocked(progress, node.index)"
            @click="openLesson(node.index)"
          >
            <span class="mark">{{ lessonMark(node.lesson.kind) }}</span>
          </button>
          <div class="meta">
            <strong>{{ node.lesson.title }}</strong>
            <span v-if="progress.skipped.includes(node.lesson.id) && !(progress.stars[node.lesson.id] > 0)">
              Skipped
            </span>
            <span v-else class="stars" aria-hidden="true">
              <i v-for="n in 3" :key="n" :class="{ on: n <= (progress.stars[node.lesson.id] ?? 0) }">★</i>
            </span>
            <button
              v-if="
                node.lesson.kind === 'match' &&
                isUnlocked(progress, node.index) &&
                !isCleared(progress, node.lesson)
              "
              type="button"
              class="skip"
              @click="skip(node.lesson.id)"
            >
              Skip
            </button>
          </div>
        </li>
      </ol>
    </div>

    <button type="button" class="reset" @click="resetProgress">Reset course progress</button>
  </div>
</template>

<style scoped>
.path-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.25rem 1rem 3rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.top {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.top h1 {
  font-size: 1.6rem;
  line-height: 1.1;
}

.kicker {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.75rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.back {
  padding: 0.45rem 0.7rem;
}

.xp {
  margin-left: auto;
  color: #f0c14d;
  font-weight: 700;
}

.continue {
  align-self: center;
}

.done-note,
.practice {
  text-align: center;
}

.practice {
  background: transparent;
  color: var(--accent);
  padding: 0.4rem;
}

.section-head {
  text-align: center;
  margin-bottom: 0.4rem;
}

.section-head p,
.section-head span {
  color: var(--text-muted);
}

.section-head p {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-head h2 {
  font-size: 1.35rem;
}

.trail {
  list-style: none;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.5rem 0 1rem;
}

.trail::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 8px;
  transform: translateX(-50%);
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.08);
}

.trail li {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  transform: translateX(var(--nudge));
}

.node {
  width: 74px;
  height: 74px;
  border-radius: 50%;
  background: #1c6b4a;
  color: white;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.28);
  font-size: 1.45rem;
}

.node.current {
  box-shadow:
    0 0 0 4px rgba(61, 214, 140, 0.35),
    0 8px 18px rgba(0, 0, 0, 0.28);
}

.node.locked {
  background: #2a3344;
  color: var(--text-muted);
}

.meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 0.25rem;
  text-align: center;
}

.meta strong {
  font-size: 0.85rem;
}

.stars {
  color: rgba(255, 255, 255, 0.25);
  letter-spacing: 0.08em;
  font-style: normal;
}

.stars .on {
  color: #f0c14d;
}

.skip {
  margin-top: 0.15rem;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

.reset {
  align-self: center;
  background: transparent;
  color: var(--text-muted);
  font-weight: 500;
  margin-top: 0.5rem;
}

@media (max-width: 640px) {
  .trail li {
    --nudge: 0px !important;
    align-items: flex-start;
    padding-left: calc(50% - 37px);
  }

  .meta {
    align-items: flex-start;
    margin-left: 84px;
    margin-top: -58px;
    min-height: 58px;
    text-align: left;
  }
}
</style>
