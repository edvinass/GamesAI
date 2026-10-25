import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import RoomView from '@/views/RoomView.vue'
import GameView from '@/views/GameView.vue'
import ChessPath from '@/games/chess/tutorial/ChessPath.vue'
import ChessLesson from '@/games/chess/tutorial/ChessLesson.vue'
import { captureCheatParam } from '@/games/chess/cheatMode'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/chess/learn', name: 'chess-learn', component: ChessPath },
    { path: '/chess/learn/:lessonId', name: 'chess-lesson', component: ChessLesson },
    { path: '/r/:code', name: 'room-short', component: RoomView },
    { path: '/room/:id', name: 'room', component: RoomView },
    { path: '/room/:id/play', name: 'game', component: GameView },
  ],
})

router.beforeEach((to) => {
  captureCheatParam(to.query)
})

export default router
