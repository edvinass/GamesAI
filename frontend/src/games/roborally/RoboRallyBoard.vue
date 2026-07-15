<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import type { RoboRallyGameState, RoboRallyRobot, Room } from '@/types'
import { CARD_LABELS, CARD_SHORT, FACING_ARROW } from './rules'

const props = defineProps<{
  gameState: RoboRallyGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const selectedCardId = ref<string | null>(null)
const selectedSlotIndex = ref<number | null>(null)
const displayRobots = ref<Record<string, RoboRallyRobot>>({})
const isAnimating = ref(false)
const animStepLabel = ref('')
let animationToken = 0
let animationTimer: ReturnType<typeof setTimeout> | null = null
let lastReplayedLogKey = ''

/** Hold each sub-step so the race is readable one action at a time. */
const EXEC_STEP_MS = 550
const EXEC_REGISTER_PAUSE_MS = 350

interface ExecFrame {
  player_id: string
  before: { x: number; y: number; facing: RoboRallyRobot['facing'] }
  after: { x: number; y: number; facing: RoboRallyRobot['facing'] }
  card_type?: string
  moved?: boolean
  step?: number
  phase?: 'card' | 'board'
}

function cloneRobots(robots: Record<string, RoboRallyRobot>) {
  return Object.fromEntries(
    Object.entries(robots).map(([id, robot]) => [id, { ...robot }]),
  )
}

function executionLogKey(log: Array<Record<string, unknown>> | undefined | null): string {
  if (!log?.length) return ''
  return JSON.stringify(log)
}

function flattenExecutionLog(log: Array<Record<string, unknown>>): ExecFrame[] {
  const frames: ExecFrame[] = []
  for (const entry of log) {
    const step = typeof entry.step === 'number' ? entry.step : undefined
    if (entry.type === 'register_step' && Array.isArray(entry.robots)) {
      for (const raw of entry.robots as ExecFrame[]) {
        if (raw.before && raw.after && raw.player_id) {
          frames.push({ ...raw, step: raw.step ?? step, phase: 'card' })
        }
      }
    }
    if (entry.type === 'board_step' && Array.isArray(entry.events)) {
      for (const raw of entry.events as Array<Record<string, unknown>>) {
        const before = raw.before as ExecFrame['before'] | undefined
        const after = raw.after as ExecFrame['after'] | undefined
        if (before && after && typeof raw.player_id === 'string') {
          const eventType = String(raw.type ?? raw.card_type ?? 'board')
          frames.push({
            player_id: raw.player_id,
            before,
            after,
            card_type: eventType,
            moved: before.x !== after.x || before.y !== after.y || before.facing !== after.facing,
            step: typeof raw.step === 'number' ? raw.step : step,
            phase: 'board',
          })
        }
      }
    }
  }
  return frames
}

function frameLabel(frame: ExecFrame): string {
  const register =
    typeof frame.step === 'number' ? `Register ${frame.step + 1}` : 'Register'
  const action = frame.card_type
    ? (CARD_LABELS[frame.card_type] ?? frame.card_type.replace(/_/g, ' '))
    : frame.phase === 'board'
      ? 'Board'
      : 'Card'
  const nick =
    props.gameState.players.find((p) => p.id === frame.player_id)?.nickname ?? 'Robot'
  const blocked = frame.moved === false && frame.phase === 'card' ? ' (blocked)' : ''
  return `${register} · ${nick}: ${action}${blocked}`
}

function sleep(ms: number, token: number) {
  return new Promise<void>((resolve) => {
    animationTimer = setTimeout(() => {
      animationTimer = null
      resolve()
    }, ms)
  }).then(() => {
    if (token !== animationToken) {
      throw new Error('animation-cancelled')
    }
  })
}

function cancelAnimation() {
  animationToken += 1
  if (animationTimer) {
    clearTimeout(animationTimer)
    animationTimer = null
  }
}

async function replayExecution(log: Array<Record<string, unknown>>) {
  const token = ++animationToken
  const frames = flattenExecutionLog(log)
  if (!frames.length) {
    displayRobots.value = cloneRobots(props.gameState.robots)
    isAnimating.value = false
    animStepLabel.value = ''
    return
  }

  isAnimating.value = true
  const positions: Record<string, RoboRallyRobot> = {}

  // Rewind every robot to its first logged position for this execution.
  for (const frame of frames) {
    if (positions[frame.player_id]) continue
    const serverRobot = props.gameState.robots[frame.player_id]
    if (!serverRobot) continue
    positions[frame.player_id] = {
      ...serverRobot,
      x: frame.before.x,
      y: frame.before.y,
      facing: frame.before.facing,
    }
  }

  for (const player of props.gameState.players) {
    if (!positions[player.id] && props.gameState.robots[player.id]) {
      positions[player.id] = { ...props.gameState.robots[player.id] }
    }
  }

  displayRobots.value = cloneRobots(positions)

  try {
    let previousStep: number | undefined
    for (const frame of frames) {
      if (token !== animationToken) return

      if (previousStep !== undefined && frame.step !== undefined && frame.step !== previousStep) {
        animStepLabel.value = `Register ${frame.step + 1}`
        await sleep(EXEC_REGISTER_PAUSE_MS, token)
      }
      previousStep = frame.step

      animStepLabel.value = frameLabel(frame)
      // Show the "before" pose briefly, then apply the move.
      await sleep(EXEC_STEP_MS, token)

      const current = displayRobots.value[frame.player_id]
      if (!current) continue

      displayRobots.value = {
        ...displayRobots.value,
        [frame.player_id]: {
          ...current,
          x: frame.after.x,
          y: frame.after.y,
          facing: frame.after.facing,
          checkpoints_reached:
            typeof (frame as { checkpoints_reached?: number }).checkpoints_reached === 'number'
              ? (frame as { checkpoints_reached: number }).checkpoints_reached
              : current.checkpoints_reached,
        },
      }
    }

    if (token !== animationToken) return
    // Brief hold on the final pose before handing control back.
    await sleep(EXEC_REGISTER_PAUSE_MS, token)
    displayRobots.value = cloneRobots(props.gameState.robots)
    isAnimating.value = false
    animStepLabel.value = ''
  } catch (err) {
    if (err instanceof Error && err.message === 'animation-cancelled') return
    throw err
  }
}

// Watch a stable key so later WS updates (AI programming, card places) with the
// same execution_log do not cancel the step-by-step replay.
watch(
  () => executionLogKey(props.gameState.execution_log),
  (logKey) => {
    if (logKey && logKey === lastReplayedLogKey) {
      return
    }

    cancelAnimation()

    if (!logKey) {
      lastReplayedLogKey = ''
      displayRobots.value = cloneRobots(props.gameState.robots)
      isAnimating.value = false
      animStepLabel.value = ''
      return
    }

    lastReplayedLogKey = logKey
    void replayExecution(props.gameState.execution_log)
  },
  { immediate: true },
)

watch(
  () => props.gameState.robots,
  (robots) => {
    if (!isAnimating.value) {
      displayRobots.value = cloneRobots(robots)
    }
  },
  { deep: true },
)

function clearSelection() {
  selectedCardId.value = null
  selectedSlotIndex.value = null
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') clearSelection()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  cancelAnimation()
  window.removeEventListener('keydown', onKeydown)
})

