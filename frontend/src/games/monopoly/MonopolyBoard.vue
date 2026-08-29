<script setup lang="ts">
import { computed, ref } from 'vue'
import type { MonopolyGameState, MonopolyPlayerState, Room } from '@/types'
import {
  COLOR_HEX,
  COLOR_LABEL,
  SPACE_TINY,
  spaceGridPos,
  spaceSide,
  tokenGlyph,
} from './boardData'

const props = defineProps<{
  gameState: MonopolyGameState
  room: Room
  playerId: string
}>()

const emit = defineEmits<{
  action: [data: Record<string, unknown>]
}>()

const showManage = ref(false)
const showTrade = ref(false)
const tradeToId = ref('')
const tradeOfferCash = ref(0)
const tradeRequestCash = ref(0)
const tradeOfferProps = ref<number[]>([])
const tradeRequestProps = ref<number[]>([])
const bidAmount = ref(10)
const selectedSpaceId = ref<number | null>(null)

const gs = computed(() => props.gameState)
const me = computed(() => gs.value.players[props.playerId] ?? null)
const isActor = computed(() => gs.value.current_actor_id === props.playerId)
const isTurnPlayer = computed(() => {
  const order = gs.value.seat_order
  const idx = gs.value.current_player_index
  return order[idx] === props.playerId
})
const phase = computed(() => gs.value.phase)
const isFinished = computed(() => phase.value === 'finished' || Boolean(gs.value.winner))

const playersList = computed(() =>
  gs.value.seat_order.map((id) => gs.value.players[id]).filter(Boolean) as MonopolyPlayerState[],
)

const playerIndex = computed(() => {
  const map: Record<string, number> = {}
  gs.value.seat_order.forEach((id, i) => {
    map[id] = i
  })
  return map
})

const actorName = computed(() => {
  const id = gs.value.current_actor_id
  return id ? (gs.value.players[id]?.nickname ?? '…') : '…'
})

const myProps = computed(() =>
  Object.entries(gs.value.properties)
    .filter(([, p]) => p.owner_id === props.playerId)
    .map(([id, p]) => ({
      id: Number(id),
      ...p,
      space: gs.value.spaces.find((s) => s.id === Number(id)),
    }))
    .sort((a, b) => a.id - b.id),
)

const landSpace = computed(() => {
  const pos = me.value?.position
  if (pos == null) return null
  return gs.value.spaces.find((s) => s.id === pos) ?? null
})

const landPrice = computed(() => landSpace.value?.price ?? null)

const tokensBySpace = computed(() => {
  const map: Record<number, MonopolyPlayerState[]> = {}
  for (const p of playersList.value) {
    if (p.bankrupt) continue
    if (!map[p.position]) map[p.position] = []
    map[p.position].push(p)
  }
  return map
})

const statusText = computed(() => {
  if (isFinished.value) {
    const w = gs.value.winner ? gs.value.players[gs.value.winner]?.nickname : null
    return w ? `${w} wins the game!` : 'Game over'
  }
  const p = phase.value
  if (p === 'awaiting_roll') return isActor.value ? 'Your turn — roll the dice' : `${actorName.value} to roll`
  if (p === 'awaiting_buy') {
    const name = landSpace.value?.name ?? 'property'
    return isActor.value ? `Buy ${name}?` : `${actorName.value} deciding`
  }
  if (p === 'auction') return isActor.value ? 'Your bid' : `Auction — ${actorName.value}`
  if (p === 'awaiting_payment') return isActor.value ? 'Raise cash or go bankrupt' : `${actorName.value} settling debt`
  if (p === 'trade_pending') return isActor.value ? 'Respond to trade' : 'Trade pending'
  if (p === 'awaiting_end') return isActor.value ? 'Build, trade, or end turn' : `${actorName.value}'s turn`
  return `${actorName.value}'s turn`
})

const selectedDeed = computed(() => {
  const id = selectedSpaceId.value
  if (id == null) return null
  const space = gs.value.spaces.find((s) => s.id === id)
  const prop = gs.value.properties[String(id)]
  if (!space) return null
  return { space, prop }
})

function send(action: Record<string, unknown>) {
  emit('action', action)
}

function ownerColor(spaceId: number): string | null {
  const owner = gs.value.properties[String(spaceId)]?.owner_id
  if (!owner) return null
  return gs.value.players[owner]?.token_color ?? '#888'
}

function houseCount(spaceId: number): number {
  return gs.value.properties[String(spaceId)]?.houses ?? 0
}

