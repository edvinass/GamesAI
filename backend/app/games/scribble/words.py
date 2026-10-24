"""Drawable prompts for Scribble. Every word has a matching doodle."""

from __future__ import annotations

WORDS: list[dict[str, str]] = [
    {"text": "cat", "difficulty": "easy"},
    {"text": "sun", "difficulty": "easy"},
    {"text": "house", "difficulty": "easy"},
    {"text": "tree", "difficulty": "easy"},
    {"text": "car", "difficulty": "easy"},
    {"text": "fish", "difficulty": "easy"},
    {"text": "star", "difficulty": "easy"},
    {"text": "heart", "difficulty": "easy"},
    {"text": "book", "difficulty": "easy"},
    {"text": "moon", "difficulty": "easy"},
    {"text": "cake", "difficulty": "easy"},
    {"text": "boat", "difficulty": "easy"},
    {"text": "hat", "difficulty": "easy"},
    {"text": "key", "difficulty": "easy"},
    {"text": "cloud", "difficulty": "easy"},
    {"text": "cup", "difficulty": "easy"},
    {"text": "flower", "difficulty": "medium"},
    {"text": "snowman", "difficulty": "medium"},
    {"text": "pizza", "difficulty": "medium"},
    {"text": "guitar", "difficulty": "medium"},
    {"text": "clock", "difficulty": "medium"},
    {"text": "apple", "difficulty": "medium"},
    {"text": "balloon", "difficulty": "medium"},
    {"text": "mountain", "difficulty": "medium"},
    {"text": "bird", "difficulty": "medium"},
    {"text": "snake", "difficulty": "medium"},
    {"text": "rocket", "difficulty": "medium"},
    {"text": "crown", "difficulty": "medium"},
    {"text": "umbrella", "difficulty": "medium"},
    {"text": "castle", "difficulty": "hard"},
    {"text": "spider", "difficulty": "hard"},
    {"text": "volcano", "difficulty": "hard"},
    {"text": "bicycle", "difficulty": "hard"},
    {"text": "penguin", "difficulty": "hard"},
    {"text": "lighthouse", "difficulty": "hard"},
    {"text": "dragon", "difficulty": "hard"},
]

POINTS = {"easy": 100, "medium": 200, "hard": 300}

WORD_BY_TEXT = {word["text"]: word for word in WORDS}