const robotsForDisplay = computed(() =>
  isAnimating.value || Object.keys(displayRobots.value).length
    ? displayRobots.value
    : props.gameState.robots,
)

const myPlayer = computed(() =>
  props.gameState.players.find((p) => p.id === props.playerId),
)

const isSpectator = computed(() => !myPlayer.value)

const myRobot = computed(() => props.gameState.robots[props.playerId])

const myHand = computed(() => props.gameState.hands[props.playerId] ?? [])

const myProgram = computed(() => props.gameState.programs[props.playerId] ?? [])

const isLocked = computed(() => props.gameState.lock_status[props.playerId] ?? false)

const myRegisterLocks = computed(
  () => props.gameState.register_locks?.[props.playerId] ?? [],
)

const canProgram = computed(
  () =>
    props.gameState.phase === 'programming' &&
    !isLocked.value &&
    !props.gameState.winner &&
    !isSpectator.value &&
    !myRobot.value?.powered_down &&
    !myRobot.value?.eliminated,
)

const registerFilled = computed(() =>
  myProgram.value.every((slot, i) => {
    if (myRegisterLocks.value[i]) return true
    return !!(slot && !slot.hidden)
  }),
)

const powerDownNext = ref(false)

const filledSlotCount = computed(
  () => myProgram.value.filter((slot) => slot && !slot.hidden).length,
)

const programmingHint = computed(() => {
  if (!canProgram.value) return ''
  if (selectedCardId.value) {
    return 'Click a register slot to place or replace'
  }
  if (selectedSlotIndex.value != null) {
    const slot = myProgram.value[selectedSlotIndex.value]
    if (slot && !slot.hidden) {
      return 'Click another slot to move, or a hand card to replace'
    }
    return `Choose a hand card for slot ${selectedSlotIndex.value + 1}`
  }
  if (filledSlotCount.value === 0) {
    return 'Click a card to fill the next slot'
  }
  if (!registerFilled.value) {
    return 'Click cards to fill — or pick a slot first'
  }
  return 'Click a slot to reorder, or lock when ready'
})

watch(
  () =>
    [
      props.gameState.phase,
      props.gameState.round,
      props.gameState.lock_status[props.playerId] ?? false,
    ] as const,
  () => clearSelection(),
)

const board = computed(() => props.gameState.board)

const boardAspect = computed(() => `${board.value.width} / ${board.value.height}`)

const edgeWallSet = computed(() => {
  const set = new Set<string>()
  for (const w of board.value.walls ?? []) {
    if (Array.isArray(w)) {
      const [x, y] = w
      for (const d of ['N', 'E', 'S', 'W']) set.add(`${x},${y},${d}`)
    } else if (w && typeof w === 'object') {
      set.add(`${w.x},${w.y},${w.dir}`)
    }
  }
  return set
})

const checkpointMap = computed(() => {
  const map = new Map<string, number>()
  for (const [x, y, num] of board.value.checkpoints) {
    map.set(`${x},${y}`, num)
  }
  return map
})

const pitSet = computed(() => new Set((board.value.pits ?? []).map(([x, y]) => `${x},${y}`)))
const repairSet = computed(() => new Set((board.value.repairs ?? []).map(([x, y]) => `${x},${y}`)))
const upgradeSet = computed(() => new Set((board.value.upgrades ?? []).map(([x, y]) => `${x},${y}`)))

const conveyorMap = computed(() => {
  const map = new Map<string, { dir: string; express: boolean }>()
  for (const c of board.value.conveyors ?? []) {
    map.set(`${c.x},${c.y}`, { dir: c.dir, express: !!c.express })
  }
  return map
})

