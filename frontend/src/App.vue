<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <div class="ambient-bg" aria-hidden="true">
      <span class="orb orb-1" />
      <span class="orb orb-2" />
      <span class="orb orb-3" />
      <span class="orb orb-4" />
    </div>
    <RouterView v-slot="{ Component, route }">
      <Transition name="page">
        <component :is="Component" :key="route.path" />
      </Transition>
    </RouterView>
  </div>
</template>

<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  isolation: isolate;
}

.ambient-bg {
  position: fixed;
  inset: 0;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  animation: float 12s ease-in-out infinite;
}

.orb-1 {
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, #3d5a9e 0%, transparent 70%);
  top: -120px;
  left: -80px;
  animation-duration: 14s;
}

.orb-2 {
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, #6b3d8e 0%, transparent 70%);
  top: 40%;
  right: -100px;
  animation-duration: 18s;
  animation-delay: -4s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #2d6a6a 0%, transparent 70%);
  bottom: -80px;
  left: 30%;
  animation-duration: 16s;
  animation-delay: -8s;
}

.orb-4 {
  width: 240px;
  height: 240px;
  background: radial-gradient(circle, #8e3d5a 0%, transparent 70%);
  bottom: 20%;
  right: 25%;
  animation-duration: 20s;
  animation-delay: -2s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.05); }
  66% { transform: translate(-20px, 15px) scale(0.95); }
}
</style>
