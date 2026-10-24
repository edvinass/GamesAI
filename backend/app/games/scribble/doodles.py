"""Simple stroke doodles the AI can draw for each Scribble prompt."""

from __future__ import annotations

import math
from typing import Any

INK = "#1c1917"
RED = "#e11d48"
ORANGE = "#f97316"
YELLOW = "#eab308"
GREEN = "#16a34a"
BLUE = "#0284c7"
INDIGO = "#4f46e5"
PURPLE = "#9333ea"
BROWN = "#92400e"
PINK = "#e11d48"


def _poly(points: list[tuple[float, float]], color: str = INK, size: int = 16) -> dict[str, Any]:
    return {
        "color": color,
        "size": size,
        "points": [[int(round(x)), int(round(y))] for x, y in points],
    }


def _circle(cx: float, cy: float, r: float, color: str = INK, size: int = 16, n: int = 22) -> dict[str, Any]:
    pts = []
    for i in range(n + 1):
        angle = math.tau * i / n
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _poly(pts, color, size)


def _ellipse(
    cx: float, cy: float, rx: float, ry: float, color: str = INK, size: int = 16, n: int = 22
) -> dict[str, Any]:
    pts = []
    for i in range(n + 1):
        angle = math.tau * i / n
        pts.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return _poly(pts, color, size)


def _line(x1: float, y1: float, x2: float, y2: float, color: str = INK, size: int = 16) -> dict[str, Any]:
    return _poly([(x1, y1), (x2, y2)], color, size)


def _arc(
    cx: float,
    cy: float,
    r: float,
    a0: float,
    a1: float,
    color: str = INK,
    size: int = 16,
    n: int = 14,
) -> dict[str, Any]:
    pts = []
    for i in range(n + 1):
        angle = a0 + (a1 - a0) * i / n
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return _poly(pts, color, size)


def _tri(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], color: str = INK, size: int = 16) -> dict[str, Any]:
    return _poly([a, b, c, a], color, size)


def _rect(x: float, y: float, w: float, h: float, color: str = INK, size: int = 16) -> dict[str, Any]:
    return _poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], color, size)


def _cat() -> list[dict]:
    return [
        _circle(500, 400, 150, size=18),
        _tri((370, 280), (430, 160), (490, 290)),
        _tri((630, 290), (690, 160), (750, 280)),
        _circle(450, 380, 16, INK, 10),
        _circle(560, 380, 16, INK, 10),
        _tri((500, 410), (480, 450), (520, 450), INK, 10),
        _line(340, 430, 230, 400, size=10),
        _line(340, 450, 230, 470, size=10),
        _line(660, 430, 770, 400, size=10),
        _line(660, 450, 770, 470, size=10),
    ]


def _sun() -> list[dict]:
    strokes = [_circle(500, 340, 120, ORANGE, 20)]
    for i in range(8):
        angle = math.tau * i / 8
        strokes.append(
            _line(
                500 + 150 * math.cos(angle),
                340 + 150 * math.sin(angle),
                500 + 230 * math.cos(angle),
                340 + 230 * math.sin(angle),
                YELLOW,
                18,
            )
        )
    return strokes


def _house() -> list[dict]:
    return [
        _rect(300, 320, 400, 280, BROWN, 18),
        _tri((270, 330), (500, 140), (730, 330), RED, 18),
        _rect(450, 430, 100, 170, INK, 14),
        _rect(340, 380, 80, 70, BLUE, 12),
        _rect(580, 380, 80, 70, BLUE, 12),
    ]


def _tree() -> list[dict]:
    return [
        _rect(455, 400, 90, 220, BROWN, 16),
        _circle(500, 280, 170, GREEN, 20),
        _circle(390, 340, 90, GREEN, 16),
        _circle(620, 340, 90, GREEN, 16),
    ]


def _car() -> list[dict]:
    return [
        _poly([(180, 430), (280, 320), (680, 320), (780, 430), (780, 500), (180, 500), (180, 430)], BLUE, 18),
        _rect(300, 340, 140, 80, INDIGO, 12),
        _rect(500, 340, 150, 80, INDIGO, 12),
        _circle(300, 520, 55, INK, 18),
        _circle(680, 520, 55, INK, 18),
        _circle(300, 520, 22, YELLOW, 10),
        _circle(680, 520, 22, YELLOW, 10),
    ]


def _fish() -> list[dict]:
    return [
        _ellipse(470, 360, 180, 100, BLUE, 18),
        _tri((640, 360), (800, 260), (800, 460), BLUE, 16),
        _circle(380, 340, 14, INK, 10),
        _arc(430, 400, 40, 0.2, 2.2, INK, 10),
    ]


