import type { GameRules } from '../codenames/rules'

export const spyfallRules: GameRules = {
  title: 'Spyfall',
  sections: [
    {
      heading: 'Overview',
      body: 'Most players share a secret location and role. One player is the Spy and does not know the location. Everyone asks questions to figure out who the Spy is — while the Spy tries to guess the location.',
    },
    {
      heading: 'Questioning',
      body: 'Players take turns asking one other player a question. The target must answer in character. Use questions to probe who really knows the location without giving away too much yourself.',
    },
    {
      heading: 'Accusation & voting',
      body: 'Any player can call for a vote during questioning. Everyone votes for who they think is the Spy. A majority vote for the Spy means the residents win; otherwise the Spy wins.',
    },
    {
      heading: 'Spy guess',
      body: 'The Spy can guess the location at any time during questioning. A correct guess wins for the Spy; a wrong guess wins for the residents.',
    },
    {
      heading: 'Timer',
      body: 'When the round timer runs out, voting begins automatically. Use your time wisely!',
    },
  ],
}
