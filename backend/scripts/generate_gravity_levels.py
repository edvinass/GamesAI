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
    level(
        1,
        "First Drop",
        "Draw a ramp so the ball rolls into the green target.",
        "Draw shapes — they fall right away. Build a ramp, then drop the ball.",
        420,
        (140, 90, 14),
        (660, 520, 28),
        [rect(120, 420, 180, 16)],
    ),
    level(
        2,
        "The Gap",
        "Bridge the gap between the two platforms.",
        "Drop as many bridge pieces as you need to cross the gap.",
        380,
        (110, 80, 14),
        (690, 500, 26),
        [rect(150, 360, 220, 16), rect(650, 360, 220, 16)],
    ),
    level(
        3,
        "Bounce Pad",
        "Use a steep slope to launch the ball toward the target.",
        "Draw falling platforms to bounce the ball toward the target.",
        360,
        (120, 70, 14),
        (700, 540, 24),
        [rect(400, 460, 520, 16, -0.18), rect(620, 320, 140, 16)],
    ),
    level(
        4,
        "Pinball",
        "Guide the ball through the obstacles.",
        "Keep drawing walls and ramps while the ball moves.",
        340,
        (400, 80, 14),
        (720, 520, 22),
        [
            rect(250, 280, 120, 16, 0.5),
            rect(550, 380, 120, 16, -0.45),
            rect(400, 480, 80, 80),
        ],
    ),
    level(
        5,
        "Master Stroke",
        "Limited ink — every line counts.",
        "Every shape you draw falls — plan carefully, then drop the ball.",
        260,
        (90, 100, 13),
        (710, 510, 20),
        [
            rect(160, 400, 140, 14),
            rect(520, 320, 160, 14, 0.35),
            rect(680, 440, 100, 14, -0.25),
        ],
    ),
    level(
        6,
        "Stairway",
        "Build steps that carry the ball upward and right.",
        "Stack falling planks into stairs before you drop the ball.",
        400,
        (100, 70, 14),
        (680, 480, 24),
        [
            rect(180, 480, 120, 14),
            rect(320, 400, 120, 14),
            rect(460, 320, 120, 14),
            rect(600, 240, 120, 14),
        ],
    ),
    level(
        7,
        "Funnel",
        "Guide the ball through the narrow opening.",
        "Shape a chute that feeds the ball into the funnel mouth.",
        380,
        (400, 60, 14),
        (400, 530, 22),
        [
            rect(280, 350, 16, 180),
            rect(520, 350, 16, 180),
            rect(400, 260, 200, 14),
        ],
    ),
    level(
        8,
        "The Well",
        "Drop the ball into the pit from above.",
        "Build a ramp that drops the ball cleanly into the well.",
        360,
        (400, 70, 14),
        (400, 500, 26),
        [
            rect(400, 380, 280, 16),
            rect(320, 300, 16, 120),
            rect(480, 300, 16, 120),
        ],
    ),
    level(
        9,
        "Split Path",
        "Choose the safer route around the center block.",
        "Route around the pillar — both sides work if you plan ahead.",
        370,
        (120, 80, 14),
        (700, 500, 24),
        [rect(400, 340, 80, 160), rect(200, 420, 160, 14), rect(600, 420, 160, 14)],
    ),
    level(
        10,
        "Gate Crash",
        "Slip through the angled gates one at a time.",
        "Draw guides so the ball threads each gate without stopping.",
        350,
        (400, 65, 14),
        (720, 520, 22),
        [
            rect(250, 250, 100, 14, 0.55),
            rect(550, 320, 100, 14, -0.55),
            rect(350, 420, 100, 14, 0.4),
        ],
    ),
    level(
        11,
        "Zigzag",
        "Hop across alternating ledges.",
        "Bridge each ledge in the zigzag before releasing the ball.",
        390,
        (90, 75, 14),
        (710, 490, 24),
        [
            rect(160, 380, 180, 14),
            rect(400, 300, 180, 14),
            rect(640, 220, 180, 14),
        ],
    ),
    level(
        12,
        "Tower Drop",
        "Circle the tower and reach the far side.",
        "Use the tower as a bumper — wrap your path around it.",
        360,
        (150, 70, 14),
        (680, 510, 22),
        [circle(400, 320, 55), rect(620, 400, 140, 14)],
    ),
    level(
        13,
        "Canyon",
        "Cross the deep canyon with a sturdy bridge.",
        "Span the canyon — wide shapes settle faster than thin lines.",
        400,
        (120, 85, 14),
        (680, 520, 26),
        [rect(400, 400, 16, 200), rect(180, 360, 140, 14), rect(620, 360, 140, 14)],
    ),
    level(
        14,
        "Bumper Field",
        "Bounce off the pegs toward the target.",
        "Ricochet through the bumpers with angled falling planks.",
        380,
        (400, 60, 14),
        (700, 530, 22),
        [circle(280, 280, 22), circle(520, 320, 22), circle(360, 420, 22), circle(580, 460, 22)],
    ),
    level(
        15,
        "Spiral Stairs",
        "Climb the spiral one step at a time.",
        "Each step is offset — build a continuous spiral ramp.",
        410,
        (100, 70, 14),
        (700, 470, 24),
        [
            rect(200, 500, 100, 14),
            rect(300, 420, 100, 14),
            rect(400, 340, 100, 14),
            rect(500, 260, 100, 14),
            rect(600, 180, 100, 14),
        ],
    ),
    level(
        16,
        "Dead End",
        "The direct path is blocked — go over the wall.",
        "You cannot go straight — ramp up and over the barrier.",
        340,
        (120, 80, 14),
        (680, 500, 22),
        [rect(350, 400, 16, 160), rect(550, 400, 16, 160), rect(450, 320, 120, 14)],
    ),
    level(
        17,
        "High Wire",
        "Reach the distant ledge without falling short.",
        "Aim for the narrow ledge — momentum matters on the wire.",
        320,
        (100, 70, 14),
        (720, 450, 20),
        [rect(680, 470, 100, 14), rect(400, 350, 14, 140)],
    ),
    level(
        18,
        "Catapult",
        "Build a launch ramp off the steep slope.",
        "Use the steep slab to fling the ball toward the target.",
        350,
        (150, 75, 14),
        (700, 540, 22),
        [rect(300, 380, 160, 14, -0.65), rect(550, 300, 120, 14)],
    ),
    level(
        19,
        "Maze Lite",
        "Navigate around the box obstacles.",
        "Weave through the maze with falling walls and ramps.",
        370,
        (80, 70, 14),
        (720, 510, 22),
        [
            rect(250, 300, 140, 14),
            rect(450, 380, 140, 14),
            rect(350, 460, 14, 100),
            rect(550, 260, 14, 100),
        ],
    ),
    level(
        20,
        "Plinko",
        "Let the ball cascade through the pegs.",
        "Guide the ball down the peg board into the target zone.",
        390,
        (400, 55, 14),
        (400, 530, 24),
        [
            circle(320, 200, 18),
            circle(480, 200, 18),
            circle(360, 300, 18),
            circle(440, 300, 18),
            circle(400, 400, 18),
        ],
    ),
    level(
        21,
        "The Ledge",
        "Roll the ball onto the high ledge.",
        "Build enough ramp to reach the elevated target ledge.",
        360,
        (120, 80, 14),
        (650, 380, 22),
        [rect(620, 400, 160, 14), rect(300, 480, 200, 14, -0.2)],
    ),
    level(
        22,
        "Labyrinth",
        "Find the path through the walled corridor.",
        "Thread the corridor — tight turns, tight ink budget.",
        330,
        (100, 70, 14),
        (700, 520, 20),
        [
            rect(300, 250, 14, 160),
            rect(500, 350, 14, 160),
            rect(400, 450, 200, 14),
            rect(200, 350, 120, 14),
        ],
    ),
    level(
        23,
        "Double Gap",
        "Bridge two gaps in a row.",
        "Two jumps — reuse settled shapes as footing for the next span.",
        380,
        (90, 75, 14),
        (710, 500, 24),
        [
            rect(200, 380, 160, 14),
            rect(400, 380, 16, 120),
            rect(600, 380, 160, 14),
            rect(400, 280, 160, 14),
        ],
    ),
    level(
        24,
        "Island Hop",
        "Hop between tiny floating platforms.",
        "Small islands — drop compact shapes that land squarely.",
        400,
        (100, 70, 14),
        (700, 480, 22),
        [
            rect(220, 420, 80, 14),
            rect(380, 350, 80, 14),
            rect(540, 280, 80, 14),
            rect(680, 420, 80, 14),
        ],
    ),
    level(
        25,
        "The Slide",
        "Send the ball down the long ramp.",
        "One long slide can do the job — angle it carefully.",
        360,
        (150, 70, 14),
        (700, 530, 24),
        [rect(400, 350, 500, 16, -0.12), rect(600, 450, 120, 14)],
    ),
    level(
        26,
        "Corkscrew",
        "Wind down through the offset platforms.",
        "Each platform shifts left — plan a winding descent.",
        380,
        (680, 70, 14),
        (120, 520, 24),
        [
            rect(600, 200, 120, 14),
            rect(480, 300, 120, 14),
            rect(360, 400, 120, 14),
            rect(240, 480, 120, 14),
        ],
    ),
    level(
        27,
        "Narrow Gate",
        "Thread the needle into the target alcove.",
        "The gate is tight — approach with a controlled ramp.",
        310,
        (400, 60, 14),
        (400, 520, 20),
        [rect(340, 380, 14, 120), rect(460, 380, 14, 120), rect(400, 300, 80, 14)],
    ),
    level(
        28,
        "The Pillar",
        "Wrap around the central pillar.",
        "The pillar blocks the middle — route around either side.",
        350,
        (400, 65, 14),
        (700, 520, 22),
        [circle(400, 350, 45), rect(620, 440, 140, 14, -0.15)],
    ),
    level(
        29,
        "Corner Pocket",
        "Sink the ball into the bottom-right pocket.",
        "Use the walls to funnel the ball into the corner pocket.",
        340,
        (120, 70, 14),
        (740, 540, 20),
        [rect(650, 450, 14, 160), rect(580, 380, 140, 14), rect(300, 400, 14, 120)],
    ),
    level(
        30,
        "S-Curve",
        "Follow the S-curve path downward.",
        "Mirror the S-curve with angled falling ramps.",
        370,
        (150, 75, 14),
        (680, 510, 22),
        [
            rect(280, 300, 140, 14, 0.35),
            rect(520, 400, 140, 14, -0.35),
            rect(350, 480, 140, 14, 0.25),
        ],
    ),
    level(
        31,
        "Domino Run",
        "Set up a chain of angled domino ramps.",
        "Each tilted slab passes the ball to the next.",
        360,
        (100, 70, 14),
        (710, 500, 22),
        [
            rect(200, 450, 100, 14, 0.3),
            rect(350, 380, 100, 14, -0.25),
            rect(500, 310, 100, 14, 0.3),
            rect(650, 420, 100, 14, -0.2),
        ],
    ),
    level(
        32,
        "The Vault",
        "Climb over the vault wall to reach the target.",
        "The target sits behind the wall — go up and over.",
        330,
        (120, 80, 14),
        (680, 480, 22),
        [rect(450, 400, 16, 180), rect(450, 300, 160, 14), rect(620, 420, 140, 14)],
    ),
    level(
        33,
        "Seesaw",
        "Cross the tilted plank without sliding off.",
        "Land on the seesaw squarely so the ball rolls to the far end.",
        350,
        (200, 70, 14),
        (680, 500, 22),
        [rect(420, 380, 220, 14, 0.22), rect(620, 460, 120, 14)],
    ),
    level(
        34,
        "Gauntlet",
        "Survive the obstacle gauntlet.",
        "Many obstacles — draw early and drop when the path is ready.",
        400,
        (400, 55, 14),
        (720, 530, 20),
        [
            rect(250, 220, 80, 14, 0.4),
            rect(550, 280, 80, 14, -0.4),
            rect(350, 360, 80, 14, 0.35),
            rect(500, 420, 80, 14, -0.35),
            circle(400, 480, 25),
        ],
    ),
    level(
        35,
        "Long Shot",
        "A long journey with very little ink.",
        "Minimal ink — one well-placed ramp must carry the full distance.",
        240,
        (80, 80, 13),
        (720, 520, 20),
        [rect(200, 420, 140, 14), rect(500, 340, 160, 14, 0.2)],
    ),
    level(
        36,
        "Hourglass",
        "Pass through the pinched middle.",
        "The waist is narrow — funnel the ball through the pinch.",
        360,
        (400, 60, 14),
        (400, 530, 22),
        [
            rect(250, 250, 140, 14),
            rect(550, 250, 140, 14),
            rect(300, 400, 14, 120),
            rect(500, 400, 14, 120),
        ],
    ),
    level(
        37,
        "Roller Coaster",
        "Ride the series of steep ramps.",
        "Chain steep ramps for a roller-coaster descent.",
        380,
        (120, 70, 14),
        (700, 520, 22),
        [
            rect(250, 350, 140, 14, -0.4),
            rect(450, 280, 140, 14, 0.35),
            rect(620, 400, 140, 14, -0.3),
        ],
    ),
    level(
        38,
        "The Trap",
        "Enter the trap through the only opening.",
        "Three walls surround the target — find the gap and funnel in.",
        340,
        (400, 65, 14),
        (400, 500, 22),
        [
            rect(320, 380, 14, 140),
            rect(480, 380, 14, 140),
            rect(400, 320, 140, 14),
            rect(400, 440, 80, 14),
        ],
    ),
    level(
        39,
        "Floating Isles",
        "Leap across widely spaced islands.",
        "Islands are far apart — build bridges that land flush.",
        410,
        (80, 75, 14),
        (720, 490, 22),
        [
            rect(180, 450, 70, 14),
            rect(340, 360, 70, 14),
            rect(500, 270, 70, 14),
            rect(660, 380, 70, 14),
        ],
    ),
    level(
        40,
        "The Chute",
        "Drop the ball through the vertical chute.",
        "Align a chute so the ball falls straight into the target.",
        350,
        (400, 55, 14),
        (400, 520, 24),
        [rect(360, 300, 14, 200), rect(440, 300, 14, 200), rect(400, 220, 60, 14)],
    ),
    level(
        41,
        "Balance Beam",
        "Cross the thin balance beam.",
        "The beam is narrow — center your shapes or the ball falls.",
        300,
        (150, 70, 14),
        (680, 480, 20),
        [rect(420, 400, 200, 10), rect(620, 460, 100, 14)],
    ),
    level(
        42,
        "Ricochet",
        "Bank shots off the circular bumpers.",
        "Use bumper circles to redirect the ball toward the goal.",
        370,
        (100, 70, 14),
        (710, 510, 22),
        [circle(350, 280, 30), circle(550, 350, 30), rect(450, 450, 120, 14, 0.15)],
    ),
    level(
        43,
        "Fortress",
        "Breach the fortress walls.",
        "Walls guard the target — ramp over or slip through a gap.",
        330,
        (400, 60, 14),
        (680, 500, 20),
        [
            rect(500, 380, 14, 160),
            rect(620, 380, 14, 160),
            rect(560, 300, 120, 14),
            rect(680, 440, 100, 14),
        ],
    ),
    level(
        44,
        "Triple Bounce",
        "Bounce three times before the finish.",
        "Three angled slabs — each bounce must aim at the next.",
        360,
        (120, 75, 14),
        (700, 530, 22),
        [
            rect(250, 400, 120, 14, -0.45),
            rect(420, 320, 120, 14, 0.4),
            rect(580, 440, 120, 14, -0.35),
        ],
    ),
    level(
        45,
        "The Needle",
        "Thread the needle with precision.",
        "Tiny gap, tiny target — precision beats speed.",
        260,
        (400, 60, 14),
        (720, 520, 18),
        [rect(350, 350, 14, 140), rect(450, 350, 14, 140), rect(550, 420, 120, 14)],
    ),
    level(
        46,
        "Cascade",
        "Let the ball cascade down the terraces.",
        "Terraced drops — each level catches and passes the ball.",
        390,
        (680, 70, 14),
        (120, 520, 24),
        [
            rect(600, 180, 130, 14),
            rect(480, 280, 130, 14),
            rect(360, 380, 130, 14),
            rect(240, 480, 130, 14),
        ],
    ),
    level(
        47,
        "The Arch",
        "Roll under the arch and into the target.",
        "Pass under the arch — too high and you miss the goal.",
        350,
        (150, 70, 14),
        (650, 510, 22),
        [rect(400, 320, 200, 14), rect(320, 260, 14, 100), rect(480, 260, 14, 100)],
    ),
    level(
        48,
        "Switchback",
        "Climb the switchback trail.",
        "Sharp switchbacks — alternate direction on each ramp.",
        370,
        (90, 75, 14),
        (710, 490, 22),
        [
            rect(200, 480, 140, 14, 0.5),
            rect(400, 380, 140, 14, -0.5),
            rect(600, 280, 140, 14, 0.45),
        ],
    ),
    level(
        49,
        "Final Bridge",
        "One last long bridge to the tiny target.",
        "The longest gap yet — make every pixel of ink count.",
        280,
        (100, 80, 13),
        (720, 510, 18),
        [rect(200, 400, 160, 14), rect(500, 320, 14, 140), rect(650, 450, 100, 14)],
    ),
    level(
        50,
        "Gravity Master",
        "The ultimate test — prove you master gravity.",
        "Fifty levels lead here — plan, draw, drop, and deliver.",
        250,
        (400, 55, 13),
        (400, 520, 18),
        [
            circle(280, 250, 28),
            circle(520, 250, 28),
            rect(350, 380, 14, 120),
            rect(450, 380, 14, 120),
            rect(400, 300, 100, 14, 0.2),
            rect(250, 450, 100, 14, -0.3),
            rect(550, 450, 100, 14, 0.3),
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
  const sx = width / level.world_width
  const sy = height / level.world_height
  const layoutScale = Math.min(sx, sy)

  const scaleX = (n: number) => n * sx
  const scaleY = (n: number) => n * sy
  const scaleUniform = (n: number) => n * layoutScale

  return {
    ...level,
    world_width: width,
    world_height: height,
    layout_scale: layoutScale,
    ball: {
      x: scaleX(level.ball.x),
      y: scaleY(level.ball.y),
      radius: scaleUniform(level.ball.radius),
    },
    target: {
      x: scaleX(level.target.x),
      y: scaleY(level.target.y),
      radius: scaleUniform(level.target.radius),
    },
    static_bodies: level.static_bodies.map((body) => ({
      ...body,
      x: scaleX(body.x),
      y: scaleY(body.y),
      width: body.width !== undefined ? scaleX(body.width) : undefined,
      height: body.height !== undefined ? scaleY(body.height) : undefined,
      radius: body.radius !== undefined ? scaleUniform(body.radius) : undefined,
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