function isMortgaged(spaceId: number): boolean {
  return Boolean(gs.value.properties[String(spaceId)]?.mortgaged)
}

function kindIcon(kind: string, id: number): string {
  if (kind === 'railroad') return '🚂'
  if (kind === 'utility') return id === 12 ? '💡' : '💧'
  if (kind === 'chance') return '?'
  if (kind === 'community_chest') return '📦'
  if (kind === 'tax') return '💰'
  if (kind === 'go') return '→'
  if (kind === 'jail') return '🔒'
  if (kind === 'free_parking') return '🅿'
  if (kind === 'go_to_jail') return '👮'
  return ''
}

function toggleOfferProp(id: number) {
  const set = new Set(tradeOfferProps.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  tradeOfferProps.value = [...set]
}

function toggleRequestProp(id: number) {
  const set = new Set(tradeRequestProps.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  tradeRequestProps.value = [...set]
}

function proposeTrade() {
  if (!tradeToId.value) return
  send({
    type: 'propose_trade',
    to_id: tradeToId.value,
    offer_cash: tradeOfferCash.value,
    request_cash: tradeRequestCash.value,
    offer_props: tradeOfferProps.value,
    request_props: tradeRequestProps.value,
  })
  showTrade.value = false
}

const partnerProps = computed(() => {
  if (!tradeToId.value) return []
  return Object.entries(gs.value.properties)
    .filter(([, p]) => p.owner_id === tradeToId.value)
    .map(([id, p]) => ({
      id: Number(id),
      ...p,
      space: gs.value.spaces.find((s) => s.id === Number(id)),
    }))
})

const logLines = computed(() => (gs.value.log || []).slice(-10).reverse())

const pendingTrade = computed(() => gs.value.pending_trade)

function selectSpace(id: number) {
  selectedSpaceId.value = selectedSpaceId.value === id ? null : id
}
</script>

<template>
  <div class="mono-play">
    <aside class="sidebar">
      <div class="status-card">
        <p class="status-label">Status</p>
        <h2 class="status">{{ statusText }}</h2>
        <div v-if="gs.last_dice" class="dice-row" aria-label="Last dice roll">
          <span class="die" :data-face="gs.last_dice[0]">{{ gs.last_dice[0] }}</span>
          <span class="die-plus">+</span>
          <span class="die" :data-face="gs.last_dice[1]">{{ gs.last_dice[1] }}</span>
          <span class="die-total">= {{ gs.last_dice[0] + gs.last_dice[1] }}</span>
        </div>
      </div>

      <div v-if="gs.last_card" class="drawn-card" :class="gs.last_card.id.startsWith('chance') ? 'chance' : 'chest'">
        <span class="drawn-label">{{ gs.last_card.id.startsWith('chance') ? 'Chance' : 'Community Chest' }}</span>
        <p>{{ gs.last_card.text }}</p>
      </div>

      <div v-if="gs.auction" class="banner auction">
        <strong>Auction</strong>
        <span>{{ gs.spaces.find((s) => s.id === gs.auction!.space_id)?.name }}</span>
        <span class="banner-cash">High bid ${{ gs.auction.high_bid }}</span>
      </div>
      <div v-if="gs.debt" class="banner debt">
        <strong>Debt due</strong>
        <span>${{ gs.debt.amount }} — {{ gs.debt.reason }}</span>
      </div>
      <div v-if="pendingTrade" class="banner trade">
        <strong>Trade offer</strong>
        <span>
          {{ gs.players[pendingTrade.from_id]?.nickname }} →
          {{ gs.players[pendingTrade.to_id]?.nickname }}
        </span>
      </div>

      <section class="players-section">
        <h3 class="side-title">Players</h3>
        <ul class="players">
          <li
            v-for="p in playersList"
            :key="p.id"
            :class="{
              active: p.id === gs.current_actor_id,
              me: p.id === playerId,
              out: p.bankrupt,
            }"
          >
            <span class="tok" :style="{ background: p.token_color }" :title="p.nickname">
              {{ tokenGlyph(playerIndex[p.id] ?? 0) }}
            </span>
            <div class="p-info">
              <div class="p-name">
                <strong>{{ p.nickname }}</strong>
                <span v-if="p.id === playerId" class="you">you</span>
                <span v-if="p.in_jail" class="jail">Jail</span>
              </div>
              <span class="cash">${{ p.cash.toLocaleString() }}</span>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="myProps.length" class="deeds-section">
        <h3 class="side-title">Your deeds</h3>
        <div class="deed-strip">
          <button
            v-for="prop in myProps"
            :key="prop.id"
            type="button"
            class="mini-deed"
            :class="{ mortgaged: prop.mortgaged }"
            :style="{ '--deed': prop.space?.color ? COLOR_HEX[prop.space.color] : '#555' }"
            :title="prop.space?.name"
            @click="selectSpace(prop.id)"
          >
            <span class="mini-bar" />
            <span class="mini-name">{{ prop.space?.name?.split(' ')[0] }}</span>
            <span v-if="prop.houses === 5" class="mini-hotel">H</span>
            <span v-else-if="prop.houses" class="mini-houses">{{ prop.houses }}</span>
          </button>
        </div>
      </section>

      <div v-if="selectedDeed" class="deed-card">
        <div
          class="deed-header"
          :style="{
            background: selectedDeed.space.color
              ? COLOR_HEX[selectedDeed.space.color]
              : selectedDeed.space.kind === 'railroad'
                ? '#1a1a1a'
                : '#6b8e23',
          }"
        >
          <span v-if="selectedDeed.space.color" class="deed-group">
            {{ COLOR_LABEL[selectedDeed.space.color] }}
          </span>
          <strong>{{ selectedDeed.space.name }}</strong>
        </div>
        <div class="deed-body">
          <p v-if="selectedDeed.space.price">Price ${{ selectedDeed.space.price }}</p>
          <p v-if="selectedDeed.prop?.owner_id">
            Owner: {{ gs.players[selectedDeed.prop.owner_id]?.nickname }}
          </p>
          <p v-else-if="selectedDeed.space.price">Unowned</p>
          <p v-if="selectedDeed.prop?.mortgaged" class="mort-tag">Mortgaged</p>
          <p v-if="(selectedDeed.prop?.houses ?? 0) > 0">
            {{ selectedDeed.prop!.houses === 5 ? 'Hotel' : `${selectedDeed.prop!.houses} house(s)` }}
          </p>
        </div>
      </div>

      <div class="log">
        <h3 class="side-title">Log</h3>
        <div v-for="(line, i) in logLines" :key="i" class="log-line">{{ line.message }}</div>
      </div>
    </aside>

    <div class="main">
      <div class="board-wrap">
        <div class="board-frame">
          <div class="board">
            <div class="center">
              <div class="center-texture" />
              <div class="brand-wrap">
                <div class="brand">MONOPOLY</div>
                <div class="brand-sub">PROPERTY TRADING GAME</div>
              </div>
              <div class="center-decks">
                <div class="deck chest-deck">
                  <span>COMMUNITY</span>
                  <span>CHEST</span>
                </div>
                <div class="deck chance-deck">
                  <span>CHANCE</span>
                </div>
              </div>
            </div>

            <button
              v-for="space in gs.spaces"
              :key="space.id"
              type="button"
              class="cell"
              :class="[
                `side-${spaceSide(space.id)}`,
                `kind-${space.kind}`,
                {
                  corner: [0, 10, 20, 30].includes(space.id),
                  mortgaged: isMortgaged(space.id),
                  selected: selectedSpaceId === space.id,
                },
              ]"
              :style="{
                gridRow: spaceGridPos(space.id).row,
                gridColumn: spaceGridPos(space.id).col,
                '--stripe': space.color ? COLOR_HEX[space.color] : 'transparent',
                '--owner': ownerColor(space.id) || 'transparent',
              }"
              :title="space.name"
              @click="selectSpace(space.id)"
            >
              <div v-if="space.color" class="stripe" />
              <div class="cell-inner">
                <div v-if="kindIcon(space.kind, space.id)" class="kind-icon">
                  {{ kindIcon(space.kind, space.id) }}
                </div>
                <div class="name">{{ SPACE_TINY[space.id] ?? space.name }}</div>
                <div v-if="houseCount(space.id) > 0" class="buildings">
                  <template v-if="houseCount(space.id) === 5">
                    <span class="hotel" />
                  </template>
                  <template v-else>
                    <span v-for="n in houseCount(space.id)" :key="n" class="house" />
                  </template>
                </div>
                <div v-if="space.price && ![0, 10, 20, 30].includes(space.id)" class="price">
                  ${{ space.price }}
                </div>
                <div v-if="isMortgaged(space.id)" class="mort-stamp">MORTGAGED</div>
              </div>
              <div class="tokens">
                <span
                  v-for="t in tokensBySpace[space.id] || []"
                  :key="t.id"
                  class="token"
                  :style="{ background: t.token_color }"
                  :title="t.nickname"
                >
                  {{ tokenGlyph(playerIndex[t.id] ?? 0) }}
                </span>
              </div>
              <div v-if="ownerColor(space.id)" class="owner-pip" :style="{ background: ownerColor(space.id)! }" />
            </button>
          </div>
        </div>
      </div>

      <div v-if="!isFinished" class="actions">
        <template v-if="phase === 'awaiting_roll' && isTurnPlayer">
          <template v-if="me?.in_jail">
            <button type="button" class="btn-primary" @click="send({ type: 'roll_jail' })">
              Roll for doubles
            </button>
            <button
              v-if="(me?.cash ?? 0) >= 50"
              type="button"
              class="btn-secondary"
              @click="send({ type: 'pay_jail' })"
            >
              Pay $50
            </button>
            <button
              v-if="(me?.get_out_cards ?? 0) > 0"
              type="button"
              class="btn-secondary"
              @click="send({ type: 'use_jail_card' })"
            >
              Get Out of Jail Free
            </button>
          </template>
          <button v-else type="button" class="btn-primary btn-roll" @click="send({ type: 'roll' })">
            🎲 Roll dice
          </button>
        </template>

        <template v-if="phase === 'awaiting_buy' && isActor">
          <button
            type="button"
            class="btn-primary"
            :disabled="landPrice != null && (me?.cash ?? 0) < landPrice"
            @click="send({ type: 'buy' })"
          >
            Buy{{ landPrice != null ? ` for $${landPrice}` : '' }}
          </button>
          <button type="button" class="btn-secondary" @click="send({ type: 'decline' })">
            Auction instead
          </button>
        </template>

        <template v-if="phase === 'auction' && isActor">
          <label class="bid-label">
            Bid
            <input v-model.number="bidAmount" type="number" min="1" step="10" />
          </label>
          <button type="button" class="btn-primary" @click="send({ type: 'bid', amount: bidAmount })">
            Bid ${{ bidAmount }}
          </button>
          <button type="button" class="btn-secondary" @click="send({ type: 'pass_auction' })">Pass</button>
        </template>

        <template v-if="phase === 'awaiting_payment' && isActor">
          <button
            type="button"
            class="btn-primary"
            :disabled="(me?.cash ?? 0) < (gs.debt?.amount ?? 0)"
            @click="send({ type: 'pay_debt' })"
          >
            Pay ${{ gs.debt?.amount ?? 0 }}
          </button>
          <button type="button" class="btn-secondary" @click="showManage = true">Manage assets</button>
          <button type="button" class="btn-danger" @click="send({ type: 'declare_bankruptcy' })">
            Bankruptcy
          </button>
        </template>

        <template v-if="phase === 'trade_pending' && isActor">
          <button type="button" class="btn-primary" @click="send({ type: 'accept_trade' })">Accept trade</button>
          <button type="button" class="btn-secondary" @click="send({ type: 'reject_trade' })">Reject</button>
        </template>

        <template v-if="phase === 'awaiting_end' && isTurnPlayer">
          <button type="button" class="btn-secondary" @click="showManage = true">Build / Mortgage</button>
          <button type="button" class="btn-secondary" @click="showTrade = true">Trade</button>
          <button
            type="button"
            class="btn-primary"
            :disabled="gs.can_roll_again"
            @click="send({ type: 'end_turn' })"
          >
            End turn
          </button>
        </template>

        <button
          v-if="me && !me.bankrupt && phase !== 'finished'"
          type="button"
          class="btn-danger resign"
          @click="send({ type: 'resign' })"
        >
          Resign
        </button>
      </div>
    </div>

    <div v-if="showManage" class="modal" @click.self="showManage = false">
      <div class="modal-card">
        <h3>Manage properties</h3>
        <ul class="prop-list">
          <li v-for="prop in myProps" :key="prop.id">
            <div
              class="prop-swatch"
              :style="{ background: prop.space?.color ? COLOR_HEX[prop.space.color] : '#444' }"
            />
            <div class="prop-meta">
              <strong>{{ prop.space?.name ?? prop.id }}</strong>
              <span v-if="prop.mortgaged" class="muted">Mortgaged</span>
              <span v-else-if="prop.houses">{{ prop.houses === 5 ? 'Hotel' : `${prop.houses} houses` }}</span>
            </div>
            <div class="prop-actions">
              <button type="button" class="btn-mini" @click="send({ type: 'build', space_id: prop.id })">
                Build
              </button>
              <button type="button" class="btn-mini" @click="send({ type: 'sell_building', space_id: prop.id })">
                Sell
              </button>
              <button
                v-if="!prop.mortgaged"
                type="button"
                class="btn-mini"
                @click="send({ type: 'mortgage', space_id: prop.id })"
              >
                Mortgage
              </button>
              <button
                v-else
                type="button"
                class="btn-mini"
                @click="send({ type: 'unmortgage', space_id: prop.id })"
              >
                Unmortgage
              </button>
            </div>
          </li>
          <li v-if="!myProps.length" class="empty">You don’t own any properties yet.</li>
        </ul>
        <button type="button" class="btn-secondary" @click="showManage = false">Close</button>
      </div>
    </div>

    <div v-if="showTrade" class="modal" @click.self="showTrade = false">
      <div class="modal-card">
        <h3>Propose trade</h3>
        <label class="field">
          Partner
          <select v-model="tradeToId">
            <option value="" disabled>Select…</option>
            <option
              v-for="p in playersList.filter((x) => x.id !== playerId && !x.bankrupt)"
              :key="p.id"
              :value="p.id"
            >
              {{ p.nickname }}
            </option>
          </select>
        </label>
        <div class="cash-row">
          <label class="field">Offer cash <input v-model.number="tradeOfferCash" type="number" min="0" /></label>
          <label class="field">
            Request cash <input v-model.number="tradeRequestCash" type="number" min="0" />
          </label>
        </div>
        <div class="trade-cols">
          <div>
            <h4>You offer</h4>
            <label v-for="prop in myProps" :key="'o' + prop.id" class="check">
              <input
                type="checkbox"
                :checked="tradeOfferProps.includes(prop.id)"
                @change="toggleOfferProp(prop.id)"
              />
              {{ prop.space?.name }}
            </label>
          </div>
          <div>
            <h4>You request</h4>
            <label v-for="prop in partnerProps" :key="'r' + prop.id" class="check">
              <input
                type="checkbox"
                :checked="tradeRequestProps.includes(prop.id)"
                @change="toggleRequestProp(prop.id)"
              />
              {{ prop.space?.name }}
            </label>
            <p v-if="tradeToId && !partnerProps.length" class="muted">No properties</p>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn-primary" @click="proposeTrade">Send proposal</button>
          <button type="button" class="btn-secondary" @click="showTrade = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@500;600;700&display=swap');