const gearMap = computed(() => {
  const map = new Map<string, string>()
  for (const g of board.value.gears ?? []) map.set(`${g.x},${g.y}`, g.dir)
  return map
})

const pusherMap = computed(() => {
  const map = new Map<string, { dir: string; registers: number[] }>()
  for (const p of board.value.pushers ?? []) {
    map.set(`${p.x},${p.y}`, { dir: p.dir, registers: p.registers })
  }
  return map
})

const crusherMap = computed(() => {
  const map = new Map<string, number[]>()
  for (const c of board.value.crushers ?? []) map.set(`${c.x},${c.y}`, c.registers)
  return map
})

const laserMap = computed(() => {
  const map = new Map<string, { dir: string; strength: number }>()
  for (const laser of board.value.lasers ?? []) {
    map.set(`${laser.x},${laser.y}`, { dir: laser.dir, strength: laser.strength ?? 1 })
  }
  return map
})

const robotAt = computed(() => {
  const map = new Map<string, { playerId: string; facing: string; color: string; nickname: string }>()
  for (const player of props.gameState.players) {
    const robot = robotsForDisplay.value[player.id]
    if (robot && !robot.eliminated) {
      map.set(`${robot.x},${robot.y}`, {
        playerId: player.id,
        facing: robot.facing,
        color: player.color,
        nickname: player.nickname,
      })
    }
  }
  return map
})

const cols = computed(() => Array.from({ length: board.value.width }, (_, i) => i))
const rows = computed(() => Array.from({ length: board.value.height }, (_, i) => i))

const phaseLabel = computed(() => {
  const gs = props.gameState
  if (gs.winner) return 'Finished'
  if (isAnimating.value || gs.phase === 'executing') return 'Executing'
  if (canProgram.value) return 'Programming'
  if (isLocked.value) return 'Waiting'
  return 'Programming'
})

const phaseClass = computed(() => {
  const gs = props.gameState
  if (gs.winner) return 'phase--finished'
  if (isAnimating.value || gs.phase === 'executing') return 'phase--executing'
  if (canProgram.value) return 'phase--programming'
  if (isLocked.value) return 'phase--waiting'
  return 'phase--programming'
})

const statusText = computed(() => {
  const gs = props.gameState
  if (gs.winner) {
    const winner = gs.players.find((p) => p.id === gs.winner)
    if (gs.win_reason === 'checkpoints') {
      return `${winner?.nickname ?? 'Winner'} reached all checkpoints`
    }
    return `${winner?.nickname ?? 'Winner'} wins`
  }
  if (isAnimating.value && animStepLabel.value) {
    return animStepLabel.value
  }
  if (gs.phase === 'executing') {
    return 'Robots are running this round\'s program…'
  }
  if (isLocked.value) {
    return 'Your program is locked — waiting for other racers'
  }
  if (canProgram.value) {
    return programmingHint.value || 'Pick cards from your hand and fill every register slot'
  }
  return 'Watch the race unfold'
})

const priorityList = computed(() =>
  props.gameState.register_order.map((pid, i) => ({
    rank: i + 1,
    player: props.gameState.players.find((p) => p.id === pid),
    robot: robotsForDisplay.value[pid] ?? props.gameState.robots[pid],
    locked: props.gameState.lock_status[pid] ?? false,
    isMe: pid === props.playerId,
  })),
)

function isAntenna(x: number, y: number): boolean {
  const [ax, ay] = board.value.antenna
  return x === ax && y === ay
}

function hasEdge(x: number, y: number, dir: string): boolean {
  return edgeWallSet.value.has(`${x},${y},${dir}`)
}

function checkpointNum(x: number, y: number): number | null {
  return checkpointMap.value.get(`${x},${y}`) ?? null
}

function robotOn(x: number, y: number) {
  return robotAt.value.get(`${x},${y}`)
}

function isPit(x: number, y: number): boolean {
  return pitSet.value.has(`${x},${y}`)
}

function floorShade(x: number, y: number): string {
  return (x + y) % 2 === 0 ? 'floor-a' : 'floor-b'
}

function conveyorAt(x: number, y: number) {
  return conveyorMap.value.get(`${x},${y}`)
}

function gearAt(x: number, y: number) {
  return gearMap.value.get(`${x},${y}`)
}

function pusherAt(x: number, y: number) {
  return pusherMap.value.get(`${x},${y}`)
}

function crusherAt(x: number, y: number) {
  return crusherMap.value.get(`${x},${y}`)
}

function laserAt(x: number, y: number) {
  return laserMap.value.get(`${x},${y}`)
}

function isRegisterLocked(i: number): boolean {
  return !!myRegisterLocks.value[i]
}

function firstEmptySlot(): number | null {
  const index = myProgram.value.findIndex(
    (slot, i) => !isRegisterLocked(i) && (!slot || slot.hidden),
  )
  return index >= 0 ? index : null
}

function placeCard(slotIndex: number, cardId: string) {
  if (isRegisterLocked(slotIndex)) return
  emit('action', {
    type: 'place_card',
    slot_index: slotIndex,
    card_id: cardId,
  })
  clearSelection()
}

