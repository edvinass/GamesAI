"""Word list and trie used to check and search Scrabble plays."""

from __future__ import annotations

from pathlib import Path

_WORDS: set[str] | None = None
_TRIE: dict | None = None

# lexicon.txt is the ENABLE list, which predates several two-letter words that
# every current official list accepts. Add them (and their plurals) here.
_SUPPLEMENT = (
    "DA", "EW", "FE", "GI", "GIS", "KI", "KIS", "OI", "OK", "PO", "POS",
    "QI", "QIS", "TE", "TES", "ZA", "ZAS",
)


class TrieNode:
    __slots__ = ("children", "end")

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.end = False


def _load_words() -> set[str]:
    path = Path(__file__).with_name("lexicon.txt")
    words: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            word = line.strip().upper()
            if 2 <= len(word) <= 15 and word.isalpha():
                words.add(word)
    if not words:
        raise RuntimeError("Scrabble lexicon is empty")
    words.update(_SUPPLEMENT)
    return words


def words() -> set[str]:
    global _WORDS
    if _WORDS is None:
        _WORDS = _load_words()
    return _WORDS


def is_word(text: str) -> bool:
    return text in words()


def trie() -> TrieNode:
    global _TRIE
    if _TRIE is None:
        root = TrieNode()
        for word in words():
            node = root
            for letter in word:
                child = node.children.get(letter)
                if child is None:
                    child = TrieNode()
                    node.children[letter] = child
                node = child
            node.end = True
        _TRIE = root
    return _TRIE