def _star() -> list[dict]:
    cx, cy, outer, inner = 500, 350, 200, 80
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    pts.append(pts[0])
    return [_poly(pts, YELLOW, 18)]


def _heart() -> list[dict]:
    pts = []
    for i in range(32):
        t = math.tau * i / 32
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((500 + x * 16, 360 - y * 16))
    pts.append(pts[0])
    return [_poly(pts, RED, 18)]


def _book() -> list[dict]:
    return [
        _rect(250, 180, 500, 360, BROWN, 18),
        _line(500, 180, 500, 540, INK, 14),
        _line(310, 250, 460, 250, INK, 8),
        _line(310, 300, 460, 300, INK, 8),
        _line(310, 350, 440, 350, INK, 8),
        _line(540, 250, 690, 250, INK, 8),
        _line(540, 300, 690, 300, INK, 8),
    ]


def _moon() -> list[dict]:
    return [
        _circle(480, 350, 160, YELLOW, 18),
        _circle(560, 300, 130, "#f6f1e7", 28),
    ]


def _cake() -> list[dict]:
    return [
        _rect(280, 340, 440, 200, PINK, 18),
        _poly([(280, 340), (320, 280), (400, 340), (480, 280), (560, 340), (640, 280), (720, 340)], PINK, 16),
        _line(430, 280, 430, 180, BROWN, 10),
        _line(570, 280, 570, 180, BROWN, 10),
        _circle(430, 165, 18, ORANGE, 12),
        _circle(570, 165, 18, ORANGE, 12),
    ]


def _boat() -> list[dict]:
    return [
        _poly([(220, 400), (780, 400), (680, 500), (320, 500), (220, 400)], BROWN, 18),
        _line(500, 400, 500, 160, INK, 14),
        _tri((500, 180), (500, 380), (700, 380), RED, 16),
        _arc(500, 540, 280, 0.15, math.pi - 0.15, BLUE, 14, 18),
    ]


def _hat() -> list[dict]:
    return [
        _ellipse(500, 430, 260, 50, INK, 18),
        _poly([(360, 420), (400, 180), (600, 180), (640, 420)], PURPLE, 18),
        _rect(390, 170, 220, 36, RED, 14),
    ]


def _key() -> list[dict]:
    return [
        _circle(340, 320, 90, YELLOW, 18),
        _circle(340, 320, 36, "#f6f1e7", 16),
        _line(420, 360, 760, 520, YELLOW, 18),
        _line(680, 480, 720, 430, YELLOW, 16),
        _line(740, 510, 790, 460, YELLOW, 16),
    ]


def _cloud() -> list[dict]:
    return [
        _circle(400, 380, 90, BLUE, 16),
        _circle(500, 320, 120, BLUE, 18),
        _circle(620, 370, 100, BLUE, 16),
        _ellipse(500, 420, 220, 70, BLUE, 16),
    ]


def _cup() -> list[dict]:
    return [
        _poly([(340, 200), (400, 520), (640, 520), (700, 200)], BROWN, 18),
        _arc(730, 340, 70, -1.2, 1.2, BROWN, 16, 12),
        _ellipse(520, 200, 180, 36, BROWN, 14),
    ]


def _flower() -> list[dict]:
    strokes = []
    for i in range(6):
        angle = math.tau * i / 6
        strokes.append(_circle(500 + 110 * math.cos(angle), 300 + 110 * math.sin(angle), 70, PINK, 14))
    strokes.append(_circle(500, 300, 48, YELLOW, 14))
    strokes.append(_line(500, 370, 500, 600, GREEN, 16))
    strokes.append(_poly([(500, 460), (620, 400), (540, 480)], GREEN, 12))
    return strokes


def _snowman() -> list[dict]:
    return [
        _circle(500, 500, 120, INK, 16),
        _circle(500, 330, 90, INK, 16),
        _circle(500, 200, 64, INK, 16),
        _circle(476, 190, 8, INK, 8),
        _circle(524, 190, 8, INK, 8),
        _tri((500, 210), (560, 220), (500, 230), ORANGE, 10),
        _line(390, 330, 280, 280, BROWN, 12),
        _line(610, 330, 720, 280, BROWN, 12),
        _rect(450, 110, 100, 30, INK, 12),
        _rect(470, 60, 60, 50, INK, 12),
    ]


