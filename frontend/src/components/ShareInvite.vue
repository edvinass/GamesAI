<script setup lang="ts">
import { useShareRoom } from '@/composables/useShareRoom'

const props = defineProps<{
  code: string
  gameName?: string
}>()

const { code, shareUrl, canNativeShare, copied, share, copyLink, copyCode } = useShareRoom({
  code: () => props.code,
  gameName: () => props.gameName,
})
</script>

<template>
  <div class="share-invite">
    <span class="toolbar-label">Invite friends</span>

    <div class="code-row">
      <div class="code-block">
        <span class="code-label">Room code</span>
        <span class="code-value" aria-label="Room code">{{ code }}</span>
      </div>
      <button
        type="button"
        class="btn-secondary copy-btn"
        :class="{ copied: copied === 'code' }"
        @click="copyCode"
      >
        {{ copied === 'code' ? '✓ Copied' : 'Copy code' }}
      </button>
    </div>

    <div class="share-row">
      <input :value="shareUrl" readonly class="url-input" aria-label="Invite link" />
      <button
        type="button"
        class="btn-secondary copy-btn"
        :class="{ copied: copied === 'link' }"
        @click="copyLink"
      >
        {{ copied === 'link' ? '✓ Copied' : 'Copy link' }}
      </button>
      <button
        v-if="canNativeShare"
        type="button"
        class="btn-primary share-btn"
        @click="share"
      >
        Share
      </button>
    </div>
  </div>
</template>

<style scoped>
.share-invite {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.toolbar-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.code-row {
  display: flex;
  gap: 0.5rem;
  align-items: stretch;
}

.code-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
  background: rgba(91, 156, 255, 0.08);
}

.code-label {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.code-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: 0.28em;
  line-height: 1.2;
  color: var(--text);
}

.share-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.url-input {
  flex: 1 1 12rem;
  min-width: 0;
  font-size: 0.85rem;
}

.copy-btn,
.share-btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.copy-btn.copied {
  background: rgba(61, 214, 140, 0.15);
  border-color: var(--success);
  color: var(--success);
  animation: celebrate 0.4s var(--ease-bounce);
}

@keyframes celebrate {
  0% { transform: scale(1); }
  40% { transform: scale(1.06); }
  100% { transform: scale(1); }
}

@media (max-width: 520px) {
  .share-btn {
    flex: 1 1 100%;
  }

  .code-value {
    font-size: 1.25rem;
    letter-spacing: 0.2em;
  }
}
</style>
