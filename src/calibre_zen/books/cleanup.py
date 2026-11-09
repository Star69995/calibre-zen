#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""Tree-level cleanup for XHTML that came out of a PDF conversion.

Pure lxml, no calibre or Qt imports, so the rules can be tested on their own.
Works on one parsed XHTML document (namespaced elements) at a time; ``epub.py``
feeds it the spine files of an epub.

What it fixes: empty paragraphs and decorative ornament images (the blank
pages around chapter headings), chapter headings that are plain/inline text,
paragraphs broken in the middle of a sentence, spaces around punctuation and
dashes. Every text edit goes through ``_apply`` which only inserts or deletes
characters, so inline markup survives and no words can be lost.
"""
import re
from collections import Counter

from lxml import etree

XHTML = 'http://www.w3.org/1999/xhtml'


def _q(tag):
    return '{%s}%s' % (XHTML, tag)


P, DIV, IMG, BR, H2, BODY, HEAD, TITLE = (
    _q(t) for t in ('p', 'div', 'img', 'br', 'h2', 'body', 'head', 'title'))
HEADINGS = {_q('h%d' % i) for i in range(1, 7)}
# Anything in an otherwise empty paragraph that makes it worth keeping.
CONTENT_TAGS = {IMG, _q('svg'), _q('object'), _q('hr'), _q('table'), _q('audio'),
                _q('video')}
SKIP_TEXT = {_q('pre'), _q('code'), _q('script'), _q('style')}

WS = '[ \t\r\n\f]+'
OPEN_QUOTES = '“"‘'

_ONES = 'One|Two|Three|Four|Five|Six|Seven|Eight|Nine'
_NUM = (r'(?:\d{1,3}|[IVXLC]{1,6}|(?:%s|Ten|Eleven|Twelve|Thirteen|Fourteen|Fifteen|'
        r'Sixteen|Seventeen|Eighteen|Nineteen|(?:Twenty|Thirty|Forty|Fifty|Sixty)'
        r'(?:[- ](?:%s))?))' % (_ONES, _ONES))
HEADING_RE = re.compile(r'^(?:Chapter\s+%s(?:\s*[:.\-–—]\s*.{1,60})?|Prologue|Epilogue)$'
                        % _NUM, re.I)
# "...timing.” Chapter Eight" glued to the end of the previous paragraph.
HEADING_TAIL_RE = re.compile(r'(?<=[.!?…”"’)])\s+(Chapter\s+%s)\s*$' % _NUM, re.I)
# A heading glued to the end of a paragraph with no stop before it ("... Do’Urden Chapter 1"),
# and one glued to the start of the next ("CHAPTER 5 Come on, ..."): neither may be merged.
HEADING_END_RE = re.compile(r'(?:^|\s)(?:Chapter\s+%s|Prologue|Epilogue|Dedication|'
                            r'Acknowledg(?:e)?ments|About the Author)\s*$' % _NUM, re.I)
HEADING_START_RE = re.compile(r'(?:Chapter\s+%s|Prologue|Epilogue|Dedication|'
                              r'Acknowledg(?:e)?ments|About the Author)\b' % _NUM, re.I)
SMALL_WORDS = {'a', 'an', 'the', 'of', 'and', 'in', 'on', 'to', 'for', 'at', 'or', 'but'}
PAGE_BREAK = 'page-break-before: always'


class Options:
    """Per-book settings, computed by ``epub.py`` before the first file."""

    def __init__(self, dash_style='tight', latin=True, heading_class=None,
                 is_ornament=None, remove_ornaments=False, hyphen_dash=False):
        self.dash_style = dash_style          # 'tight' (a—b) or 'spaced' (a — b)
        self.hyphen_dash = hyphen_dash        # the book writes its dashes as a lone "-"
        self.latin = latin                    # Latin-script text: case-based rules on
        self.heading_class = heading_class    # class copied onto headings we create
        # True for a tiny decorative image. Such images are kept unless
        # remove_ornaments is set: they are part of the book's design.
        self.is_ornament = is_ornament or (lambda src: False)
        self.remove_ornaments = remove_ornaments


class Stats:
    """Counts per rule plus a few before/after samples for the report."""

    def __init__(self):
        self.counts = Counter()
        self.samples = {}
        self.removed_images = set()

    def add(self, rule, before=None, after=None, n=1):
        self.counts[rule] += n
        if before is not None:
            s = self.samples.setdefault(rule, [])
            if len(s) < 5:
                s.append((before, after))

    def update(self, other):
        self.counts.update(other.counts)
        for rule, items in other.samples.items():
            s = self.samples.setdefault(rule, [])
            s.extend(items[:max(0, 5 - len(s))])
        self.removed_images |= other.removed_images


# --- text slots ------------------------------------------------------------

def _slots(el):
    """All text positions inside el in document order: (node, 'text'|'tail')."""
    out = [(el, 'text')]

    def walk(node):
        for c in node:
            if isinstance(c.tag, str):
                out.append((c, 'text'))
                walk(c)
            out.append((c, 'tail'))
    walk(el)
    return out


def _get(slot):
    return getattr(slot[0], slot[1]) or ''


def _set(slot, value):
    setattr(slot[0], slot[1], value or None)


def _apply(slots, edits):
    """Apply (start, end, new) edits, given on the concatenated slot text.

    Insertions go after the character before them; deletions cut each slot
    they overlap. Edits are applied back to front so positions stay valid.
    """
    for a, b, new in sorted(edits, reverse=True):
        texts = [_get(s) for s in slots]
        pos = 0
        done = not new
        for slot, t in zip(slots, texts):
            lo, hi = pos, pos + len(t)
            pos = hi
            if b > a and lo < b and hi > a:        # overlaps the deleted span
                s, e = max(a, lo) - lo, min(b, hi) - lo
                t = t[:s] + (new if not done else '') + t[e:]
                done = True
                _set(slot, t)
            elif b == a and new and not done and lo < a <= hi:   # pure insertion
                t = t[:a - lo] + new + t[a - lo:]
                done = True
                _set(slot, t)
        if not done and slots:                    # insertion at 0
            _set(slots[0], new + _get(slots[0]))


def _text(el):
    return ''.join(el.itertext())


def _has_alnum(s):
    return any(c.isalnum() for c in s)


# --- per-paragraph text rules ----------------------------------------------

def _del_spaces(m, S):
    return [(m.start(), m.end(), '')]


def _ins_after(m, S):
    return [(m.end(), m.end(), ' ')]


def _ins_before(m, S):
    return [(m.start(), m.start(), ' ')]


def _hyphen_space(m, S):
    if re.match(r'(?:and|or|to|nor)\b', S[m.end():m.end() + 4]):
        return []          # "pre- and post-war" keeps its space
    return [(m.start(), m.end(), '')]


def _to_emdash(m, S):
    return [(m.start(), m.end(), '—')]


def _move_space(m, S):
    "'word ,next' -> 'word, next': one edit, so the report shows the real result."
    return [(m.start(), m.end(), m.group(1) + ' ')]


def _always(opts):
    return True


def _latin(opts):
    return opts.latin


def _latin_hyphen_breaks(opts):
    "Not in a book that writes its dashes as '-': there 'smile- yes' is no split word."
    return opts.latin and not opts.hyphen_dash


# A “ glued to the word before it ("were-“ the") closes a quote the converter
# set the wrong way round: the space after it is a real one.
_OPENING_QUOTE = r'(?<=(?<![^\s—(\[“‘])“)'

# (name, regex, edit function, applies to these Options)
TEXT_RULES = [
    ('ascii dash -> em dash', re.compile(r'(?<!-)-{2,3}(?!-)'), _to_emdash, _always),
    ('spaced hyphen -> em dash',
     re.compile(r'(?<=[A-Za-z”’.!?,]) - (?=[A-Za-z“‘])'), _to_emdash, _always),
    ('space before , ; ! ? stuck to the next word',
     re.compile(r'(?<=[A-Za-z0-9”’)])[ ]+([,;!?])(?=[A-Za-z“‘(])'), _move_space, _always),
    # a , ; : after a sentence end is a misread quote mark: not ours to fix
    ('space before , ; : ! ?',
     re.compile(r'(?:(?<=[^\s.!?])[ ]+(?=[,;:!?])|(?<=[.!?])[ ]+(?=[!?]))'), _del_spaces, _always),
    # not " .04": that period is a decimal point
    ('space before period', re.compile(r'(?<=[^\s.,;:])[ ]+(?=\.(?![ ]*\.|\d))'),
     _del_spaces, _always),
    ('space before closing quote/paren', re.compile(r'(?<=\S)[ ]+(?=[”)])'),
     _del_spaces, _always),
    ('space after opening quote/paren', re.compile(r'(?:%s|(?<=\())[ ]+(?=\S)' % _OPENING_QUOTE),
     _del_spaces, _always),
    ('missing space after , ; ! ?', re.compile(r'(?<=[A-Za-z])[,;!?](?=[A-Za-z“‘(])'),
     _ins_after, _always),
    ('missing space after period',
     re.compile(r'(?<=[a-z]{2})\.(?=[A-Z](?:[a-z]|\b))'), _ins_after, _latin),
    ('missing space after colon', re.compile(r'(?<=[A-Za-z]):(?=[A-Za-z])'),
     _ins_after, _always),
    ('missing space after closing quote', re.compile(r'(?<=[.!?,]”)(?=[A-Za-z])'),
     _ins_before, _always),
    ('missing space before opening quote', re.compile(r'(?<=[.!?,;:])(?=[“‘])'),
     _ins_before, _always),
    ('broken hyphenated word', re.compile(r'(?<=[a-z]-)[ ]+(?=[a-z])'),
     _hyphen_space, _latin_hyphen_breaks),
]
DASH_RULES = {
    'tight': [
        ('space around em dash', re.compile(r'[ ]+(?=—)'), _del_spaces),
        ('space around em dash', re.compile(r'(?<=—)[ ]+'), _del_spaces),
    ],
    'spaced': [
        ('missing space around em dash', re.compile(r'(?<=[^\s“‘(\[—])(?=—)'),
         _ins_before),
        ('missing space around em dash', re.compile(r'(?<=—)(?=[^\s”’)\],.!?;:—])'),
         _ins_before),
    ],
}


def _normalize_ws(slots):
    """Collapse whitespace runs (also across inline element boundaries)."""
    prev_space = True
    for slot in slots:
        if slot[1] == 'tail' and slot[0].tag == BR:
            prev_space = True
        t = _get(slot)
        if not t:
            continue
        new = re.sub(WS, ' ', t)
        if prev_space and new.startswith(' '):
            new = new[1:]
        if new != t:
            _set(slot, new)
        if new:
            prev_space = new.endswith(' ')
    for slot in reversed(slots):
        t = _get(slot)
        if not t:
            continue
        if t.rstrip(' ') != t:
            _set(slot, t.rstrip(' '))
        if t.rstrip(' '):
            break


def fix_text(el, opts, stats):
    """Whitespace/punctuation rules for one block element (p or heading)."""
    slots = _slots(el)
    _normalize_ws(slots)
    S = ''.join(_get(s) for s in slots)
    if not _has_alnum(S):       # scene breaks like "* * *"
        return
    rules = [(n, rx, fn) for n, rx, fn, applies in TEXT_RULES if applies(opts)]
    rules.extend(DASH_RULES[opts.dash_style])
    for name, rx, fn in rules:
        S = ''.join(_get(s) for s in slots)
        edits = []
        for m in rx.finditer(S):
            es = fn(m, S)
            if es:
                a, b, new = es[0]
                lo, hi = max(0, a - 15), min(len(S), b + 15)
                stats.add(name, S[lo:hi], S[lo:a] + new + S[b:hi])
                edits.extend(es)
        if edits:
            _apply(slots, edits)
    _normalize_ws(slots)       # never leave a double space behind


# --- structure ---------------------------------------------------------------

def _remove(el):
    """Remove el but keep the text that follows it."""
    parent, tail = el.getparent(), el.tail
    if tail and tail.strip():
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or '') + tail
        else:
            parent.text = (parent.text or '') + tail
    parent.remove(el)


def _is_empty(el):
    if _text(el).strip() or el.get('id') or el.get('name'):
        return False
    return not any(d.tag in CONTENT_TAGS for d in el.iterdescendants())


def _sole_image(el):
    """src of the image if el is a block that holds nothing but one image."""
    if el.tag == IMG:
        return el.get('src')
    if el.tag == P and not _text(el).strip() and not el.get('id'):
        imgs = [d for d in el.iterdescendants() if d.tag in CONTENT_TAGS]
        if len(imgs) == 1 and imgs[0].tag == IMG:
            return imgs[0].get('src')
    return None


def remove_blank_blocks(container, opts, stats):
    """Drop empty paragraphs and empty page-break divs (and, only when asked
    for, ornament images)."""
    for el in list(container):
        if not isinstance(el.tag, str):
            continue
        src = _sole_image(el)
        if src is not None:
            if opts.remove_ornaments and opts.is_ornament(src):
                stats.removed_images.add(src)
                stats.add('ornament image', n=1)
                _remove(el)
            continue
        if el.tag == P and _is_empty(el):
            stats.add('empty paragraph')
            _remove(el)
        elif (el.tag == DIV and len(el) == 0 and not _text(el).strip()
              and re.match(r'^calibre_pb_\d+$', el.get('id') or '')):
            stats.add('empty page-break div')
            _remove(el)


def _make_heading(el, opts, text=None):
    el.tag = H2
    for k in list(el.attrib):
        if k != 'id':
            del el.attrib[k]
    if opts.heading_class:
        el.set('class', opts.heading_class)
    if text is not None:
        for c in list(el):
            el.remove(c)
        el.text = text


def detect_headings(body, opts, stats):
    for p in list(body.iter(P)):
        if len(p):          # only plain-text paragraphs
            continue
        text = re.sub(WS, ' ', p.text or '').strip()
        if text and HEADING_RE.match(text) and len(text) <= 70:
            _make_heading(p, opts, text)
            stats.add('chapter heading recognised', text, '<h2>' + text)
            continue
        m = HEADING_TAIL_RE.search(p.text or '')
        if m:
            heading = etree.Element(H2)
            if opts.heading_class:
                heading.set('class', opts.heading_class)
            heading.text = re.sub(WS, ' ', m.group(1))
            before = (p.text or '')
            p.text = before[:m.start()].rstrip()
            tail = p.tail
            p.addnext(heading)
            p.tail = tail
            stats.add('chapter heading split from paragraph', before[-40:],
                      p.text[-25:] + ' | <h2>' + heading.text)


def _title_like(text):
    words = text.split()
    if not 1 <= len(words) <= 6 or len(text) > 40:
        return False
    if not re.match(r"^[A-Za-z' ]+$", text):
        return False
    return all(w[0].isupper() or w.lower() in SMALL_WORDS for w in words)


def promote_first_title(body, opts, stats):
    """A short Title Case first line in a file with no heading becomes <h2>."""
    if not opts.latin or any(True for _ in body.iter(*HEADINGS)):
        return
    for el in body:
        if not isinstance(el.tag, str) or el.tag != P:
            continue
        text = re.sub(WS, ' ', _text(el)).strip()
        if not text:            # an ornament image paragraph before the title
            continue
        nxt = el.getnext()
        if (_title_like(text) and nxt is not None and nxt.tag == P
                and len(_text(nxt).strip()) >= 60 and not len(el)):
            _make_heading(el, opts, text)
            stats.add('first line promoted to heading', text, '<h2>' + text)
        return


def _should_merge_simple(pt, nt):
    last = pt[-1]
    if nt[0].islower() or last in ',;':
        return True
    return last.isalnum() and len(pt) >= 30 and nt[0] not in OPEN_QUOTES


def _join(prev, nxt):
    slots = _slots(prev)
    _normalize_ws(slots)
    last = prev[-1] if len(prev) else None
    text = (nxt.text or '').lstrip()
    if last is None:
        prev.text = (prev.text or '') + ' ' + text
    else:
        last.tail = (last.tail or '') + ' ' + text
    for c in list(nxt):
        prev.append(c)
    _remove(nxt)


def merge_broken_paragraphs(container, opts, stats):
    """Join paragraphs that the PDF page/line layout cut in the middle."""
    if not opts.latin:
        return
    prev = None
    for el in list(container):
        if el.getparent() is not container:      # already joined into prev
            continue
        if el.tag != P:
            prev = None
            continue
        if prev is None or el.getprevious() is not prev:
            prev = el
            continue
        pt, nt = _text(prev).rstrip(), _text(el).lstrip()
        if (not pt or not nt or not _has_alnum(pt) or not _has_alnum(nt)
                or HEADING_END_RE.search(pt) or HEADING_START_RE.match(nt)):
            prev = el
            continue
        if _should_merge_simple(pt, nt):
            nodes, reason = [el], 'paragraph broken mid-sentence'
        else:
            nodes, reason = _open_quote_chain(pt, el), 'paragraph broken inside a quote'
        if not nodes:
            prev = el
            continue
        stats.add(reason, pt[-35:] + ' ¶ ' + nt[:35], pt[-35:] + ' ' + nt[:35])
        for node in nodes:
            _join(prev, node)


def _opens(s):
    return s.count('“') - s.count('”')


def _open_quote_chain(pt, el):
    """Paragraphs to join if they continue (and close) a quote pt left open.

    Only accepted when the quote really closes within 4 paragraphs, so a stray
    unmatched quote mark can't swallow the rest of the chapter."""
    if _opens(pt) <= 0:
        return None
    chain, acc, node = [], pt, el
    while node is not None and node.tag == P and len(chain) < 4:
        nt = _text(node).lstrip()
        if not nt or nt[0] in OPEN_QUOTES:
            return None
        chain.append(node)
        acc += ' ' + nt
        if _opens(acc) <= 0:
            return chain
        node = node.getnext()
    return None