function selectCard(cardId: string) {
  if (!canProgram.value) return

  if (selectedSlotIndex.value != null) {
    placeCard(selectedSlotIndex.value, cardId)
    return
  }

  if (selectedCardId.value === cardId) {
    clearSelection()
    return
  }

  const empty = firstEmptySlot()
  if (empty != null) {
    placeCard(empty, cardId)
    return
  }

  selectedCardId.value = cardId
}

function onSlotClick(slotIndex: number) {
  if (!canProgram.value) return
  if (isRegisterLocked(slotIndex)) return

  if (selectedCardId.value) {
    placeCard(slotIndex, selectedCardId.value)
    return
  }

  if (selectedSlotIndex.value === slotIndex) {
    clearSelection()
    return
  }

  if (selectedSlotIndex.value != null) {
    emit('action', {
      type: 'swap_slots',
      from_index: selectedSlotIndex.value,
      to_index: slotIndex,
    })
    clearSelection()
    return
  }

  selectedSlotIndex.value = slotIndex
}

function clearSlot(slotIndex: number) {
  if (isRegisterLocked(slotIndex)) return
  if (!canProgram.value) return
  const slot = myProgram.value[slotIndex]
  if (!slot || slot.hidden) return
  emit('action', { type: 'clear_slot', slot_index: slotIndex })
  if (selectedSlotIndex.value === slotIndex) clearSelection()
}

function clearAllSlots() {
  if (!canProgram.value || filledSlotCount.value === 0) return
  for (let i = 0; i < myProgram.value.length; i++) {
    if (isRegisterLocked(i)) continue
    const slot = myProgram.value[i]
    if (slot && !slot.hidden) {
      emit('action', { type: 'clear_slot', slot_index: i })
    }
  }
  clearSelection()
}

function lockProgram() {
  if (!canProgram.value || !registerFilled.value) return
  emit('action', {
    type: 'lock_program',
    ...(powerDownNext.value ? { power_down: true } : {}),
  })
}

function slotTitle(slot: { type?: string; hidden?: boolean } | null | undefined, index: number) {
  if (!canProgram.value) {
    return slot && !slot.hidden ? cardTitle(slot) : `Register slot ${index + 1}`
  }
  if (selectedCardId.value) {
    return slot && !slot.hidden
      ? `Replace with selected card`
      : `Place selected card in slot ${index + 1}`
  }
  if (selectedSlotIndex.value === index) {
    return 'Selected — click another slot to move, or Esc to cancel'
  }
  if (selectedSlotIndex.value != null) {
    return `Move here from slot ${selectedSlotIndex.value + 1}`
  }
  if (slot && !slot.hidden) {
    return `${cardTitle(slot)} — click to move`
  }
  return `Empty slot ${index + 1} — click to target, then pick a card`
}

function resign() {
  if (isSpectator.value || props.gameState.winner) return
  if (window.confirm('Forfeit this race?')) {
    emit('action', { type: 'resign' })
  }
}

function cardLabel(card: { type?: string; hidden?: boolean }) {
  if (card.hidden || !card.type) return '?'
  return CARD_SHORT[card.type] ?? card.type
}

function cardTitle(card: { type?: string; hidden?: boolean }) {
  if (card.hidden || !card.type) return 'Hidden card'
  return CARD_LABELS[card.type] ?? card.type
}

function cardTypeClass(type?: string): string {
  if (!type) return 'card--unknown'
  if (type.startsWith('move_')) return 'card--move'
  if (type.startsWith('turn_')) return 'card--turn'
  if (type === 'backup') return 'card--backup'
  return 'card--unknown'
}
</script>

