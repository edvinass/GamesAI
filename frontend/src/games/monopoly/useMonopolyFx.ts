import { onUnmounted, ref, watch, type Ref } from 'vue'
import type { MonopolyGameState } from '@/types'
import {
  playAuctionBid,
  playAuctionStart,
  playBankrupt,
  playBuild,
  playBuy,
  playCardDraw,
  playCardFlip,
  playCashGain,
  playCashLoss,
  playDiceSettle,
  playDiceTick,
  playJail,
  playLand,
  playTokenHop,
  playWin,
  playYourTurn,
  unlockAudio,
} from './sounds'

export type FxKind =
  | 'dice'
  | 'land'
  | 'buy'
  | 'cash'
  | 'card'
  | 'auction'
  | 'jail'
  | 'build'
  | 'bankrupt'
  | 'toast'
  | 'banner'

export type BannerTone =
  | 'default'
  | 'dice'
  | 'doubles'
  | 'land'
  | 'buy'
  | 'build'
  | 'jail'
  | 'rent'
  | 'gain'
  | 'auction'
  | 'bankrupt'
  | 'win'
  | 'turn'
  | 'card'

export interface FxEvent {
  id: number
  kind: FxKind
  at: number
  spaceId?: number
  playerId?: string
  amount?: number
  dice?: [number, number]
  text?: string
  cardKind?: 'chance' | 'community_chest'
  color?: string
}

export interface BoardBanner {
  id: number
  title: string
  subtitle?: string
  tone: BannerTone
}

let fxSeq = 0