def _visible_before(h, body, opts):
    """True if something visible (text or a non-ornament image) comes before h
    in the document. Empty blocks and ornament images don't count: they sit
    on the same page as the heading in the original layout."""
    node = h
    while node is not None and node is not body:
        for prev in node.itersiblings(preceding=True):
            if not isinstance(prev.tag, str):
                continue
            if _text(prev).strip():
                return True
            src = _sole_image(prev)
            if src is not None:
                if not opts.is_ornament(src):
                    return True
            elif prev.tag in CONTENT_TAGS or any(
                    d.tag in CONTENT_TAGS for d in prev.iterdescendants()):
                return True
        node = node.getparent()
    return False


def _is_ornament_block(el, opts):
    src = _sole_image(el)
    return (isinstance(el.tag, str) and src is not None and not _text(el).strip()
            and opts.is_ornament(src))


def style_headings(body, opts):
    """Page break before headings that follow visible content in their file
    (some readers add a blank page when the very first element asks for one).
    Ornament images right above a heading belong with it, so the break goes
    before them."""
    for h in body.iter(*HEADINGS):
        target = h
        prev = h.getprevious()
        while prev is not None and _is_ornament_block(prev, opts):
            target, prev = prev, prev.getprevious()
        if PAGE_BREAK in (h.get('style') or '') + (target.get('style') or ''):
            continue
        if _visible_before(target, body, opts):
            target.set('style', PAGE_BREAK)


