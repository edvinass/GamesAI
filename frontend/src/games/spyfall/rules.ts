import type { GameRules } from '../codenames/rules'

export const spyfallRules: GameRules = {
  title: 'Spyfall',
  subtitle: 'Find the spy hiding at a secret location',
  quickStart: [
    'When the round starts, read your assignment — Spy or Resident.',
    'Residents share one location and each get a role; everyone can see the full list of possible locations.',
    'Take turns asking one other player a question (typed online, or aloud in Same room mode).',
    'Accuse someone to start a vote, or (as Spy) guess the location to end the round.',
  ],
  sections: [
    {
      heading: 'Your assignment',
      body: 'At the start of each round you are either the Spy or a Resident. This app shows your assignment clearly before play begins.',
      bullets: [
        'Resident: you know the location and your role. Use the location list to craft distinguishing questions.',
        'Spy: you do not know the location. Use the location list to narrow possibilities and guess.',
      ],
    },
    {
      heading: 'Questioning phase',
      body: 'Players take turns. On your turn, pick one other player and ask a single question. They must reply in character.',
      bullets: [
        'Residents: ask questions that test whether others know the location — without naming it yourself.',
        'Spy: ask vague questions that could fit many locations. Bluff if you need to.',
        'Online: type Q&A in the app. Same room: speak aloud, then confirm on your device.',
      ],
    },
    {
      heading: 'Same room mode',
      body: 'Enable this in the lobby when everyone is together. Phones only show secrets and track turns — you talk face to face.',
      bullets: [
        'Asker picks a target and asks aloud, then taps confirm.',
        'Target answers aloud, then taps confirm to advance the turn.',
        'Accusations, votes, and spy location guesses still happen in the app.',
      ],
    },
    {
      heading: 'Accusation & voting',
      body: 'Any player can call an accusation during questioning. Everyone then votes once for who they think is the Spy.',
      bullets: [
        'Majority votes for the Spy → Residents win.',
        'Wrong target or a tie → Spy wins the vote.',
        'You may abstain, but that counts as your vote.',
      ],
    },
    {
      heading: 'Spy location guess',
      body: 'The Spy can guess the location at any time during questioning — from the action panel or by selecting from the location list.',
      bullets: [
        'Correct guess → Spy wins immediately.',
        'Wrong guess → Residents win immediately.',
      ],
    },
    {
      heading: 'Timer',
      body: 'If a round timer is enabled, questioning ends automatically when time runs out and voting begins.',
    },
    {
      heading: 'AI & solo practice',
      body: 'Need a full table? The host can add AI players in the lobby, or enable solo practice for a 3-player game (you + 2 AI). Same room mode is humans only — AI seats are disabled.',
    },
  ],
  tips: [
    'Read your assignment carefully before dismissing the reveal screen.',
    'Residents: answer naturally for your role — overly perfect answers can make you look suspicious.',
    'Everyone: keep the location list open — residents to ask sharper questions, the Spy to narrow guesses.',
    'Same room: keep phones face-up for roles, but talk to each other — not the chat box.',
  ],
}
