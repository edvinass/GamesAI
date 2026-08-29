"""Standard US-style Monopoly board, decks, and rent helpers."""

from __future__ import annotations

from copy import deepcopy

# Color groups: property indices belonging to each set
COLOR_SETS: dict[str, list[int]] = {
    "brown": [1, 3],
    "light_blue": [6, 8, 9],
    "pink": [11, 13, 14],
    "orange": [16, 18, 19],
    "red": [21, 23, 24],
    "yellow": [26, 27, 29],
    "green": [31, 32, 34],
    "dark_blue": [37, 39],
}

RAILROADS = [5, 15, 25, 35]
UTILITIES = [12, 28]

# rents: [site, 1h, 2h, 3h, 4h, hotel]
SPACES: list[dict] = [
    {"id": 0, "name": "GO", "kind": "go"},
    {
        "id": 1,
        "name": "Mediterranean Avenue",
        "kind": "property",
        "color": "brown",
        "price": 60,
        "house_cost": 50,
        "rents": [2, 10, 30, 90, 160, 250],
        "mortgage": 30,
    },
    {"id": 2, "name": "Community Chest", "kind": "community_chest"},
    {
        "id": 3,
        "name": "Baltic Avenue",
        "kind": "property",
        "color": "brown",
        "price": 60,
        "house_cost": 50,
        "rents": [4, 20, 60, 180, 320, 450],
        "mortgage": 30,
    },
    {"id": 4, "name": "Income Tax", "kind": "tax", "tax": 200},
    {
        "id": 5,
        "name": "Reading Railroad",
        "kind": "railroad",
        "price": 200,
        "mortgage": 100,
    },
    {
        "id": 6,
        "name": "Oriental Avenue",
        "kind": "property",
        "color": "light_blue",
        "price": 100,
        "house_cost": 50,
        "rents": [6, 30, 90, 270, 400, 550],
        "mortgage": 50,
    },
    {"id": 7, "name": "Chance", "kind": "chance"},
    {
        "id": 8,
        "name": "Vermont Avenue",
        "kind": "property",
        "color": "light_blue",
        "price": 100,
        "house_cost": 50,
        "rents": [6, 30, 90, 270, 400, 550],
        "mortgage": 50,
    },
    {
        "id": 9,
        "name": "Connecticut Avenue",
        "kind": "property",
        "color": "light_blue",
        "price": 120,
        "house_cost": 50,
        "rents": [8, 40, 100, 300, 450, 600],
        "mortgage": 60,
    },
    {"id": 10, "name": "Jail / Just Visiting", "kind": "jail"},
    {
        "id": 11,
        "name": "St. Charles Place",
        "kind": "property",
        "color": "pink",
        "price": 140,
        "house_cost": 100,
        "rents": [10, 50, 150, 450, 625, 750],
        "mortgage": 70,
    },
    {
        "id": 12,
        "name": "Electric Company",
        "kind": "utility",
        "price": 150,
        "mortgage": 75,
    },
    {
        "id": 13,
        "name": "States Avenue",
        "kind": "property",
        "color": "pink",
        "price": 140,
        "house_cost": 100,
        "rents": [10, 50, 150, 450, 625, 750],
        "mortgage": 70,
    },
    {
        "id": 14,
        "name": "Virginia Avenue",
        "kind": "property",
        "color": "pink",
        "price": 160,
        "house_cost": 100,
        "rents": [12, 60, 180, 500, 700, 900],
        "mortgage": 80,
    },
    {
        "id": 15,
        "name": "Pennsylvania Railroad",
        "kind": "railroad",
        "price": 200,
        "mortgage": 100,
    },
    {
        "id": 16,
        "name": "St. James Place",
        "kind": "property",
        "color": "orange",
        "price": 180,
        "house_cost": 100,
        "rents": [14, 70, 200, 550, 750, 950],
        "mortgage": 90,
    },
    {"id": 17, "name": "Community Chest", "kind": "community_chest"},
    {
        "id": 18,
        "name": "Tennessee Avenue",
        "kind": "property",
        "color": "orange",
        "price": 180,
        "house_cost": 100,
        "rents": [14, 70, 200, 550, 750, 950],
        "mortgage": 90,
    },
    {
        "id": 19,
        "name": "New York Avenue",
        "kind": "property",
        "color": "orange",
        "price": 200,
        "house_cost": 100,
        "rents": [16, 80, 220, 600, 800, 1000],
        "mortgage": 100,
    },
    {"id": 20, "name": "Free Parking", "kind": "free_parking"},
    {
        "id": 21,
        "name": "Kentucky Avenue",
        "kind": "property",
        "color": "red",
        "price": 220,
        "house_cost": 150,
        "rents": [18, 90, 250, 700, 875, 1050],
        "mortgage": 110,
    },
    {"id": 22, "name": "Chance", "kind": "chance"},
    {
        "id": 23,
        "name": "Indiana Avenue",
        "kind": "property",
        "color": "red",
        "price": 220,
        "house_cost": 150,
        "rents": [18, 90, 250, 700, 875, 1050],
        "mortgage": 110,
    },
    {
        "id": 24,
        "name": "Illinois Avenue",
        "kind": "property",
        "color": "red",
        "price": 240,
        "house_cost": 150,
        "rents": [20, 100, 300, 750, 925, 1100],
        "mortgage": 120,
    },
    {
        "id": 25,
        "name": "B&O Railroad",
        "kind": "railroad",
        "price": 200,
        "mortgage": 100,
    },
    {
        "id": 26,
        "name": "Atlantic Avenue",
        "kind": "property",
        "color": "yellow",
        "price": 260,
        "house_cost": 150,
        "rents": [22, 110, 330, 800, 975, 1150],
        "mortgage": 130,
    },
    {
        "id": 27,
        "name": "Ventnor Avenue",
        "kind": "property",
        "color": "yellow",
        "price": 260,
        "house_cost": 150,
        "rents": [22, 110, 330, 800, 975, 1150],
        "mortgage": 130,
    },
    {
        "id": 28,
        "name": "Water Works",
        "kind": "utility",
        "price": 150,
        "mortgage": 75,
    },
    {
        "id": 29,
        "name": "Marvin Gardens",
        "kind": "property",
        "color": "yellow",
        "price": 280,
        "house_cost": 150,
        "rents": [24, 120, 360, 850, 1025, 1200],
        "mortgage": 140,
    },
    {"id": 30, "name": "Go To Jail", "kind": "go_to_jail"},
    {
        "id": 31,
        "name": "Pacific Avenue",
        "kind": "property",
        "color": "green",
        "price": 300,
        "house_cost": 200,
        "rents": [26, 130, 390, 900, 1100, 1275],
        "mortgage": 150,
    },
    {
        "id": 32,
        "name": "North Carolina Avenue",
        "kind": "property",
        "color": "green",
        "price": 300,
        "house_cost": 200,
        "rents": [26, 130, 390, 900, 1100, 1275],
        "mortgage": 150,
    },
    {"id": 33, "name": "Community Chest", "kind": "community_chest"},
    {
        "id": 34,
        "name": "Pennsylvania Avenue",
        "kind": "property",
        "color": "green",
        "price": 320,
        "house_cost": 200,
        "rents": [28, 150, 450, 1000, 1200, 1400],
        "mortgage": 160,
    },
    {
        "id": 35,
        "name": "Short Line",
        "kind": "railroad",
        "price": 200,
        "mortgage": 100,
    },
    {"id": 36, "name": "Chance", "kind": "chance"},
    {
        "id": 37,
        "name": "Park Place",
        "kind": "property",
        "color": "dark_blue",
        "price": 350,
        "house_cost": 200,
        "rents": [35, 175, 500, 1100, 1300, 1500],
        "mortgage": 175,
    },
    {"id": 38, "name": "Luxury Tax", "kind": "tax", "tax": 100},
    {
        "id": 39,
        "name": "Boardwalk",
        "kind": "property",
        "color": "dark_blue",
        "price": 400,
        "house_cost": 200,
        "rents": [50, 200, 600, 1400, 1700, 2000],
        "mortgage": 200,
    },
]