KEEP_WITH_NEXT = 'page-break-after: avoid'


def keep_ornaments_with_text(body, opts):
    """Keep the paragraph before an ornament on the same page as it, so a
    full page doesn't push the ornament alone onto an otherwise empty page."""
    for el in body.iter(P, IMG):
        if not _is_ornament_block(el, opts):
            continue
        prev = el.getprevious()
        if (prev is not None and prev.tag == P and _text(prev).strip()
                and 'page-break-after' not in (prev.get('style') or '')):
            prev.set('style', KEEP_WITH_NEXT)


def fix_title(root, stats):
    """pdftohtml leaves a mojibake <title>; use the first heading instead."""
    title = next(root.iter(TITLE), None)
    if title is None:
        return
    if (title.text or '').strip() and '�' not in title.text:
        return
    heading = next(root.iter(*HEADINGS), None)
    if heading is not None and _text(heading).strip():
        title.text = re.sub(WS, ' ', _text(heading)).strip()
        stats.add('document title repaired')


def clean_document(root, opts):
    """Clean one parsed XHTML document in place; returns Stats."""
    stats = Stats()
    body = next(root.iter(BODY), None)
    if body is None:
        return stats
    containers = [body] + [d for d in body.iter(DIV)
                           if any(c.tag == P for c in d)]
    for c in containers:
        remove_blank_blocks(c, opts, stats)
    detect_headings(body, opts, stats)
    promote_first_title(body, opts, stats)
    for c in containers:
        merge_broken_paragraphs(c, opts, stats)
    for el in body.iter(P, *HEADINGS):
        if not any(a.tag in SKIP_TEXT for a in el.iterancestors()):
            fix_text(el, opts, stats)
    style_headings(body, opts)
    keep_ornaments_with_text(body, opts)
    fix_title(root, stats)
    return stats


