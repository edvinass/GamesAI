#!/usr/bin/env python3
"""Generate Gravity Master level definitions for backend and frontend."""

from __future__ import annotations

import json
from pathlib import Path

FLOOR = {"type": "rect", "x": 400, "y": 580, "width": 760, "height": 24}


def rect(x: float, y: float, w: float, h: float, angle: float = 0) -> dict:
    body: dict = {"type": "rect", "x": x, "y": y, "width": w, "height": h}
    if angle:
        body["angle"] = angle
    return body


def circle(x: float, y: float, r: float) -> dict:
    return {"type": "circle", "x": x, "y": y, "radius": r}


def wall(x: float, y: float, h: float, *, thick: float = 16) -> dict:
    return rect(x, y, thick, h)


def ramp(x: float, y: float, w: float, angle: float) -> dict:
    return rect(x, y, w, 14, angle)


def peg(x: float, y: float, r: float = 20) -> dict:
    return circle(x, y, r)


def level(
    id_: int,
    name: str,
    hint: str,
    hint_fe: str,
    max_ink: int,
    ball: tuple[float, float, float],
    target: tuple[float, float, float],
    bodies: list[dict],
) -> dict:
    return {
        "id": id_,
        "name": name,
        "hint": hint,
        "hint_fe": hint_fe,
        "world_width": 800,
        "world_height": 600,
        "max_ink": max_ink,
        "ball": {"x": ball[0], "y": ball[1], "radius": ball[2]},
        "target": {"x": target[0], "y": target[1], "radius": target[2]},
        "static_bodies": [FLOOR, *bodies],
    }