# Card effects: type + args. "get_out_of_jail" is held by the player.
CHANCE_CARDS: list[dict] = [
    {"id": "chance_go", "text": "Advance to GO. Collect $200.", "effect": "advance", "to": 0},
    {"id": "chance_illinois", "text": "Advance to Illinois Avenue.", "effect": "advance", "to": 24},
    {"id": "chance_st_charles", "text": "Advance to St. Charles Place.", "effect": "advance", "to": 11},
    {
        "id": "chance_nearest_util",
        "text": "Advance to the nearest Utility.",
        "effect": "nearest_utility",
    },
    {
        "id": "chance_nearest_rr",
        "text": "Advance to the nearest Railroad.",
        "effect": "nearest_railroad",
    },
    {"id": "chance_50", "text": "Bank pays you dividend of $50.", "effect": "cash", "amount": 50},
    {
        "id": "chance_jail_card",
        "text": "Get Out of Jail Free.",
        "effect": "get_out_of_jail",
    },
    {"id": "chance_back_3", "text": "Go back 3 spaces.", "effect": "move_relative", "steps": -3},
    {"id": "chance_jail", "text": "Go directly to Jail.", "effect": "go_to_jail"},
    {
        "id": "chance_repairs",
        "text": "Make general repairs: $25 per house, $100 per hotel.",
        "effect": "repairs",
        "house": 25,
        "hotel": 100,
    },
    {"id": "chance_poor_tax", "text": "Pay poor tax of $15.", "effect": "cash", "amount": -15},
    {"id": "chance_reading", "text": "Take a trip to Reading Railroad.", "effect": "advance", "to": 5},
    {"id": "chance_boardwalk", "text": "Take a walk on the Boardwalk.", "effect": "advance", "to": 39},
    {
        "id": "chance_chairman",
        "text": "You have been elected Chairman — pay each player $50.",
        "effect": "pay_each",
        "amount": 50,
    },
    {"id": "chance_loan", "text": "Your building loan matures. Collect $150.", "effect": "cash", "amount": 150},
    {"id": "chance_crossword", "text": "You won a crossword competition. Collect $100.", "effect": "cash", "amount": 100},
]