def _pizza() -> list[dict]:
    return [
        _tri((220, 560), (780, 560), (500, 140), ORANGE, 18),
        _line(500, 140, 500, 560, YELLOW, 12),
        _circle(430, 360, 28, RED, 12),
        _circle(560, 400, 28, RED, 12),
        _circle(480, 470, 24, RED, 12),
        _circle(560, 260, 22, GREEN, 10),
    ]


def _guitar() -> list[dict]:
    return [
        _ellipse(420, 460, 130, 160, BROWN, 18),
        _circle(420, 470, 40, INK, 12),
        _poly([(500, 340), (560, 300), (700, 120), (760, 160), (600, 360)], BROWN, 16),
        _line(640, 250, 720, 200, INK, 8),
        _line(670, 280, 740, 230, INK, 8),
    ]


def _clock() -> list[dict]:
    return [
        _circle(500, 350, 180, INK, 18),
        _line(500, 350, 500, 220, INK, 12),
        _line(500, 350, 640, 390, RED, 12),
        _circle(500, 350, 12, RED, 10),
    ]


def _apple() -> list[dict]:
    return [
        _circle(500, 400, 160, RED, 20),
        _line(500, 250, 520, 150, BROWN, 12),
        _poly([(520, 170), (620, 140), (560, 220)], GREEN, 12),
    ]


def _balloon() -> list[dict]:
    return [
        _ellipse(500, 260, 120, 150, RED, 18),
        _tri((500, 400), (470, 450), (530, 450), RED, 12),
        _poly([(500, 450), (470, 520), (530, 560), (480, 620)], INK, 10),
    ]


def _mountain() -> list[dict]:
    return [
        _tri((80, 560), (360, 160), (640, 560), INK, 18),
        _tri((360, 560), (680, 200), (960, 560), BLUE, 18),
        _tri((360, 160), (420, 250), (300, 250), "#f6f1e7", 14),
    ]


def _bird() -> list[dict]:
    return [
        _ellipse(460, 380, 140, 70, BLUE, 16),
        _circle(600, 340, 50, BLUE, 14),
        _tri((640, 340), (720, 330), (640, 360), ORANGE, 12),
        _tri((400, 340), (300, 220), (430, 360), INDIGO, 14),
        _line(400, 440, 380, 520, INK, 10),
        _line(460, 450, 470, 530, INK, 10),
    ]


def _snake() -> list[dict]:
    pts = []
    for i in range(28):
        t = i / 27
        pts.append((160 + t * 680, 360 + math.sin(t * math.tau * 2) * 80))
    return [
        _poly(pts, GREEN, 28),
        _circle(150, 360, 28, GREEN, 14),
        _circle(140, 350, 6, INK, 8),
        _line(120, 340, 80, 310, RED, 8),
    ]


def _rocket() -> list[dict]:
    return [
        _poly([(500, 80), (600, 280), (600, 480), (400, 480), (400, 280), (500, 80)], BLUE, 18),
        _circle(500, 300, 36, YELLOW, 12),
        _tri((400, 420), (320, 540), (430, 480), RED, 14),
        _tri((600, 420), (680, 540), (570, 480), RED, 14),
        _tri((450, 480), (500, 620), (550, 480), ORANGE, 14),
    ]


def _crown() -> list[dict]:
    return [
        _poly(
            [(220, 460), (260, 220), (380, 360), (500, 160), (620, 360), (740, 220), (780, 460), (220, 460)],
            YELLOW,
            18,
        ),
        _circle(380, 300, 18, RED, 10),
        _circle(500, 220, 18, RED, 10),
        _circle(620, 300, 18, RED, 10),
    ]


def _umbrella() -> list[dict]:
    return [
        _arc(500, 340, 220, math.pi, math.tau, RED, 18, 18),
        _line(280, 340, 720, 340, RED, 16),
        _line(500, 340, 500, 560, INK, 14),
        _arc(500, 540, 50, 0, math.pi, INK, 14, 10),
    ]


def _castle() -> list[dict]:
    return [
        _rect(220, 320, 560, 280, INK, 16),
        _rect(180, 180, 140, 420, BROWN, 16),
        _rect(680, 180, 140, 420, BROWN, 16),
        _rect(430, 140, 140, 180, BROWN, 16),
        _poly([(180, 180), (210, 120), (250, 180), (290, 120), (320, 180)], BROWN, 12),
        _poly([(680, 180), (710, 120), (750, 180), (790, 120), (820, 180)], BROWN, 12),
        _rect(450, 430, 100, 170, INDIGO, 14),
        _line(500, 140, 500, 70, INK, 8),
        _tri((500, 70), (560, 100), (500, 110), RED, 10),
    ]