LEVELS: list[dict] = [
    # --- Tutorial trio (1–5) ---
    level(
        1,
        "First Drop",
        "Draw a ramp so the ball rolls into the green target.",
        "Draw shapes — they fall right away. Build a ramp, then drop the ball.",
        420,
        (140, 90, 14),
        (660, 520, 28),
        [ramp(200, 440, 200, -0.22), peg(420, 360, 16)],
    ),
    level(
        2,
        "The Gap",
        "Bridge the gap between the two platforms.",
        "Two ledges, one chasm — drop bridge pieces until they meet in the middle.",
        400,
        (110, 80, 14),
        (690, 500, 26),
        [rect(150, 360, 200, 16), rect(650, 360, 200, 16), peg(400, 400, 18)],
    ),
    level(
        3,
        "Bounce Pad",
        "Use a steep slope to launch the ball toward the target.",
        "A steep slab is already waiting — add falling ramps to bank the ball right.",
        380,
        (120, 70, 14),
        (700, 540, 24),
        [ramp(380, 440, 420, -0.28), wall(620, 300, 120), peg(520, 280, 22)],
    ),
    level(
        4,
        "Pinball Alley",
        "Ricochet through the peg field.",
        "Thread the bumpers — draw walls while the ball is still rolling if you need to.",
        360,
        (400, 80, 14),
        (720, 520, 22),
        [
            peg(280, 240, 20),
            peg(520, 240, 20),
            peg(360, 340, 18),
            peg(440, 340, 18),
            peg(400, 440, 18),
            ramp(250, 480, 100, 0.55),
            ramp(550, 380, 100, -0.5),
        ],
    ),
    level(
        5,
        "Master Stroke",
        "Limited ink — every line counts.",
        "Three platforms, tiny ink budget — sketch the whole route before you drop.",
        240,
        (90, 100, 13),
        (710, 510, 20),
        [rect(160, 400, 120, 14), ramp(480, 320, 150, 0.4), ramp(660, 440, 90, -0.3)],
    ),
    # --- Ramps & routing (6–15) ---
    level(
        6,
        "Stairway",
        "Build steps that carry the ball upward and right.",
        "Static stubs mark the stair line — fill the gaps with falling planks.",
        410,
        (100, 70, 14),
        (680, 480, 24),
        [
            rect(180, 480, 100, 14),
            rect(320, 400, 100, 14),
            rect(460, 320, 100, 14),
            rect(600, 240, 100, 14),
            wall(700, 360, 100),
        ],
    ),
    level(
        7,
        "Funnel",
        "Guide the ball through the narrow opening.",
        "Walls form a funnel — shape a chute that feeds the ball through the mouth.",
        390,
        (400, 60, 14),
        (400, 530, 22),
        [
            wall(260, 340, 200),
            wall(540, 340, 200),
            ramp(400, 250, 180, 0.08),
            peg(400, 420, 20),
        ],
    ),
    level(
        8,
        "The Well",
        "Drop the ball into the pit from above.",
        "A rim surrounds the target — ramp over the lip or drop straight in.",
        370,
        (400, 70, 14),
        (400, 500, 26),
        [
            rect(400, 370, 260, 16),
            wall(310, 290, 120),
            wall(490, 290, 120),
            peg(400, 430, 24),
        ],
    ),
    level(
        9,
        "Split Path",
        "Choose the safer route around the center block.",
        "Go left or right around the pillar — both paths reach the target.",
        380,
        (120, 80, 14),
        (700, 500, 24),
        [
            rect(400, 340, 90, 180),
            ramp(200, 420, 160, -0.1),
            ramp(600, 420, 160, 0.1),
            peg(400, 480, 18),
        ],
    ),
    level(
        10,
        "Gate Crash",
        "Slip through the angled gates one at a time.",
        "Three tilted gates block the lane — draw guides to thread each gap.",
        360,
        (400, 65, 14),
        (720, 520, 22),
        [
            ramp(240, 240, 110, 0.6),
            ramp(560, 310, 110, -0.6),
            ramp(340, 410, 110, 0.45),
            peg(480, 480, 18),
        ],
    ),
    level(
        11,
        "Zigzag",
        "Hop across alternating ledges.",
        "Each ledge sits higher and farther right — chain falling bridges upward.",
        400,
        (90, 75, 14),
        (710, 490, 24),
        [
            rect(160, 380, 150, 14),
            rect(400, 290, 150, 14),
            rect(640, 200, 150, 14),
            peg(280, 330, 16),
            peg(520, 240, 16),
        ],
    ),
    level(
        12,
        "Tower Drop",
        "Circle the tower and reach the far side.",
        "A big bumper blocks the middle — wrap around it with falling ramps.",
        370,
        (150, 70, 14),
        (680, 510, 22),
        [circle(400, 310, 60), ramp(620, 400, 140, -0.12), wall(250, 380, 100)],
    ),
    level(
        13,
        "Canyon",
        "Cross the deep canyon with a sturdy bridge.",
        "A tall divider splits the floor — span it before you drop the ball.",
        410,
        (120, 85, 14),
        (680, 520, 26),
        [
            wall(400, 390, 220),
            rect(180, 350, 130, 14),
            rect(620, 350, 130, 14),
            peg(400, 320, 20),
        ],
    ),
    level(
        14,
        "Bumper Field",
        "Bounce off the pegs toward the target.",
        "Diamond of bumpers guards the goal — bank off them with angled planks.",
        390,
        (400, 60, 14),
        (700, 530, 22),
        [
            peg(320, 260, 22),
            peg(480, 260, 22),
            peg(320, 400, 22),
            peg(480, 400, 22),
            peg(400, 330, 18),
            ramp(600, 460, 120, -0.2),
        ],
    ),
    level(
        15,
        "Spiral Stairs",
        "Climb the spiral one step at a time.",
        "Five offset stubs spiral upward — connect them into one continuous ramp.",
        420,
        (100, 70, 14),
        (700, 470, 24),
        [
            rect(200, 500, 90, 14),
            rect(310, 420, 90, 14),
            rect(420, 340, 90, 14),
            rect(530, 260, 90, 14),
            rect(640, 180, 90, 14),
        ],
    ),
    # --- Obstacles & verticality (16–25) ---
    level(
        16,
        "Dead End",
        "The direct path is blocked — go over the wall.",
        "Twin walls seal the corridor — ramp up and over the barrier.",
        350,
        (120, 80, 14),
        (680, 500, 22),
        [
            wall(340, 390, 170),
            wall(560, 390, 170),
            ramp(450, 300, 130, 0.15),
            peg(450, 450, 18),
        ],
    ),
    level(
        17,
        "High Wire",
        "Reach the distant ledge without falling short.",
        "The target sits on a lonely ledge — build enough ramp to carry momentum.",
        330,
        (100, 70, 14),
        (720, 450, 20),
        [
            rect(680, 470, 110, 14),
            wall(400, 340, 150),
            ramp(300, 460, 160, -0.15),
            peg(550, 400, 16),
        ],
    ),
    level(
        18,
        "Catapult",
        "Build a launch ramp off the steep slope.",
        "A steep slab waits mid-screen — fling the ball toward the far target.",
        360,
        (150, 75, 14),
        (700, 540, 22),
        [ramp(290, 370, 170, -0.7), rect(550, 300, 120, 14), peg(420, 480, 20)],
    ),
    level(
        19,
        "Maze Lite",
        "Navigate around the box obstacles.",
        "Three walls form a mini maze — weave through with falling ramps.",
        380,
        (80, 70, 14),
        (720, 510, 22),
        [
            rect(250, 290, 150, 14),
            rect(450, 370, 150, 14),
            wall(350, 450, 110),
            wall(550, 250, 110),
            peg(620, 420, 18),
        ],
    ),
    level(
        20,
        "Plinko",
        "Let the ball cascade through the pegs.",
        "Triangle peg board — nudge the ball left or right as it falls.",
        400,
        (400, 55, 14),
        (400, 530, 24),
        [
            peg(340, 180, 18),
            peg(460, 180, 18),
            peg(300, 260, 18),
            peg(400, 260, 18),
            peg(500, 260, 18),
            peg(340, 340, 18),
            peg(460, 340, 18),
            peg(400, 420, 18),
        ],
    ),
    level(
        21,
        "The Ledge",
        "Roll the ball onto the high ledge.",
        "Target sits above the floor — build a tall ramp with a flat landing.",
        370,
        (120, 80, 14),
        (650, 380, 22),
        [rect(620, 400, 160, 14), ramp(300, 470, 220, -0.25), wall(500, 320, 100)],
    ),
    level(
        22,
        "Labyrinth",
        "Find the path through the walled corridor.",
        "S-shaped corridor — tight turns and a slim ink budget.",
        340,
        (100, 70, 14),
        (700, 520, 20),
        [
            wall(300, 240, 170),
            wall(500, 340, 170),
            ramp(400, 440, 200, 0.05),
            rect(200, 340, 120, 14),
            peg(600, 460, 18),
        ],
    ),
    level(
        23,
        "Double Gap",
        "Bridge two gaps in a row.",
        "Two chasms in sequence — reuse settled shapes as footing for the next span.",
        390,
        (90, 75, 14),
        (710, 500, 24),
        [
            rect(200, 370, 150, 14),
            wall(400, 370, 130),
            rect(600, 370, 150, 14),
            ramp(400, 270, 150, 0.1),
            peg(400, 470, 16),
        ],
    ),
    level(
        24,
        "Island Hop",
        "Hop between tiny floating platforms.",
        "Four tiny islands at different heights — compact shapes land best.",
        410,
        (100, 70, 14),
        (700, 480, 22),
        [
            rect(220, 420, 70, 14),
            rect(380, 340, 70, 14),
            rect(540, 260, 70, 14),
            rect(680, 400, 70, 14),
            peg(460, 480, 16),
        ],
    ),
    level(
        25,
        "The Slide",
        "Send the ball down the long ramp.",
        "One long slide can win it — angle your falling ramp to match the chute.",
        370,
        (150, 70, 14),
        (700, 530, 24),
        [ramp(400, 340, 520, -0.14), rect(600, 450, 120, 14), peg(350, 480, 18)],
    ),
    # --- Reverse & precision (26–35) ---
    level(
        26,
        "Corkscrew",
        "Wind down through the offset platforms.",
        "Start top-right, finish bottom-left — each step shifts sideways.",
        390,
        (680, 70, 14),
        (120, 520, 24),
        [
            rect(600, 190, 120, 14),
            rect(480, 290, 120, 14),
            rect(360, 390, 120, 14),
            rect(240, 480, 120, 14),
            peg(520, 380, 18),
        ],
    ),
    level(
        27,
        "Narrow Gate",
        "Thread the needle into the target alcove.",
        "A tight gate leads to the alcove — approach with a controlled ramp.",
        320,
        (400, 60, 14),
        (400, 520, 20),
        [
            wall(330, 370, 130),
            wall(470, 370, 130),
            ramp(400, 290, 70, 0.05),
            peg(400, 460, 16),
        ],
    ),
    level(
        28,
        "The Pillar",
        "Wrap around the central pillar.",
        "Ring of bumpers surrounds the pillar — pick a side and loop around.",
        360,
        (400, 65, 14),
        (700, 520, 22),
        [
            circle(400, 340, 50),
            peg(280, 340, 18),
            peg(520, 340, 18),
            peg(400, 240, 18),
            ramp(620, 440, 140, -0.15),
        ],
    ),
    level(
        29,
        "Corner Pocket",
        "Sink the ball into the bottom-right pocket.",
        "Billiards-style pocket — use the walls to funnel into the corner.",
        350,
        (120, 70, 14),
        (740, 540, 20),
        [
            wall(650, 440, 170),
            rect(580, 370, 140, 14),
            wall(300, 390, 120),
            peg(500, 480, 20),
        ],
    ),
    level(
        30,
        "S-Curve",
        "Follow the S-curve path downward.",
        "Three angled slabs hint at the S — extend them with falling ramps.",
        380,
        (150, 75, 14),
        (680, 510, 22),
        [
            ramp(270, 290, 150, 0.4),
            ramp(530, 390, 150, -0.4),
            ramp(340, 470, 150, 0.3),
            peg(450, 350, 16),
        ],
    ),
    level(
        31,
        "Domino Run",
        "Set up a chain of angled domino ramps.",
        "Four tilted slabs — each bounce should pass the ball to the next.",
        370,
        (100, 70, 14),
        (710, 500, 22),
        [
            ramp(200, 440, 100, 0.35),
            ramp(350, 370, 100, -0.3),
            ramp(500, 300, 100, 0.35),
            ramp(650, 410, 100, -0.25),
        ],
    ),
    level(
        32,
        "The Vault",
        "Climb over the vault wall to reach the target.",
        "Target hides behind a tall wall — go up and over the top.",
        340,
        (120, 80, 14),
        (680, 480, 22),
        [
            wall(450, 390, 190),
            ramp(450, 290, 160, 0.1),
            rect(620, 420, 140, 14),
            peg(350, 460, 18),
        ],
    ),
    level(
        33,
        "Seesaw",
        "Cross the tilted plank without sliding off.",
        "Land squarely on the tilted plank so the ball rolls to the far end.",
        360,
        (200, 70, 14),
        (680, 500, 22),
        [ramp(420, 370, 230, 0.25), rect(620, 460, 120, 14), peg(420, 480, 16)],
    ),
    level(
        34,
        "Gauntlet",
        "Survive the obstacle gauntlet.",
        "Five obstacles guard the lane — draw early, drop when the path is ready.",
        410,
        (400, 55, 14),
        (720, 530, 20),
        [
            ramp(240, 210, 80, 0.45),
            ramp(560, 270, 80, -0.45),
            ramp(340, 350, 80, 0.4),
            ramp(500, 410, 80, -0.4),
            peg(400, 470, 26),
        ],
    ),
    level(
        35,
        "Long Shot",
        "A long journey with very little ink.",
        "Huge distance, minimal ink — one well-placed ramp must do the work.",
        230,
        (80, 80, 13),
        (720, 520, 20),
        [rect(200, 410, 130, 14), ramp(500, 330, 170, 0.22), peg(400, 480, 16)],
    ),
    # --- Chambers & finales (36–50) ---
    level(
        36,
        "Hourglass",
        "Pass through the pinched middle.",
        "Wide top, narrow waist, wide bottom — funnel through the pinch.",
        370,
        (400, 60, 14),
        (400, 530, 22),
        [
            ramp(250, 240, 150, 0.15),
            ramp(550, 240, 150, -0.15),
            wall(300, 390, 120),
            wall(500, 390, 120),
            peg(400, 340, 18),
        ],
    ),
    level(
        37,
        "Roller Coaster",
        "Ride the series of steep ramps.",
        "Chain steep ramps for a roller-coaster line into the target.",
        390,
        (120, 70, 14),
        (700, 520, 22),
        [
            ramp(240, 340, 140, -0.45),
            ramp(440, 270, 140, 0.4),
            ramp(620, 390, 140, -0.35),
            peg(340, 450, 18),
        ],
    ),
    level(
        38,
        "The Trap",
        "Enter the trap through the only opening.",
        "Three walls surround the target — find the gap and funnel in.",
        350,
        (400, 65, 14),
        (400, 500, 22),
        [
            wall(310, 370, 150),
            wall(490, 370, 150),
            ramp(400, 310, 140, 0.05),
            rect(400, 430, 70, 14),
            peg(400, 380, 16),
        ],
    ),
    level(
        39,
        "Floating Isles",
        "Leap across widely spaced islands.",
        "Islands are far apart — bridges must land flush or the ball tumbles off.",
        420,
        (80, 75, 14),
        (720, 490, 22),
        [
            rect(170, 440, 65, 14),
            rect(330, 350, 65, 14),
            rect(490, 260, 65, 14),
            rect(650, 370, 65, 14),
            peg(410, 480, 16),
        ],
    ),
    level(
        40,
        "The Chute",
        "Drop the ball through the vertical chute.",
        "Vertical chute with pegs inside — align a ramp so the ball drops cleanly.",
        360,
        (400, 55, 14),
        (400, 520, 24),
        [
            wall(350, 290, 210),
            wall(450, 290, 210),
            ramp(400, 210, 60, 0.05),
            peg(380, 350, 16),
            peg(420, 420, 16),
        ],
    ),
    level(
        41,
        "Balance Beam",
        "Cross the thin balance beam.",
        "A razor-thin beam spans the gap — center your shapes or the ball falls.",
        300,
        (150, 70, 14),
        (680, 480, 20),
        [rect(420, 400, 220, 10), rect(620, 460, 100, 14), peg(420, 350, 16)],
    ),
    level(
        42,
        "Ricochet",
        "Bank shots off the circular bumpers.",
        "Three bumpers form a bank shot — redirect the ball toward the goal.",
        380,
        (100, 70, 14),
        (710, 510, 22),
        [
            peg(340, 270, 30),
            peg(520, 330, 30),
            peg(400, 420, 24),
            ramp(450, 460, 120, 0.18),
        ],
    ),
    level(
        43,
        "Fortress",
        "Breach the fortress walls.",
        "Inner courtyard hides the target — ramp over the wall or slip through.",
        340,
        (400, 60, 14),
        (680, 500, 20),
        [
            wall(490, 370, 170),
            wall(610, 370, 170),
            ramp(550, 290, 120, 0.1),
            rect(680, 440, 100, 14),
            peg(550, 450, 18),
        ],
    ),
    level(
        44,
        "Triple Bounce",
        "Bounce three times before the finish.",
        "Three steep slabs — each bounce must aim at the next.",
        370,
        (120, 75, 14),
        (700, 530, 22),
        [
            ramp(240, 390, 120, -0.5),
            ramp(420, 310, 120, 0.45),
            ramp(590, 430, 120, -0.4),
            peg(330, 480, 16),
        ],
    ),
    level(
        45,
        "The Needle",
        "Thread the needle with precision.",
        "Tiny gate, tiny target — precision beats speed here.",
        260,
        (400, 60, 14),
        (720, 520, 18),
        [
            wall(340, 340, 150),
            wall(460, 340, 150),
            ramp(550, 410, 120, -0.08),
            peg(400, 420, 14),
        ],
    ),
    level(
        46,
        "Cascade",
        "Let the ball cascade down the terraces.",
        "Four terraces step down leftward — catch and pass at each level.",
        400,
        (680, 70, 14),
        (120, 520, 24),
        [
            rect(600, 170, 130, 14),
            rect(480, 270, 130, 14),
            rect(360, 370, 130, 14),
            rect(240, 470, 130, 14),
            peg(420, 320, 18),
        ],
    ),
    level(
        47,
        "The Arch",
        "Roll under the arch and into the target.",
        "Pass under the arch — too high and you sail over the goal.",
        360,
        (150, 70, 14),
        (650, 510, 22),
        [
            ramp(400, 310, 210, 0.05),
            wall(310, 250, 100),
            wall(490, 250, 100),
            peg(400, 420, 18),
        ],
    ),
    level(
        48,
        "Switchback",
        "Climb the switchback trail.",
        "Sharp switchbacks — alternate direction on each ramp segment.",
        380,
        (90, 75, 14),
        (710, 490, 22),
        [
            ramp(190, 470, 140, 0.55),
            ramp(400, 370, 140, -0.55),
            ramp(610, 270, 140, 0.5),
            peg(300, 400, 16),
        ],
    ),
    level(
        49,
        "Final Bridge",
        "One last long bridge to the tiny target.",
        "Three gaps, tiny target — make every pixel of ink count.",
        290,
        (100, 80, 13),
        (720, 510, 18),
        [
            rect(200, 390, 150, 14),
            wall(500, 310, 150),
            rect(650, 440, 100, 14),
            peg(400, 450, 16),
        ],
    ),
    level(
        50,
        "Gravity Master",
        "The ultimate test — prove you master gravity.",
        "Bumpers, gates, and a tiny goal — everything you have learned, one level.",
        260,
        (400, 55, 13),
        (400, 520, 18),
        [
            peg(260, 220, 26),
            peg(540, 220, 26),
            peg(400, 300, 22),
            wall(330, 370, 130),
            wall(470, 370, 130),
            ramp(400, 290, 90, 0.15),
            ramp(230, 440, 100, -0.35),
            ramp(570, 440, 100, 0.35),
            peg(400, 470, 18),
        ],
    ),
]