COMMUNITY_CHEST_CARDS: list[dict] = [
    {"id": "cc_go", "text": "Advance to GO. Collect $200.", "effect": "advance", "to": 0},
    {"id": "cc_bank_error", "text": "Bank error in your favor. Collect $200.", "effect": "cash", "amount": 200},
    {"id": "cc_doctor", "text": "Doctor's fees. Pay $50.", "effect": "cash", "amount": -50},
    {"id": "cc_stock", "text": "From sale of stock you get $50.", "effect": "cash", "amount": 50},
    {
        "id": "cc_jail_card",
        "text": "Get Out of Jail Free.",
        "effect": "get_out_of_jail",
    },
    {"id": "cc_jail", "text": "Go directly to Jail.", "effect": "go_to_jail"},
    {
        "id": "cc_opera",
        "text": "Grand Opera Night — collect $50 from every player.",
        "effect": "collect_each",
        "amount": 50,
    },
    {"id": "cc_holiday", "text": "Holiday fund matures. Collect $100.", "effect": "cash", "amount": 100},
    {"id": "cc_refund", "text": "Income tax refund. Collect $20.", "effect": "cash", "amount": 20},
    {
        "id": "cc_birthday",
        "text": "It is your birthday — collect $10 from every player.",
        "effect": "collect_each",
        "amount": 10,
    },
    {"id": "cc_insurance", "text": "Life insurance matures. Collect $100.", "effect": "cash", "amount": 100},
    {"id": "cc_hospital", "text": "Pay hospital fees of $100.", "effect": "cash", "amount": -100},
    {"id": "cc_school", "text": "Pay school fees of $50.", "effect": "cash", "amount": -50},
    {"id": "cc_consultancy", "text": "Receive $25 consultancy fee.", "effect": "cash", "amount": 25},
    {
        "id": "cc_repairs",
        "text": "You are assessed for street repairs: $40 per house, $115 per hotel.",
        "effect": "repairs",
        "house": 40,
        "hotel": 115,
    },
    {"id": "cc_beauty", "text": "You have won second prize in a beauty contest. Collect $10.", "effect": "cash", "amount": 10},
    {"id": "cc_inherit", "text": "You inherit $100.", "effect": "cash", "amount": 100},
]

TOKEN_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#e67e22"]


def space_by_id(space_id: int) -> dict:
    return SPACES[space_id]


def is_ownable(space: dict) -> bool:
    return space["kind"] in ("property", "railroad", "utility")


def railroad_rent(owned_count: int) -> int:
    return {1: 25, 2: 50, 3: 100, 4: 200}.get(owned_count, 0)


def utility_rent(owned_count: int, dice_total: int) -> int:
    if owned_count >= 2:
        return dice_total * 10
    if owned_count == 1:
        return dice_total * 4
    return 0


def fresh_decks(rng) -> tuple[list[dict], list[dict]]:
    chance = deepcopy(CHANCE_CARDS)
    community = deepcopy(COMMUNITY_CHEST_CARDS)
    rng.shuffle(chance)
    rng.shuffle(community)
    return chance, community