def _spider() -> list[dict]:
    strokes = [_circle(500, 360, 70, INK, 16), _circle(500, 250, 40, INK, 14)]
    for side in (-1, 1):
        for i, dy in enumerate((-80, -20, 40, 100)):
            strokes.append(_line(500, 360, 500 + side * (180 + i * 20), 360 + dy, INK, 10))
    return strokes


def _volcano() -> list[dict]:
    return [
        _tri((120, 580), (500, 180), (880, 580), BROWN, 18),
        _poly([(430, 250), (470, 160), (530, 160), (570, 250)], INK, 14),
        _poly([(470, 170), (500, 60), (540, 180)], ORANGE, 16),
        _circle(500, 90, 30, RED, 12),
        _circle(560, 70, 22, ORANGE, 10),
    ]


def _bicycle() -> list[dict]:
    return [
        _circle(280, 460, 110, INK, 16),
        _circle(720, 460, 110, INK, 16),
        _poly([(280, 460), (460, 460), (560, 280), (420, 280), (280, 460)], INK, 12),
        _line(560, 280, 720, 460, INK, 12),
        _line(420, 280, 360, 220, INK, 12),
        _line(320, 220, 400, 220, INK, 12),
        _line(460, 460, 460, 380, INK, 10),
    ]


def _penguin() -> list[dict]:
    return [
        _ellipse(500, 400, 130, 190, INK, 18),
        _ellipse(500, 430, 70, 120, "#f6f1e7", 16),
        _circle(460, 300, 12, "#f6f1e7", 8),
        _circle(540, 300, 12, "#f6f1e7", 8),
        _tri((500, 330), (540, 350), (500, 360), ORANGE, 12),
        _ellipse(360, 430, 40, 70, INK, 12),
        _ellipse(640, 430, 40, 70, INK, 12),
        _tri((450, 580), (500, 620), (480, 560), ORANGE, 10),
        _tri((550, 580), (500, 620), (520, 560), ORANGE, 10),
    ]


def _lighthouse() -> list[dict]:
    return [
        _poly([(420, 560), (460, 180), (540, 180), (580, 560), (420, 560)], "#f6f1e7", 18),
        _rect(450, 260, 100, 40, RED, 14),
        _rect(445, 360, 110, 40, RED, 14),
        _rect(440, 460, 120, 40, RED, 14),
        _rect(430, 150, 140, 40, INK, 12),
        _line(500, 150, 500, 70, YELLOW, 10),
        _line(500, 90, 680, 40, YELLOW, 10),
        _line(500, 110, 700, 130, YELLOW, 10),
    ]


def _dragon() -> list[dict]:
    return [
        _ellipse(460, 400, 180, 80, GREEN, 18),
        _poly([(600, 360), (760, 280), (740, 360), (820, 340), (700, 420)], GREEN, 14),
        _tri((300, 360), (180, 200), (340, 340), GREEN, 14),
        _tri((360, 340), (300, 160), (420, 330), GREEN, 14),
        _circle(250, 390, 40, GREEN, 12),
        _circle(240, 380, 8, INK, 8),
        _poly([(220, 400), (140, 430), (200, 450)], ORANGE, 12),
        _line(420, 470, 400, 560, BROWN, 12),
        _line(520, 470, 540, 560, BROWN, 12),
        _poly([(180, 380), (120, 340), (160, 400)], RED, 12),
    ]


DOODLES = {
    "cat": _cat,
    "sun": _sun,
    "house": _house,
    "tree": _tree,
    "car": _car,
    "fish": _fish,
    "star": _star,
    "heart": _heart,
    "book": _book,
    "moon": _moon,
    "cake": _cake,
    "boat": _boat,
    "hat": _hat,
    "key": _key,
    "cloud": _cloud,
    "cup": _cup,
    "flower": _flower,
    "snowman": _snowman,
    "pizza": _pizza,
    "guitar": _guitar,
    "clock": _clock,
    "apple": _apple,
    "balloon": _balloon,
    "mountain": _mountain,
    "bird": _bird,
    "snake": _snake,
    "rocket": _rocket,
    "crown": _crown,
    "umbrella": _umbrella,
    "castle": _castle,
    "spider": _spider,
    "volcano": _volcano,
    "bicycle": _bicycle,
    "penguin": _penguin,
    "lighthouse": _lighthouse,
    "dragon": _dragon,
}


def doodle_for(word: str) -> list[dict[str, Any]]:
    builder = DOODLES.get(word)
    if not builder:
        return [_circle(500, 340, 80, INK, 16), _line(430, 300, 470, 340, INK, 12), _line(560, 300, 520, 340, INK, 12)]
    return builder()