<template>
  <div class="roborally-board">
    <header class="status-bar">
      <div class="status-left">
        <span class="phase-badge" :class="phaseClass">{{ phaseLabel }}</span>
        <div class="status-copy">
          <h2 class="map-name">{{ board.name }}</h2>
          <p class="status-line">{{ statusText }}</p>
        </div>
      </div>

      <div class="status-stats">
        <div class="stat-pill">
          <span class="stat-label">Round</span>
          <span class="stat-value">{{ gameState.round }}</span>
        </div>
        <div v-if="myRobot && !isSpectator" class="stat-pill stat-pill--accent">
          <span class="stat-label">Checkpoints</span>
          <span class="stat-value">{{ myRobot.checkpoints_reached }} / {{ gameState.total_checkpoints }}</span>
        </div>
        <div v-if="myRobot && !isSpectator" class="stat-pill">
          <span class="stat-label">Damage</span>
          <span class="stat-value">{{ myRobot.damage ?? 0 }}/9</span>
        </div>
        <div v-if="myRobot && !isSpectator" class="stat-pill">
          <span class="stat-label">Lives</span>
          <span class="stat-value">{{ myRobot.lives ?? 3 }}</span>
        </div>
      </div>

      <button
        v-if="!isSpectator && !gameState.winner"
        type="button"
        class="btn-secondary forfeit-btn"
        @click="resign"
      >
        Forfeit
      </button>
    </header>

    <div class="main-stage">
      <div class="arena">
        <div class="grid-frame">
          <div
            class="grid"
            :style="{
              aspectRatio: boardAspect,
              gridTemplateColumns: `repeat(${board.width}, 1fr)`,
              gridTemplateRows: `repeat(${board.height}, 1fr)`,
            }"
          >
            <template v-for="y in rows" :key="'row-' + y">
              <div
                v-for="x in cols"
                :key="`${x}-${y}`"
                class="cell"
                :class="[
                  floorShade(x, y),
                  {
                    floor: !isPit(x, y),
                    pit: isPit(x, y),
                    antenna: isAntenna(x, y),
                    checkpoint: checkpointNum(x, y) != null,
                    repair: repairSet.has(`${x},${y}`),
                    upgrade: upgradeSet.has(`${x},${y}`),
                    'edge-n': hasEdge(x, y, 'N'),
                    'edge-e': hasEdge(x, y, 'E'),
                    'edge-s': hasEdge(x, y, 'S'),
                    'edge-w': hasEdge(x, y, 'W'),
                  },
                ]"
              >
                <span
                  v-if="conveyorAt(x, y)"
                  class="tile-belt"
                  :class="{ express: conveyorAt(x, y)!.express }"
                >{{ FACING_ARROW[conveyorAt(x, y)!.dir] }}</span>
                <span v-if="gearAt(x, y)" class="tile-gear">{{ gearAt(x, y) === 'left' ? '↺' : '↻' }}</span>
                <span v-if="pusherAt(x, y)" class="tile-pusher" :title="`Pusher ${pusherAt(x, y)!.registers}`">
                  {{ FACING_ARROW[pusherAt(x, y)!.dir] }}P
                </span>
                <span v-if="crusherAt(x, y)" class="tile-crusher" :title="`Crusher ${crusherAt(x, y)}`">X</span>
                <span v-if="laserAt(x, y)" class="tile-laser">{{ FACING_ARROW[laserAt(x, y)!.dir] }}</span>
                <span v-if="repairSet.has(`${x},${y}`)" class="tile-site">R</span>
                <span v-if="upgradeSet.has(`${x},${y}`)" class="tile-site tile-upgrade">U</span>
                <span v-if="checkpointNum(x, y)" class="cp-ring">
                  <span class="cp-num">{{ checkpointNum(x, y) }}</span>
                </span>
                <span v-if="isAntenna(x, y)" class="antenna-glow">
                  <span class="antenna-icon">A</span>
                </span>
                <div
                  v-if="robotOn(x, y)"
                  class="robot"
                  :class="{
                    'robot--me': robotOn(x, y)?.playerId === playerId,
                    'robot--animating': isAnimating,
                  }"
                  :style="{ '--robot-color': robotOn(x, y)?.color }"
                  :title="robotOn(x, y)?.nickname"
                >
                  <span class="robot-shell" />
                  <span class="robot-arrow">{{ FACING_ARROW[robotOn(x, y)!.facing] }}</span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <aside class="racers-panel">
        <div class="panel-head">
          <h3>Register order</h3>
          <span class="panel-sub">Closest to antenna first</span>
        </div>
        <ol class="racer-list">
          <li
            v-for="entry in priorityList"
            :key="entry.player?.id"
            class="racer-card"
            :class="{ 'racer-card--me': entry.isMe, 'racer-card--locked': entry.locked }"
          >
            <span class="racer-rank">{{ entry.rank }}</span>
            <span class="racer-dot" :style="{ background: entry.player?.color }" />
            <div class="racer-info">
              <span class="racer-name">
                {{ entry.player?.nickname }}
                <span v-if="entry.isMe" class="you-tag">You</span>
              </span>
              <div class="cp-track">
                <div
                  class="cp-fill"
                  :style="{ width: `${((entry.robot?.checkpoints_reached ?? 0) / gameState.total_checkpoints) * 100}%`, background: entry.player?.color }"
                />
              </div>
            </div>
            <span class="racer-meta">
              <span class="racer-cp">{{ entry.robot?.checkpoints_reached ?? 0 }}/{{ gameState.total_checkpoints }}</span>
              <span class="racer-hp" title="Damage / lives">{{ entry.robot?.damage ?? 0 }}★{{ entry.robot?.lives ?? 3 }}</span>
              <span v-if="entry.locked" class="lock-icon" title="Program locked">L</span>
            </span>
          </li>
        </ol>
      </aside>
    </div>

    <section v-if="!isSpectator" class="programming-dock" :class="{ 'dock--programming': canProgram }">
      <div class="dock-section dock-register">
        <div class="dock-head">
          <span class="dock-label">Register</span>
          <div class="dock-head-right">
            <span class="dock-count">{{ filledSlotCount }} / {{ gameState.register_size }}</span>
            <button
              v-if="canProgram && filledSlotCount > 0"
              type="button"
              class="clear-all-btn"
              title="Return all cards to hand"
              @click="clearAllSlots"
            >
              Clear all
            </button>
          </div>
        </div>
        <div class="register-slots">
          <div
            v-for="(slot, i) in myProgram"
            :key="'slot-' + i"
            class="slot-wrap"
          >
            <button
              type="button"
              class="slot"
              :class="[
                cardTypeClass(slot?.type),
                {
                  filled: slot && !slot.hidden,
                  active: canProgram && !isRegisterLocked(i),
                  pulsing: canProgram && !isRegisterLocked(i) && !slot && selectedSlotIndex == null && !selectedCardId,
                  selected: selectedSlotIndex === i,
                  'slot--locked': isRegisterLocked(i),
                  'drop-target':
                    canProgram &&
                    !isRegisterLocked(i) &&
                    (selectedCardId != null ||
                      (selectedSlotIndex != null && selectedSlotIndex !== i)),
                },
              ]"
              :disabled="!canProgram || isRegisterLocked(i)"
              :title="isRegisterLocked(i) ? 'Locked by damage' : slotTitle(slot, i)"
              @click="onSlotClick(i)"
            >
              <span class="slot-num">{{ i + 1 }}{{ isRegisterLocked(i) ? '·' : '' }}</span>
              <span v-if="slot && !slot.hidden" class="slot-card">{{ cardLabel(slot) }}</span>
              <span v-else class="slot-empty">+</span>
            </button>
            <button
              v-if="canProgram && slot && !slot.hidden && !isRegisterLocked(i)"
              type="button"
              class="slot-clear"
              title="Return to hand"
              aria-label="Clear register slot"
              @click.stop="clearSlot(i)"
            >
              ×
            </button>
          </div>
        </div>
      </div>

      <div class="dock-section dock-hand">
        <div class="dock-head">
          <span class="dock-label">Hand</span>
          <span v-if="canProgram" class="dock-hint">{{ programmingHint }}</span>
        </div>
        <div class="hand-cards">
          <button
            v-for="card in myHand"
            :key="card.id"
            type="button"
            class="hand-card"
            :class="[
              cardTypeClass(card.type),
              {
                selected: selectedCardId === card.id,
                hidden: card.hidden,
                'place-ready': canProgram && selectedSlotIndex != null && !card.hidden,
              },
            ]"
            :disabled="!canProgram || card.hidden"
            :title="
              canProgram && selectedSlotIndex != null
                ? `Place in slot ${selectedSlotIndex + 1}`
                : cardTitle(card)
            "
            @click="selectCard(card.id)"
          >
            <span class="hand-card-glyph">{{ card.hidden ? '?' : cardLabel(card) }}</span>
            <span v-if="!card.hidden && card.type" class="hand-card-name">{{ CARD_LABELS[card.type] }}</span>
          </button>
        </div>
      </div>

      <div class="dock-actions">
        <label v-if="canProgram" class="power-down-label">
          <input v-model="powerDownNext" type="checkbox" />
          Power down next round
        </label>
        <button
          type="button"
          class="lock-btn"
          :class="{ ready: registerFilled && canProgram, locked: isLocked }"
          :disabled="!canProgram || !registerFilled"
          @click="lockProgram"
        >
          <span class="lock-btn-icon">{{ isLocked ? '✓' : '▶' }}</span>
          <span>{{ isLocked ? 'Locked in' : 'Lock program' }}</span>
        </button>
      </div>
    </section>

    <section v-else class="spectator-dock">
      <p>Spectating — you are not racing in this game.</p>
    </section>
  </div>