function nextId() {
  fxSeq += 1
  return fxSeq
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

/** Spaces visited walking forward from→to (exclusive of from, inclusive of to). */
function forwardPath(from: number, to: number): number[] {
  const path: number[] = []
  let p = from
  while (p !== to) {
    p = (p + 1) % 40
    path.push(p)
  }
  return path
}

/** Spaces visited walking backward from→to. */
function backwardPath(from: number, to: number): number[] {
  const path: number[] = []
  let p = from
  while (p !== to) {
    p = (p + 39) % 40
    path.push(p)
  }
  return path
}

function resolvePath(
  from: number,
  to: number,
  wentToJail: boolean,
): { path: number[]; teleport: boolean } {
  if (from === to) return { path: [], teleport: false }
  if (wentToJail && to === 10) {
    const fwd = (to - from + 40) % 40
    if (fwd === 0 || fwd > 6) return { path: [10], teleport: true }
  }
  const fwd = (to - from + 40) % 40
  const back = (from - to + 40) % 40
  if (back > 0 && back <= 3 && fwd > back) {
    return { path: backwardPath(from, to), teleport: false }
  }
  return { path: forwardPath(from, to), teleport: false }
}

export function useMonopolyFx(gameState: Ref<MonopolyGameState>) {
  const fx = ref<FxEvent[]>([])
  const movingPlayerId = ref<string | null>(null)
  const landPulseId = ref<number | null>(null)
  const buyFlashId = ref<number | null>(null)
  const hopSpaceId = ref<number | null>(null)
  const diceRolling = ref(false)
  const displayDice = ref<[number, number] | null>(null)
  const cardOverlay = ref<FxEvent | null>(null)
  const cardFlipped = ref(false)
  const cardLeaving = ref(false)
  const banner = ref<BoardBanner | null>(null)
  const cashFxByPlayer = ref<Record<string, FxEvent[]>>({})
  const displayPositions = ref<Record<string, number>>({})
  const boardBusy = ref(false)

  const timers: number[] = []
  const taskQueue: Array<() => Promise<void>> = []
  let pumping = false

  function later(ms: number, fn: () => void) {
    const id = window.setTimeout(fn, ms)
    timers.push(id)
    return id
  }

  function push(event: Omit<FxEvent, 'id' | 'at'>) {
    const full: FxEvent = { ...event, id: nextId(), at: Date.now() }
    fx.value = [...fx.value.slice(-24), full]
    return full
  }

  async function announce(
    title: string,
    opts: { subtitle?: string; tone?: BannerTone; ms?: number } = {},
  ) {
    const event: BoardBanner = {
      id: nextId(),
      title,
      subtitle: opts.subtitle,
      tone: opts.tone ?? 'default',
    }
    banner.value = event
    await sleep(opts.ms ?? 1100)
    if (banner.value?.id === event.id) banner.value = null
    await sleep(120)
  }

  function addCashFx(event: FxEvent) {
    if (!event.playerId) return
    const pid = event.playerId
    const current = cashFxByPlayer.value[pid] || []
    cashFxByPlayer.value = {
      ...cashFxByPlayer.value,
      [pid]: [...current, event],
    }
    later(1400, () => {
      cashFxByPlayer.value = {
        ...cashFxByPlayer.value,
        [pid]: (cashFxByPlayer.value[pid] || []).filter((e) => e.id !== event.id),
      }
    })
  }

  function initPositions(state: MonopolyGameState) {
    const map: Record<string, number> = {}
    for (const [id, p] of Object.entries(state.players)) {
      map[id] = p.position
    }
    displayPositions.value = map
  }

  function setDisplayPos(playerId: string, pos: number) {
    displayPositions.value = { ...displayPositions.value, [playerId]: pos }
  }

  async function enqueue(task: () => Promise<void>) {
    taskQueue.push(task)
    if (pumping) return
    pumping = true
    boardBusy.value = true
    while (taskQueue.length) {
      const next = taskQueue.shift()
      if (next) await next()
    }
    pumping = false
    boardBusy.value = false
  }

  async function animateDice(dice: [number, number]) {
    void unlockAudio()
    diceRolling.value = true
    displayDice.value = [1, 1]
    for (let i = 0; i < 10; i += 1) {
      displayDice.value = [
        1 + Math.floor(Math.random() * 6),
        1 + Math.floor(Math.random() * 6),
      ]
      playDiceTick()
      await sleep(70)
    }
    displayDice.value = dice
    diceRolling.value = false
    push({ kind: 'dice', dice })
    const doubles = dice[0] === dice[1]
    playDiceSettle(doubles)
    if (doubles) {
      await announce('DOUBLES!', {
        subtitle: `${dice[0]} + ${dice[1]}`,
        tone: 'doubles',
        ms: 1200,
      })
    } else {
      // Center dice already tell the story — brief hold, no banner spam
      await sleep(550)
    }
    displayDice.value = null
  }

  async function animateMove(
    playerId: string,
    from: number,
    to: number,
    wentToJail: boolean,
    nickname: string,
  ): Promise<{ passedGo: boolean }> {
    const { path, teleport } = resolvePath(from, to, wentToJail)
    movingPlayerId.value = playerId

    if (teleport) {
      playJail()
      await announce('GO TO JAIL', { subtitle: nickname, tone: 'jail', ms: 1600 })
      setDisplayPos(playerId, 10)
      landPulseId.value = 10
      hopSpaceId.value = 10
      await sleep(550)
      hopSpaceId.value = null
      await sleep(280)
      landPulseId.value = null
      movingPlayerId.value = null
      return { passedGo: false }
    }

    if (!path.length) {
      movingPlayerId.value = null
      return { passedGo: false }
    }

    const passedGo = path.includes(0) && from !== 0
    const hopMs = path.length > 14 ? 120 : path.length > 9 ? 160 : 210
    for (const spaceId of path) {
      setDisplayPos(playerId, spaceId)
      hopSpaceId.value = spaceId
      landPulseId.value = spaceId
      playTokenHop()
      await sleep(hopMs)
    }
    hopSpaceId.value = null
    push({ kind: 'land', playerId, spaceId: to })
    landPulseId.value = to
    playLand()
    if (passedGo) {
      await announce('PASSED GO', { subtitle: 'Collect $200', tone: 'gain', ms: 1100 })
    } else {
      await sleep(380)
    }
    landPulseId.value = null
    movingPlayerId.value = null
    await sleep(120)
    return { passedGo }
  }

  function snapshotPlayers(state: MonopolyGameState) {
    const map: Record<
      string,
      { cash: number; position: number; in_jail: boolean; bankrupt: boolean }
    > = {}
    for (const [id, p] of Object.entries(state.players)) {
      map[id] = {
        cash: p.cash,
        position: p.position,
        in_jail: p.in_jail,
        bankrupt: p.bankrupt,
      }
    }
    return map
  }

  function snapshotProps(state: MonopolyGameState) {
    const map: Record<string, { owner_id: string | null; houses: number; mortgaged: boolean }> = {}
    for (const [id, p] of Object.entries(state.properties)) {
      map[id] = { owner_id: p.owner_id, houses: p.houses, mortgaged: p.mortgaged }
    }
    return map
  }

  let prevPlayers = snapshotPlayers(gameState.value)
  let prevProps = snapshotProps(gameState.value)
  let prevDice = gameState.value.last_dice
    ? ([...gameState.value.last_dice] as [number, number])
    : null
  let prevCardId = gameState.value.last_card?.id ?? null
  let prevAuctionBid = gameState.value.auction?.high_bid ?? null
  let prevPhase = gameState.value.phase
  let primed = false

  initPositions(gameState.value)

  watch(
    gameState,
    (state) => {
      if (!primed) {
        prevPlayers = snapshotPlayers(state)
        prevProps = snapshotProps(state)
        prevDice = state.last_dice ? ([...state.last_dice] as [number, number]) : null
        prevCardId = state.last_card?.id ?? null
        prevAuctionBid = state.auction?.high_bid ?? null
        prevPhase = state.phase
        initPositions(state)
        primed = true
        return
      }

      const nextPlayers = snapshotPlayers(state)
      const nextProps = snapshotProps(state)
      const capturedPrevPlayers = { ...prevPlayers }
      const capturedPrevDice = prevDice ? ([...prevDice] as [number, number]) : null
      const capturedPrevCardId = prevCardId
      const capturedPrevAuctionBid = prevAuctionBid
      const capturedPrevPhase = prevPhase
      const capturedPrevProps = { ...prevProps }

      prevPlayers = nextPlayers
      prevProps = nextProps
      prevDice = state.last_dice ? ([...state.last_dice] as [number, number]) : null
      prevCardId = state.last_card?.id ?? null
      prevAuctionBid = state.auction?.high_bid ?? null
      prevPhase = state.phase

      void enqueue(async () => {
        const MOVE_CARD_EFFECTS = new Set([
          'advance',
          'go_to_jail',
          'move_relative',
          'nearest_utility',
          'nearest_railroad',
        ])

        async function revealCardIfNew() {
          const card = state.last_card
          if (!card || card.id === capturedPrevCardId) return
          const cardKind = card.id.startsWith('chance') ? 'chance' : 'community_chest'
          const event = push({ kind: 'card', text: card.text, cardKind })
          cardFlipped.value = false
          cardLeaving.value = false
          await announce(cardKind === 'chance' ? 'CHANCE!' : 'COMMUNITY CHEST', {
            tone: 'card',
            ms: 900,
          })
          cardOverlay.value = event
          playCardDraw(cardKind === 'chance')
          await sleep(480)
          if (cardOverlay.value?.id === event.id) {
            cardFlipped.value = true
            playCardFlip()
            await sleep(2400)
          }
          if (cardOverlay.value?.id === event.id) {
            cardLeaving.value = true
            await sleep(320)
          }
          if (cardOverlay.value?.id === event.id) {
            cardOverlay.value = null
            cardFlipped.value = false
            cardLeaving.value = false
          }
          await sleep(120)
        }

        const dice = state.last_dice
        if (
          dice &&
          (!capturedPrevDice ||
            capturedPrevDice[0] !== dice[0] ||
            capturedPrevDice[1] !== dice[1])
        ) {
          await animateDice([dice[0], dice[1]])
        }

        const playerIds = Object.keys(nextPlayers)
        const card = state.last_card
        const cardCausesMove =
          !!card &&
          card.id !== capturedPrevCardId &&
          MOVE_CARD_EFFECTS.has(card.effect)

        for (const id of playerIds) {
          const before = capturedPrevPlayers[id]
          const after = nextPlayers[id]
          if (!after || !before) continue
          if (before.bankrupt || !after.bankrupt) continue
          const player = state.players[id]
          push({ kind: 'bankrupt', playerId: id, text: `${player.nickname} went bankrupt` })
          playBankrupt()
          await announce('BANKRUPT!', { subtitle: player.nickname, tone: 'bankrupt', ms: 2000 })
          setDisplayPos(id, after.position)
        }

        // Advance / jail cards: reveal before the token moves
        if (cardCausesMove) {
          await revealCardIfNew()
        }

        const passedGoPlayerIds = new Set<string>()
        for (const id of playerIds) {
          const before = capturedPrevPlayers[id]
          const after = nextPlayers[id]
          if (!after || !before) continue
          const player = state.players[id]

          if (before.position !== after.position) {
            const wentToJail = !before.in_jail && after.in_jail
            const result = await animateMove(
              id,
              before.position,
              after.position,
              wentToJail,
              player.nickname,
            )
            if (result.passedGo) passedGoPlayerIds.add(id)
          } else if (!before.in_jail && after.in_jail) {
            playJail()
            await announce('GO TO JAIL', { subtitle: player.nickname, tone: 'jail', ms: 1600 })
            landPulseId.value = 10
            await sleep(500)
            landPulseId.value = null
          }
        }

        for (const [id, p] of Object.entries(nextPlayers)) {
          if (displayPositions.value[id] !== p.position && movingPlayerId.value !== id) {
            setDisplayPos(id, p.position)
          }
        }

        // Cash: peel already-announced GO $200, then pair transfers into one “A → B” banner
        const cashDeltas: { id: string; delta: number; nick: string; color: string }[] = []
        for (const id of playerIds) {
          const before = capturedPrevPlayers[id]
          const after = nextPlayers[id]
          if (!after || !before || before.cash === after.cash) continue
          const player = state.players[id]
          let delta = after.cash - before.cash
          if (passedGoPlayerIds.has(id)) {
            delta -= 200
          }
          if (delta === 0) continue
          cashDeltas.push({
            id,
            delta,
            nick: player.nickname,
            color: player.token_color,
          })
        }

        const used = new Set<string>()
        for (let i = 0; i < cashDeltas.length; i += 1) {
          const a = cashDeltas[i]!
          if (used.has(a.id)) continue
          let paired = false
          for (let j = i + 1; j < cashDeltas.length; j += 1) {
            const b = cashDeltas[j]!
            if (used.has(b.id)) continue
            if (a.delta === -b.delta && a.delta !== 0) {
              const amount = Math.abs(a.delta)
              const payer = a.delta < 0 ? a : b
              const payee = a.delta < 0 ? b : a
              for (const side of [a, b]) {
                const event = push({
                  kind: 'cash',
                  playerId: side.id,
                  amount: side.delta,
                  color: side.color,
                })
                addCashFx(event)
              }
              playCashLoss()
              playCashGain()
              if (amount >= 10) {
                await announce(`$${amount}`, {
                  subtitle: `${payer.nick} → ${payee.nick}`,
                  tone: 'rent',
                  ms: 1200,
                })
              } else {
                await sleep(280)
              }
              used.add(a.id)
              used.add(b.id)
              paired = true
              break
            }
          }
          if (paired) continue

          used.add(a.id)
          const event = push({
            kind: 'cash',
            playerId: a.id,
            amount: a.delta,
            color: a.color,
          })
          addCashFx(event)
          if (a.delta > 0) playCashGain()
          else playCashLoss()

          if (Math.abs(a.delta) >= 25) {
            await announce(a.delta > 0 ? `+$${a.delta}` : `-$${Math.abs(a.delta)}`, {
              subtitle: a.nick,
              tone: a.delta > 0 ? 'gain' : 'rent',
              ms: 1000,
            })
          } else {
            await sleep(220)
          }
        }

        for (const sid of Object.keys(nextProps)) {
          const before = capturedPrevProps[sid]
          const after = nextProps[sid]
          if (!before || !after) continue
          const spaceId = Number(sid)
          if (before.owner_id !== after.owner_id && after.owner_id) {
            buyFlashId.value = spaceId
            push({ kind: 'buy', spaceId, playerId: after.owner_id })
            const name = state.spaces.find((s) => s.id === spaceId)?.name ?? 'Property'
            const nick = state.players[after.owner_id]?.nickname ?? 'Player'
            playBuy()
            await announce('SOLD!', { subtitle: `${nick} · ${name}`, tone: 'buy', ms: 1400 })
            buyFlashId.value = null
          }
          if (after.houses > before.houses) {
            push({ kind: 'build', spaceId, playerId: after.owner_id ?? undefined })
            buyFlashId.value = spaceId
            playBuild()
            const name = state.spaces.find((s) => s.id === spaceId)?.name ?? 'Property'
            const built = after.houses === 5 ? 'HOTEL' : `HOUSE ×${after.houses}`
            await announce(built, { subtitle: name, tone: 'build', ms: 1100 })
            buyFlashId.value = null
          } else if (after.houses < before.houses) {
            buyFlashId.value = spaceId
            playCashGain()
            const name = state.spaces.find((s) => s.id === spaceId)?.name ?? 'Property'
            await announce('SOLD BUILDING', { subtitle: name, tone: 'gain', ms: 900 })
            buyFlashId.value = null
          }
          if (!before.mortgaged && after.mortgaged) {
            buyFlashId.value = spaceId
            playCashGain()
            const name = state.spaces.find((s) => s.id === spaceId)?.name ?? 'Property'
            await announce('MORTGAGED', { subtitle: name, tone: 'default', ms: 900 })
            buyFlashId.value = null
          } else if (before.mortgaged && !after.mortgaged) {
            buyFlashId.value = spaceId
            playCashLoss()
            const name = state.spaces.find((s) => s.id === spaceId)?.name ?? 'Property'
            await announce('UNMORTGAGED', { subtitle: name, tone: 'buy', ms: 900 })
            buyFlashId.value = null
          }
        }

        // Landing-triggered Chance/Chest (cash, repairs, etc.): reveal after the move
        if (!cardCausesMove) {
          await revealCardIfNew()
        }

        const bid = state.auction?.high_bid ?? null
        if (capturedPrevAuctionBid === null && state.auction) {
          playAuctionStart()
          const name =
            state.spaces.find((s) => s.id === state.auction!.space_id)?.name ?? 'Property'
          await announce('AUCTION!', { subtitle: name, tone: 'auction', ms: 1200 })
        }
        if (
          state.auction &&
          bid != null &&
          capturedPrevAuctionBid != null &&
          bid > capturedPrevAuctionBid
        ) {
          push({
            kind: 'auction',
            spaceId: state.auction.space_id,
            amount: bid,
            playerId: state.auction.high_bidder_id ?? undefined,
          })
          playAuctionBid()
          const bidder = state.auction.high_bidder_id
            ? state.players[state.auction.high_bidder_id]?.nickname
            : null
          await announce(`$${bid}`, {
            subtitle: bidder ? `${bidder} bids` : 'New high bid',
            tone: 'auction',
            ms: 750,
          })
        }

        if (state.phase !== capturedPrevPhase) {
          // Buy/auction & your-turn are clear from the action bar / status — no banner
          if (state.phase === 'awaiting_payment') {
            const debt = state.debt
            await announce('DEBT DUE', {
              subtitle: debt ? `$${debt.amount}` : 'Raise cash',
              tone: 'rent',
              ms: 1400,
            })
          }
          if (state.phase === 'trade_pending') {
            await announce('TRADE OFFER', { tone: 'default', ms: 1100 })
          }
          if (state.phase === 'awaiting_roll') {
            const actorId = state.current_actor_id
            const actor = actorId ? state.players[actorId] : null
            if (actor && !actor.is_ai && !actor.bankrupt) {
              playYourTurn()
            }
          }
          if (state.phase === 'finished' && state.winner) {
            const nick = state.players[state.winner]?.nickname ?? 'Winner'
            playWin()
            await announce(`${nick} WINS!`, { subtitle: 'Game over', tone: 'win', ms: 3600 })
          }
        }
      })
    },
    { deep: true },
  )

  onUnmounted(() => {
    for (const id of timers) {
      window.clearTimeout(id)
      window.clearInterval(id)
    }
    taskQueue.length = 0
  })

  return {
    movingPlayerId,
    landPulseId,
    buyFlashId,
    hopSpaceId,
    diceRolling,
    displayDice,
    cardOverlay,
    cardFlipped,
    cardLeaving,
    banner,
    cashFxByPlayer,
    displayPositions,
    boardBusy,
  }
}