# --- book-wide detection helpers ----------------------------------------------

_DASH = r'(?:—|(?<!-)-{2,3}(?!-))'      # em dash or an ASCII "--" stand-in


def detect_dash_style(texts):
    """The book's own em dash style by majority: 'spaced' (a — b) or 'tight'
    (a—b, the default and the usual US style). Counts "--" like an em dash."""
    tight = spaced = 0
    for t in texts:
        tight += len(re.findall(r'(?<=\S)%s(?=\S)' % _DASH, t))
        spaced += len(re.findall(r'(?<=\s)%s(?=\s)' % _DASH, t))
    return 'spaced' if spaced > tight and spaced >= 5 else 'tight'


HYPHEN_DASH_MIN = 5      # hyphens right before a quote mark that mean "dash"


def detect_hyphen_dash(texts):
    """True when the book writes its dashes as a lone "-" ("smile- yes", "to-“
    Entreri began"). The tell is a hyphen right before a quote mark: no word
    is ever split there, while one at the end of a paragraph can be a word
    cut by a page break."""
    n = sum(len(re.findall(r'[A-Za-z]-(?=[“”"‘’])', t)) for t in texts)
    return n >= HYPHEN_DASH_MIN


def is_latin(texts):
    """True when most letters are Latin (so case-based rules make sense)."""
    latin = other = 0
    for t in texts:
        for ch in t:
            if ch.isalpha():
                if ch < 'ɐ':
                    latin += 1
                else:
                    other += 1
    return latin >= other