</template>

<style scoped>
.roborally-board {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.65rem 1rem 1rem;
  background:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.12), transparent),
    linear-gradient(180deg, rgba(15, 23, 42, 0.4) 0%, transparent 30%);
}

/* ── Status bar ── */
.status-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.85rem 1.15rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.15);
  backdrop-filter: blur(8px);
}

.status-left {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  flex: 1;
  min-width: 200px;
}

.phase-badge {
  flex-shrink: 0;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.phase--programming {
  background: rgba(34, 197, 94, 0.18);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.phase--waiting {
  background: rgba(234, 179, 8, 0.18);
  color: #fde047;
  border: 1px solid rgba(234, 179, 8, 0.35);
}

.phase--executing {
  background: rgba(59, 130, 246, 0.18);
  color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.35);
  animation: pulse-phase 1.5s ease-in-out infinite;
}

.phase--finished {
  background: rgba(168, 85, 247, 0.18);
  color: #d8b4fe;
  border: 1px solid rgba(168, 85, 247, 0.35);
}

@keyframes pulse-phase {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.status-copy {
  min-width: 0;
}

.map-name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.status-line {
  margin: 0.15rem 0 0;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.status-stats {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.4rem 0.85rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
  min-width: 4.5rem;
}

.stat-pill--accent {
  border-color: rgba(250, 204, 21, 0.25);
  background: rgba(250, 204, 21, 0.06);
}

.stat-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.stat-value {
  font-size: 1rem;
  font-weight: 800;
  margin-top: 0.1rem;
}

.forfeit-btn {
  flex-shrink: 0;
}

/* ── Main stage ── */
.main-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr min(240px, 24vw);
  gap: 0.75rem;
}

@media (max-width: 860px) {
  .main-stage {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }

  .racers-panel {
    max-height: 140px;
  }

  .racer-list {
    flex-direction: row !important;
    overflow-x: auto;
  }

  .racer-card {
    min-width: 180px;
  }
}

.arena {
  min-height: 0;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  border-radius: 16px;
  background:
    linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.6));
  border: 1px solid rgba(148, 163, 184, 0.12);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 8px 32px rgba(0, 0, 0, 0.25);
}

.grid-frame {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem;
}

.grid {
  display: grid;
  gap: 3px;
  height: 100%;
  width: auto;
  max-width: 100%;
  padding: 6px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.35);
  box-shadow: inset 0 2px 12px rgba(0, 0, 0, 0.4);
}