def _py_value(v: object, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(v, dict):
        if not v:
            return "{}"
        lines = ["{"]
        for key, val in v.items():
            lines.append(f'{pad}    "{key}": {_py_value(val, indent + 4)},')
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(isinstance(x, dict) for x in v):
            lines = ["["]
            for item in v:
                item_str = _py_value(item, indent + 4)
                lines.append(f"{pad}    {item_str},")
            lines.append(f"{pad}]")
            return "\n".join(lines)
        return repr(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    return repr(v)


def render_python(levels: list[dict]) -> str:
    backend_levels = []
    for lv in levels:
        backend_levels.append(
            {
                "id": lv["id"],
                "name": lv["name"],
                "hint": lv["hint"],
                "world_width": lv["world_width"],
                "world_height": lv["world_height"],
                "max_ink": lv["max_ink"],
                "ball": lv["ball"],
                "target": lv["target"],
                "static_bodies": lv["static_bodies"],
            }
        )
    parts = ["LEVELS: list[dict] = ["]
    for lv in backend_levels:
        parts.append(f"    {_py_value(lv)},")
    parts.append("]")
    return "\n".join(parts) + "\n"


def render_typescript(levels: list[dict]) -> str:
    header = """export interface GravityStaticBody {
  type: 'rect' | 'circle'
  x: number
  y: number
  width?: number
  height?: number
  radius?: number
  angle?: number
}

export interface GravityLevel {
  id: number
  name: string
  hint: string
  world_width: number
  world_height: number
  max_ink: number
  ball: { x: number; y: number; radius: number }
  target: { x: number; y: number; radius: number }
  static_bodies: GravityStaticBody[]
  /** Min axis scale when fitted to a viewport (design levels omit this). */
  layout_scale?: number
}

export const DESIGN_WIDTH = 800
export const DESIGN_HEIGHT = 600
export const STROKE_WIDTH = 10

export function scaleLevelToViewport(level: GravityLevel, width: number, height: number): GravityLevel {
  const layoutScale = Math.min(width / level.world_width, height / level.world_height)
  const scale = (n: number) => n * layoutScale

  return {
    ...level,
    world_width: width,
    world_height: height,
    layout_scale: layoutScale,
    ball: {
      x: scale(level.ball.x),
      y: scale(level.ball.y),
      radius: scale(level.ball.radius),
    },
    target: {
      x: scale(level.target.x),
      y: scale(level.target.y),
      radius: scale(level.target.radius),
    },
    static_bodies: level.static_bodies.map((body) => ({
      ...body,
      x: scale(body.x),
      y: scale(body.y),
      width: body.width !== undefined ? scale(body.width) : undefined,
      height: body.height !== undefined ? scale(body.height) : undefined,
      radius: body.radius !== undefined ? scale(body.radius) : undefined,
    })),
  }
}

export function scaledStrokeWidth(level: GravityLevel): number {
  return STROKE_WIDTH * (level.layout_scale ?? 1)
}

export const GRAVITY_LEVELS: GravityLevel[] = [
"""
    footer = """]

export function strokeLength(points: { x: number; y: number }[]): number {
  let total = 0
  for (let i = 1; i < points.length; i++) {
    total += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y)
  }
  return total
}

export function totalInkUsed(strokes: { x: number; y: number }[][]): number {
  return strokes.reduce((sum, stroke) => sum + strokeLength(stroke), 0)
}
"""

    def ts_body(body: dict) -> str:
        parts = [f"      {{ type: '{body['type']}', x: {body['x']}, y: {body['y']}"]
        if "width" in body:
            parts.append(f", width: {body['width']}")
        if "height" in body:
            parts.append(f", height: {body['height']}")
        if "radius" in body:
            parts.append(f", radius: {body['radius']}")
        if "angle" in body:
            parts.append(f", angle: {body['angle']}")
        parts.append(" }")
        return "".join(parts)

    entries = []
    for lv in levels:
        bodies = ",\n".join(ts_body(b) for b in lv["static_bodies"])
        entries.append(
            f"""  {{
    id: {lv['id']},
    name: {json.dumps(lv['name'])},
    hint: {json.dumps(lv['hint_fe'])},
    world_width: {lv['world_width']},
    world_height: {lv['world_height']},
    max_ink: {lv['max_ink']},
    ball: {{ x: {lv['ball']['x']}, y: {lv['ball']['y']}, radius: {lv['ball']['radius']} }},
    target: {{ x: {lv['target']['x']}, y: {lv['target']['y']}, radius: {lv['target']['radius']} }},
    static_bodies: [
{bodies},
    ],
  }}"""
        )
    return header + ",\n".join(entries) + footer


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    if len(LEVELS) != 50:
        raise SystemExit(f"Expected 50 levels, got {len(LEVELS)}")

    py_path = root / "backend/app/games/gravity_master/levels.py"
    ts_path = root / "frontend/src/games/gravity_master/levels.ts"
    py_path.write_text(render_python(LEVELS), encoding="utf-8")
    ts_path.write_text(render_typescript(LEVELS), encoding="utf-8")
    print(f"Wrote {len(LEVELS)} levels to {py_path} and {ts_path}")


if __name__ == "__main__":
    main()
