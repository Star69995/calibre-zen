#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
What a search box here matches, and in what order -- one rule for both.

Preferences' search (settings.py) and Search actions (actions.py) list
different things, and a person should not have to learn two ways of finding
them. Everything they list is an `Entry`, and `rank()` is the only place a query
is compared with one. No Qt here, so the rule is tested without a window.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple

_TAGS = re.compile(r'<[^>]+>')
_SPACE = re.compile(r'\s+')

# How well a query word fits, best first. A word that only matches the
# location, the English name or the tooltip still counts, last.
TITLE_PREFIX, WORD_PREFIX, IN_TITLE, ELSEWHERE = range(4)


def plain(text: str, accelerators: bool = True) -> str:
    """
    `text` as a person reads it on screen: no HTML tags, one line, and, for a
    widget's text (`accelerators`), no accelerator ampersands -- `&&` is a
    literal ampersand and stays one. A name that is not a widget's text, such
    as a Preferences page's "Look & feel", keeps its ampersand.
    """
    text = _TAGS.sub(' ', text or '')
    if accelerators:
        text = text.replace('&&', '\0').replace('&', '').replace('\0', '&')
    return _SPACE.sub(' ', text).strip()


def fold(text: str) -> str:
    "`plain` and case-folded, without direction marks: what a query is compared with."
    return unisolated(plain(text)).casefold()


# Between a menu or page and what is inside it.
PATH_SEP = ' › '
# First-strong isolate and pop: each part of a path keeps its own direction.
FSI, PDI = '\u2068', '\u2069'
_NO_ISOLATES = {ord(c): None for c in (FSI, PDI)}


def path(parts) -> str:
    """
    Where an entry lives, outermost first: "Look & feel › Tag browser".

    Each part is isolated. A Hebrew window is full of English names (calibre's
    untranslated tabs, every plugin), and without isolation the bidi algorithm
    merges neighbouring English parts into one left-to-right run, so a Hebrew
    reader meets "Display" before "Tag browser". Isolated, the parts run in the
    window's direction and the separator, which Unicode mirrors, points the way
    they are read.
    """
    return PATH_SEP.join(FSI + p + PDI for p in parts if p)


def unisolated(text: str) -> str:
    "`text` without the isolates `path` puts in: the characters a person reads."
    return text.translate(_NO_ISOLATES)


class Entry(NamedTuple):
    title: str  # shown, the thing to find
    where: str  # shown under it: the menu or page it is in
    also: str  # matched, never shown: an English name, a tooltip
    target: Any  # what choosing it does; the caller's to interpret
    icon: Any = None  # a QIcon, or None
    shortcut: str = ''
    enabled: bool = True


def words(query: str) -> list[str]:
    return fold(query).split()


def score(entry: Entry, wanted: list[str]) -> int | None:
    """
    How well `entry` fits the query's words, lower is better, or None when one
    of them is missing. Every word has to be somewhere; the score is the worst
    of the words' fits, so "column hide" ranks by its weaker half.
    """
    title = fold(entry.title)
    rest = fold(entry.where) + ' ' + fold(entry.also)
    title_words = title.split()
    worst = TITLE_PREFIX
    for word in wanted:
        if title.startswith(word):
            fit = TITLE_PREFIX
        elif any(w.startswith(word) for w in title_words):
            fit = WORD_PREFIX
        elif word in title:
            fit = IN_TITLE
        elif word in rest:
            fit = ELSEWHERE
        else:
            return None
        worst = max(worst, fit)
    return worst


def rank(entries, query: str, limit: int = 0) -> list[Entry]:
    """
    The entries that match `query`, best first; within one fit the shorter
    title first, then the order they came in, which is the order of the menus
    or pages. An empty query matches all, in that order.
    """
    wanted = words(query)
    if not wanted:
        found = list(entries)
    else:
        scored = []
        for i, entry in enumerate(entries):
            s = score(entry, wanted)
            if s is not None:
                scored.append((s, len(entry.title), i, entry))
        scored.sort(key=lambda x: x[:3])
        found = [x[-1] for x in scored]
    return found[:limit] if limit else found