.cell {
  position: relative;
  min-width: 0;
  min-height: 0;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cell.floor-a {
  background: linear-gradient(145deg, #1a2744, #152038);
}

.cell.floor-b {
  background: linear-gradient(145deg, #162035, #121a2e);
}

.cell.floor::after {
  content: '';
  position: absolute;
  inset: 2px;
  border-radius: 3px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  pointer-events: none;
}

.cell.pit {
  background: radial-gradient(circle at center, #020617, #0f172a) !important;
}

.cell.edge-n { border-top: 3px solid #94a3b8; }
.cell.edge-e { border-right: 3px solid #94a3b8; }
.cell.edge-s { border-bottom: 3px solid #94a3b8; }
.cell.edge-w { border-left: 3px solid #94a3b8; }

.tile-belt,
.tile-gear,
.tile-pusher,
.tile-crusher,
.tile-laser,
.tile-site {
  position: absolute;
  font-size: clamp(0.55rem, 1.6vw, 0.85rem);
  font-weight: 700;
  opacity: 0.9;
  pointer-events: none;
  z-index: 1;
}

.tile-belt { color: #eab308; }
.tile-belt.express { color: #f97316; }
.tile-gear { color: #a78bfa; }
.tile-pusher { color: #38bdf8; font-size: clamp(0.4rem, 1.1vw, 0.65rem); }
.tile-crusher { color: #f87171; }
.tile-laser { color: #fb7185; top: 2px; left: 2px; }
.tile-site { color: #4ade80; bottom: 2px; right: 3px; }
.tile-upgrade { color: #22d3ee; }

.slot--locked {
  opacity: 0.65;
  outline: 1px solid rgba(248, 113, 113, 0.55);
}

.power-down-label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  cursor: pointer;
}

.racer-hp {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.cell.checkpoint {
  box-shadow: inset 0 0 0 2px rgba(250, 204, 21, 0.45);
}

.cell.antenna {
  background: radial-gradient(circle at center, #4338ca, #312e81);
}

.cp-ring {
  position: absolute;
  inset: 12%;
  border-radius: 50%;
  border: 2px solid rgba(250, 204, 21, 0.55);
  background: rgba(250, 204, 21, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.cp-num {
  font-size: clamp(0.7rem, 1.4vmin, 1.15rem);
  font-weight: 900;
  color: #fde047;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}

.antenna-glow {
  position: relative;
  z-index: 1;
  animation: antenna-pulse 2s ease-in-out infinite;
}

.antenna-icon {
  font-size: clamp(0.9rem, 2vmin, 1.4rem);
  filter: drop-shadow(0 0 6px rgba(129, 140, 248, 0.8));
}

@keyframes antenna-pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.08); opacity: 1; }
}

.robot {
  position: relative;
  width: 78%;
  height: 78%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3;
}

.robot--me .robot-shell {
  box-shadow:
    0 0 0 2px rgba(255, 255, 255, 0.85),
    0 0 14px var(--robot-color),
    0 4px 10px rgba(0, 0, 0, 0.45);
}

.robot--animating .robot-shell {
  transition: transform 0.2s ease;
}

.robot-shell {
  width: 100%;
  height: 100%;
  border-radius: 6px;
  background: linear-gradient(145deg, var(--robot-color), color-mix(in srgb, var(--robot-color) 70%, black));
  border: 2px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.45);
}

.robot-arrow {
  position: absolute;
  font-size: clamp(0.9rem, 2.2vmin, 1.5rem);
  font-weight: 900;
  color: white;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
}

/* ── Racers panel ── */
.racers-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.panel-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
}

.panel-sub {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.racer-list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
  flex: 1;
}

.racer-card {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.55);
  border: 1px solid transparent;
}

.racer-card--me {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.1);
}

.racer-card--locked {
  opacity: 0.85;
}

.racer-rank {
  width: 1.25rem;
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--text-muted);
  text-align: center;
}

.racer-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
}

.racer-info {
  flex: 1;
  min-width: 0;
}

.racer-name {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.you-tag {
  margin-left: 0.35rem;
  font-size: 0.65rem;
  font-weight: 700;
  color: #a5b4fc;
}

.cp-track {
  margin-top: 0.3rem;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  overflow: hidden;
}

.cp-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.35s ease;
}

.racer-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.15rem;
}

.racer-cp {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
}

.lock-icon {
  font-size: 0.75rem;
}

/* ── Programming dock ── */
.programming-dock {
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 6;
  display: grid;
  grid-template-columns: 1fr 1.4fr auto;
  gap: 1rem;
  align-items: end;
  padding: 1rem 1.15rem;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92));
  border: 1px solid rgba(148, 163, 184, 0.14);
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(10px);
}

.programming-dock.dock--programming {
  border-color: rgba(99, 102, 241, 0.28);
}

@media (max-width: 960px) {
  .programming-dock {
    grid-template-columns: 1fr;
    align-items: stretch;
    padding: 0.85rem 0.9rem calc(0.85rem + env(safe-area-inset-bottom, 0px));
  }

  .dock-actions {
    justify-content: stretch;
  }

  .lock-btn {
    width: 100%;
  }
}

.dock-section {
  min-width: 0;
}

.dock-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.55rem;
}

.dock-head-right {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.dock-label {
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
}

.dock-count,
.dock-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
}

.dock-hint {
  text-align: right;
  line-height: 1.3;
}

.clear-all-btn {
  border: none;
  background: transparent;
  color: rgba(248, 113, 113, 0.9);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  padding: 0.15rem 0.35rem;
  border-radius: 6px;
}

.clear-all-btn:hover {
  background: rgba(248, 113, 113, 0.12);
}

.register-slots,
.hand-cards {
  display: flex;
  gap: 0.55rem;
}

.register-slots {
  flex-wrap: wrap;
}

.hand-cards {
  flex-wrap: nowrap;
  overflow-x: auto;
  padding-bottom: 0.2rem;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch;
}

.slot-wrap {
  position: relative;
  flex: 0 0 auto;
}

.slot,
.hand-card {
  border: none;
  cursor: pointer;
  color: white;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.slot {
  width: clamp(3.75rem, 6vw, 5rem);
  height: clamp(4.75rem, 8vw, 6.25rem);
  min-width: 3.5rem;
  min-height: 4.5rem;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
  background: rgba(30, 41, 59, 0.8);
  border: 2px dashed rgba(148, 163, 184, 0.35);
}

.slot.pulsing.active:not(:disabled) {
  animation: slot-pulse 2s ease-in-out infinite;
}

@keyframes slot-pulse {
  0%, 100% { border-color: rgba(148, 163, 184, 0.35); }
  50% { border-color: rgba(99, 102, 241, 0.55); }
}

.slot.active:not(:disabled):hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.65);
}

.slot.filled {
  border-style: solid;
}

.slot.selected {
  transform: translateY(-3px);
  box-shadow:
    0 0 0 3px rgba(251, 191, 36, 0.55),
    0 8px 18px rgba(0, 0, 0, 0.3);
}

.slot.drop-target:not(.selected) {
  border-color: rgba(129, 140, 248, 0.75);
  box-shadow: inset 0 0 0 1px rgba(165, 180, 252, 0.25);
}

.slot.drop-target:not(.filled) {
  background: rgba(99, 102, 241, 0.18);
}

.slot.card--move.filled {
  background: linear-gradient(160deg, #059669, #047857);
  border-color: rgba(110, 231, 183, 0.5);
}

.slot.card--turn.filled {
  background: linear-gradient(160deg, #0284c7, #0369a1);
  border-color: rgba(125, 211, 252, 0.5);
}

.slot.card--backup.filled {
  background: linear-gradient(160deg, #d97706, #b45309);
  border-color: rgba(253, 186, 116, 0.5);
}

.slot:disabled {
  opacity: 0.55;
  cursor: default;
}

.slot-clear {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 999px;
  border: 1px solid rgba(248, 113, 113, 0.45);
  background: rgba(15, 23, 42, 0.95);
  color: #fca5a5;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
  z-index: 1;
}

.slot-clear:hover {
  background: rgba(127, 29, 29, 0.95);
  color: white;
}

.slot-num {
  font-size: 0.68rem;
  font-weight: 700;
  opacity: 0.75;
}

.slot-card {
  font-size: clamp(1.35rem, 2.5vw, 1.85rem);
  font-weight: 900;
  line-height: 1;
}

.slot-empty {
  font-size: 1.75rem;
  font-weight: 300;
  opacity: 0.45;
}

.hand-card {
  flex: 0 0 auto;
  width: clamp(4rem, 6.5vw, 5.25rem);
  height: clamp(5rem, 9vw, 6.75rem);
  min-width: 3.75rem;
  min-height: 4.75rem;
  padding: 0.45rem 0.35rem;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  border: 2px solid rgba(255, 255, 255, 0.12);
}

.hand-card.card--move {
  background: linear-gradient(165deg, #10b981, #065f46);
}

.hand-card.card--turn {
  background: linear-gradient(165deg, #0ea5e9, #075985);
}

.hand-card.card--backup {
  background: linear-gradient(165deg, #f59e0b, #92400e);
}

.hand-card.card--unknown,
.hand-card.hidden {
  background: linear-gradient(165deg, #64748b, #334155);
}

.hand-card.selected,
.hand-card.place-ready {
  transform: translateY(-4px) scale(1.04);
  box-shadow:
    0 0 0 3px rgba(99, 102, 241, 0.55),
    0 8px 20px rgba(0, 0, 0, 0.35);
}

.hand-card.place-ready:not(.selected) {
  box-shadow:
    0 0 0 2px rgba(251, 191, 36, 0.5),
    0 6px 16px rgba(0, 0, 0, 0.28);
}

.hand-card:not(:disabled):hover {
  transform: translateY(-2px);
}

.hand-card:disabled {
  opacity: 0.45;
  cursor: default;
}

.hand-card-glyph {
  font-size: clamp(1.4rem, 2.8vw, 2rem);
  font-weight: 900;
  line-height: 1;
}

.hand-card-name {
  font-size: 0.58rem;
  font-weight: 700;
  text-align: center;
  line-height: 1.15;
  opacity: 0.9;
}

.dock-actions {
  display: flex;
  align-items: flex-end;
  padding-bottom: 0.15rem;
}

.lock-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.35rem;
  border-radius: 12px;
  border: 2px solid rgba(148, 163, 184, 0.25);
  background: rgba(30, 41, 59, 0.9);
  color: var(--text-muted);
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.lock-btn.ready:not(:disabled) {
  background: linear-gradient(145deg, #6366f1, #4f46e5);
  border-color: rgba(165, 180, 252, 0.5);
  color: white;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
}

.lock-btn.ready:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.45);
}

.lock-btn.locked {
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.4);
  color: #86efac;
}

.lock-btn:disabled:not(.locked) {
  opacity: 0.5;
  cursor: default;
}

.lock-btn-icon {
  font-size: 1.1rem;
}

.spectator-dock {
  flex-shrink: 0;
  padding: 1rem 1.15rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(148, 163, 184, 0.12);
  text-align: center;
}

.spectator-dock p {
  margin: 0;
  color: var(--text-muted);
}
</style>