.mono-play {
  --felt: #0f5c3a;
  --felt-deep: #0a3d28;
  --cream: #f3e6c8;
  --ink: #1c1812;
  --wood: #5c3a1e;
  --wood-light: #8b5a2b;
  --accent: #c41e3a;
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 0.75rem;
  height: min(100%, calc(100vh - 4.5rem));
  padding: 0.5rem;
  color: #f2ebe0;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(196, 30, 58, 0.08), transparent 50%),
    linear-gradient(160deg, #14181f 0%, #1a221c 100%);
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  background: linear-gradient(180deg, #1a221c 0%, #12161a 100%);
  border: 1px solid rgba(243, 230, 200, 0.12);
  border-radius: 14px;
  padding: 0.85rem;
  overflow: auto;
  min-height: 0;
}

.status-card {
  background: rgba(15, 92, 58, 0.25);
  border: 1px solid rgba(243, 230, 200, 0.15);
  border-radius: 10px;
  padding: 0.7rem 0.8rem;
}
.status-label {
  margin: 0;
  font-size: 0.65rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9bb89a;
}
.status {
  margin: 0.2rem 0 0.5rem;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 1.05rem;
  color: var(--cream);
  line-height: 1.3;
}
.dice-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.die {
  width: 1.7rem;
  height: 1.7rem;
  display: grid;
  place-items: center;
  background: #fff;
  color: #111;
  border-radius: 5px;
  font-weight: 700;
  box-shadow: 1px 2px 0 #0005;
}
.die-plus,
.die-total {
  font-size: 0.85rem;
  color: #c8d5c0;
}

.drawn-card {
  border-radius: 8px;
  padding: 0.55rem 0.7rem;
  font-size: 0.8rem;
  line-height: 1.35;
}
.drawn-card.chance {
  background: #f7941d;
  color: #1a1208;
}
.drawn-card.chest {
  background: #5b8def;
  color: #0c1528;
}
.drawn-label {
  display: block;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.2rem;
}
.drawn-card p {
  margin: 0;
}

.banner {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  font-size: 0.8rem;
}
.banner.auction {
  background: rgba(247, 148, 29, 0.2);
  border: 1px solid rgba(247, 148, 29, 0.4);
}
.banner.debt {
  background: rgba(196, 30, 58, 0.2);
  border: 1px solid rgba(196, 30, 58, 0.45);
}
.banner.trade {
  background: rgba(91, 141, 239, 0.2);
  border: 1px solid rgba(91, 141, 239, 0.4);
}
.banner-cash {
  font-weight: 700;
  color: #f0c36a;
}

.side-title {
  margin: 0 0 0.4rem;
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #9bb89a;
}
.players {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.players li {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  padding: 0.45rem 0.5rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}
.players li.active {
  background: rgba(15, 92, 58, 0.45);
  box-shadow: inset 0 0 0 1px rgba(243, 230, 200, 0.25);
}
.players li.me {
  outline: 1px solid rgba(243, 230, 200, 0.28);
}
.players li.out {
  opacity: 0.4;
}
.tok {
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 0.85rem;
  border: 2px solid #fff8;
  flex-shrink: 0;
  box-shadow: 0 1px 3px #0006;
}
.p-info {
  min-width: 0;
  flex: 1;
}
.p-name {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  font-size: 0.88rem;
}
.you {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #c4b08a;
}
.jail {
  font-size: 0.65rem;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  background: #c41e3a;
  color: #fff;
}
.cash {
  display: block;
  color: #7dce8a;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: 0.9rem;
}

.deed-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.mini-deed {
  width: 2.6rem;
  border: 1px solid #0005;
  border-radius: 3px;
  background: var(--cream);
  color: var(--ink);
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  font-size: 0.5rem;
  line-height: 1.1;
}
.mini-deed.mortgaged {
  opacity: 0.55;
  filter: grayscale(0.4);
}
.mini-bar {
  display: block;
  height: 0.35rem;
  background: var(--deed);
}
.mini-name {
  display: block;
  padding: 0.15rem;
  font-weight: 700;
  text-align: center;
}
.mini-houses,
.mini-hotel {
  display: block;
  text-align: center;
  font-weight: 700;
  color: #0f5c3a;
  padding-bottom: 0.1rem;
}
.mini-hotel {
  color: var(--accent);
}

.deed-card {
  background: var(--cream);
  color: var(--ink);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 14px #0005;
  font-size: 0.78rem;
}
.deed-header {
  padding: 0.45rem 0.55rem;
  text-align: center;
  color: #fff;
  text-shadow: 0 1px 1px #0005;
}
.deed-header strong {
  display: block;
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 0.85rem;
}
.deed-group {
  display: block;
  font-size: 0.58rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.9;
}
.deed-body {
  padding: 0.45rem 0.6rem 0.6rem;
}
.deed-body p {
  margin: 0.15rem 0;
}
.mort-tag {
  color: var(--accent);
  font-weight: 700;
}

.log {
  margin-top: auto;
  font-size: 0.72rem;
  color: #9a958c;
  max-height: 8.5rem;
  overflow: auto;
}
.log-line {
  padding: 0.2rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  gap: 0.55rem;
}

.board-wrap {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 0;
  overflow: auto;
  padding: 0.25rem;
}

.board-frame {
  padding: 10px;
  background: linear-gradient(145deg, var(--wood-light), var(--wood) 40%, #3d2412);
  border-radius: 8px;
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.board {
  --corner: min(9.2vh, 7.4vw, 72px);
  --edge: min(6.4vh, 5.1vw, 50px);
  display: grid;
  grid-template-columns: var(--corner) repeat(9, var(--edge)) var(--corner);
  grid-template-rows: var(--corner) repeat(9, var(--edge)) var(--corner);
  gap: 0;
  background: #2c2118;
  border: 2px solid #1a120c;
  width: calc(2 * var(--corner) + 9 * var(--edge));
  height: calc(2 * var(--corner) + 9 * var(--edge));
}

.center {
  grid-column: 2 / 11;
  grid-row: 2 / 11;
  position: relative;
  background: var(--felt);
  overflow: hidden;
  display: grid;
  place-items: center;
}
.center-texture {
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      -45deg,
      transparent,
      transparent 8px,
      rgba(0, 0, 0, 0.03) 8px,
      rgba(0, 0, 0, 0.03) 16px
    ),
    radial-gradient(circle at 50% 50%, rgba(255, 255, 255, 0.06), transparent 60%);
  pointer-events: none;
}
.brand-wrap {
  position: relative;
  z-index: 1;
  transform: rotate(-45deg);
  text-align: center;
}
.brand {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-weight: 700;
  font-size: clamp(1.6rem, 4.2vw, 3.2rem);
  letter-spacing: 0.08em;
  color: var(--accent);
  text-shadow:
    2px 2px 0 #fff8,
    -1px -1px 0 #0004;
  line-height: 1;
}
.brand-sub {
  margin-top: 0.35rem;
  font-size: clamp(0.45rem, 1vw, 0.7rem);
  letter-spacing: 0.28em;
  color: rgba(243, 230, 200, 0.75);
  font-weight: 600;
}
.center-decks {
  position: absolute;
  inset: 12%;
  z-index: 1;
  pointer-events: none;
}
.deck {
  position: absolute;
  width: 22%;
  aspect-ratio: 0.7;
  border: 2px solid rgba(243, 230, 200, 0.55);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: clamp(0.4rem, 0.85vw, 0.65rem);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-align: center;
  line-height: 1.2;
  box-shadow: 2px 3px 0 #0003;
}
.chest-deck {
  top: 8%;
  left: 8%;
  transform: rotate(45deg);
  background: #5b8def;
  color: #0c1528;
}
.chance-deck {
  bottom: 8%;
  right: 8%;
  transform: rotate(45deg);
  background: #f7941d;
  color: #1a1208;
}

.cell {
  position: relative;
  background: var(--cream);
  color: var(--ink);
  border: 1px solid #2c2118;
  padding: 0;
  margin: 0;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family: 'Source Sans 3', system-ui, sans-serif;
  box-shadow: inset 0 0 0 2.5px var(--owner);
  transition: filter 0.12s ease;
}
.cell:hover,
.cell.selected {
  filter: brightness(1.06);
  z-index: 2;
}
.cell.mortgaged {
  background: #ddd3bc;
}
.cell.corner {
  font-weight: 700;
}
.cell.kind-go {
  background: #d6f0d6;
}
.cell.kind-jail {
  background: #f0e0c8;
}
.cell.kind-free_parking {
  background: #e8f0ff;
}
.cell.kind-go_to_jail {
  background: #f5d6d6;
}
.cell.kind-chance {
  background: #ffe2b8;
}
.cell.kind-community_chest {
  background: #cfe0ff;
}
.cell.kind-tax {
  background: #efe8d8;
}
.cell.kind-railroad {
  background: #ebe6dc;
}
.cell.kind-utility {
  background: #e8efe4;
}

.stripe {
  background: var(--stripe);
  flex-shrink: 0;
  border-bottom: 1px solid #0003;
}
.side-bottom .stripe,
.side-top .stripe {
  height: 22%;
  width: 100%;
}
.side-top {
  flex-direction: column-reverse;
}
.side-top .stripe {
  border-bottom: none;
  border-top: 1px solid #0003;
}
.side-left,
.side-right {
  flex-direction: row;
}
.side-left .stripe,
.side-right .stripe {
  width: 22%;
  height: 100%;
  border-bottom: none;
}
.side-left {
  flex-direction: row-reverse;
}
.side-left .stripe {
  border-left: 1px solid #0003;
}
.side-right .stripe {
  border-right: 1px solid #0003;
}

.cell-inner {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1px 2px;
  gap: 1px;
  position: relative;
}
.side-left .cell-inner,
.side-right .cell-inner {
  writing-mode: vertical-rl;
  text-orientation: mixed;
}
.side-left .cell-inner {
  transform: rotate(180deg);
}
.kind-icon {
  font-size: clamp(0.55rem, 1.1vw, 0.9rem);
  line-height: 1;
}
.name {
  font-size: clamp(0.32rem, 0.72vw, 0.55rem);
  font-weight: 700;
  line-height: 1.05;
  text-align: center;
  white-space: pre-line;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}
.corner .name {
  font-size: clamp(0.45rem, 0.95vw, 0.72rem);
}
.price {
  font-size: clamp(0.3rem, 0.65vw, 0.48rem);
  font-weight: 600;
  opacity: 0.85;
}
.buildings {
  display: flex;
  gap: 1px;
  flex-wrap: wrap;
  justify-content: center;
}
.house {
  width: 6px;
  height: 5px;
  background: #1fb25a;
  border: 0.5px solid #0a5c2e;
  border-radius: 1px 1px 0 0;
  box-shadow: inset 0 1px 0 #fff4;
}
.hotel {
  width: 10px;
  height: 7px;
  background: var(--accent);
  border: 0.5px solid #7a1020;
  border-radius: 1px;
}
.mort-stamp {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: clamp(0.28rem, 0.55vw, 0.42rem);
  font-weight: 800;
  color: var(--accent);
  letter-spacing: 0.04em;
  transform: rotate(-25deg);
  opacity: 0.75;
  pointer-events: none;
}
.tokens {
  position: absolute;
  bottom: 2px;
  right: 2px;
  display: flex;
  flex-wrap: wrap;
  gap: 1px;
  max-width: 90%;
  justify-content: flex-end;
  z-index: 3;
}
.side-top .tokens {
  bottom: auto;
  top: 2px;
}
.token {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  display: grid;
  place-items: center;
  font-size: 7px;
  line-height: 1;
  box-shadow: 0 1px 2px #0008;
}
.owner-pip {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  border: 1px solid #fff8;
  z-index: 2;
}
.side-bottom .owner-pip {
  top: auto;
  bottom: 2px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
  padding: 0.55rem 0.65rem;
  background: rgba(18, 22, 26, 0.92);
  border: 1px solid rgba(243, 230, 200, 0.1);
  border-radius: 12px;
}
.btn-primary,
.btn-secondary,
.btn-danger,
.btn-mini {
  border-radius: 8px;
  padding: 0.55rem 0.95rem;
  border: 1px solid transparent;
  cursor: pointer;
  font-weight: 700;
  font-family: inherit;
}
.btn-primary {
  background: linear-gradient(180deg, #e8c97a, #c4a04a);
  color: #1a1408;
  box-shadow: 0 2px 0 #8a6a28;
}
.btn-roll {
  font-size: 1rem;
  padding: 0.65rem 1.2rem;
}
.btn-secondary {
  background: rgba(255, 255, 255, 0.07);
  color: var(--cream);
  border-color: rgba(243, 230, 200, 0.18);
}
.btn-danger {
  background: linear-gradient(180deg, #d64545, #a82020);
  color: #fff;
}
.btn-mini {
  padding: 0.28rem 0.5rem;
  font-size: 0.72rem;
  background: rgba(28, 24, 18, 0.08);
  color: var(--ink);
  border: 1px solid rgba(0, 0, 0, 0.15);
}
.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.resign {
  margin-left: auto;
}
.bid-label,
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
}
.bid-label {
  flex-direction: row;
  align-items: center;
  gap: 0.4rem;
}
.bid-label input,
.field input,
.field select,
.modal-card input,
.modal-card select {
  background: #1a1f28;
  color: #eee;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  width: 5.5rem;
  font-family: inherit;
}
.field select {
  width: 100%;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: grid;
  place-items: center;
  z-index: 40;
  padding: 1rem;
}
.modal-card {
  background: linear-gradient(180deg, #243028, #1a1f24);
  border: 1px solid rgba(243, 230, 200, 0.15);
  border-radius: 14px;
  padding: 1.25rem;
  width: min(560px, 94vw);
  max-height: 85vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  color: var(--cream);
}
.modal-card h3 {
  margin: 0;
  font-family: 'Libre Baskerville', Georgia, serif;
}
.prop-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.prop-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  font-size: 0.85rem;
}
.prop-swatch {
  width: 0.85rem;
  height: 1.6rem;
  border-radius: 2px;
  flex-shrink: 0;
}
.prop-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 6rem;
}
.prop-actions {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}
.prop-actions .btn-mini {
  background: rgba(243, 230, 200, 0.12);
  color: var(--cream);
  border-color: rgba(243, 230, 200, 0.2);
}
.muted {
  color: #9a958c;
  font-size: 0.75rem;
}
.empty {
  justify-content: center;
  color: #9a958c;
}
.cash-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.trade-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.trade-cols h4 {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: #9bb89a;
}
.check {
  display: flex;
  gap: 0.35rem;
  font-size: 0.8rem;
  margin: 0.2rem 0;
  align-items: flex-start;
}
.modal-actions {
  display: flex;
  gap: 0.5rem;
}

@media (max-width: 900px) {
  .mono-play {
    grid-template-columns: 1fr;
    height: auto;
  }
  .sidebar {
    max-height: 14rem;
    order: 2;
  }
  .main {
    order: 1;
  }
}
</style>
