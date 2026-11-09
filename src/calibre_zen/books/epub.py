#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""Book cleanup logic: runs the rules from cleanup.py over an epub.

No Qt here. Uses calibre's polish container (so OPF/NCX stay consistent) and
the library's ``new_api`` for reading/writing formats.
"""
import os
import re
import shutil
import tempfile
import traceback

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.split import split
from calibre.ebooks.oeb.polish.toc import commit_toc, from_xpaths, get_toc
from calibre_zen.books.cleanup import BODY, HEADING_RE, HEADINGS, PAGE_BREAK, Options, Stats, clean_document, detect_dash_style, detect_hyphen_dash, is_latin

ORIGINAL_FORMAT = 'ORIGINAL_EPUB'
DELETE_CHUNK = 100               # books per call to remove_formats, so a stop is heard
ORNAMENT_MAX_BYTES = 3000      # a lone image this small is a decorative divider
HTML_MIMES = ('application/xhtml+xml', 'text/html')


class Report:
    def __init__(self, title=''):
        self.title = title
        self.stats = Stats()
        self.changed_files = []
        self.removed_files = []
        self.toc_note = ''
        self.skipped = ''
        self.dash_style = 'tight'

    @property
    def changed(self):
        return bool(self.changed_files)

    def format(self, samples=3):
        out = [self.title or 'Book']
        if self.skipped:
            return '\n'.join(out + ['  skipped: ' + self.skipped])
        if not self.changed:
            return '\n'.join(out + ['  nothing to change'])
        out.append('  em dash style: ' + self.dash_style)
        for rule, n in sorted(self.stats.counts.items(), key=lambda kv: -kv[1]):
            out.append('  %5d  %s' % (n, rule))
            for before, after in self.stats.samples.get(rule, [])[:samples]:
                out.append('           %r -> %r' % (before, after))
        if self.removed_files:
            out.append('  removed unused files: ' + ', '.join(self.removed_files))
        if self.toc_note:
            out.append('  TOC: ' + self.toc_note)
        return '\n'.join(out)


def _html_names(container):
    return [name for name, _linear in container.spine_names
            if container.mime_map.get(name) in HTML_MIMES]


def _body_texts(container, names):
    for name in names:
        yield ''.join(container.parsed(name).itertext())


def _referenced_names(container):
    """Every file still pointed at by an <img>/<image> or a stylesheet."""
    found = set()
    for name, mime in container.mime_map.items():
        if mime in HTML_MIMES:
            root = container.parsed(name)
            for el in root.iter():
                for attr in ('src', '{http://www.w3.org/1999/xlink}href', 'href'):
                    v = el.get(attr) if isinstance(el.tag, str) else None
                    if v:
                        target = container.href_to_name(v, name)
                        if target:
                            found.add(target)
        elif mime == 'text/css':
            for v in re.findall(r'url\(["\']?([^)"\']+)', container.raw_data(name)):
                target = container.href_to_name(v, name)
                if target:
                    found.add(target)
    return found


def _heading_texts(container, names):
    for name in names:
        for h in container.parsed(name).iter(*HEADINGS):
            yield name, h


def _rebuild_toc_if_safe(container, names, report):
    """Only when we created headings, and the old TOC is a flat list of the
    same kind of headings: then it is safe to regenerate it from the <h2>s."""
    created = (report.stats.counts['chapter heading recognised']
               + report.stats.counts['chapter heading split from paragraph']
               + report.stats.counts['first line promoted to heading'])
    if not created:
        return
    toc = get_toc(container)
    items = list(toc.iterdescendants())
    titles = {re.sub(r'\s+', ' ', i.title or '').strip() for i in items}
    h2_texts = {re.sub(r'\s+', ' ', ''.join(h.itertext())).strip()
                for _n, h in _heading_texts(container, names)}
    flat = all(len(i) == 0 for i in items)
    if not items or (flat and titles <= h2_texts):
        new = from_xpaths(container, ['//h:h2'])
        commit_toc(container, new)
        report.toc_note = 'rebuilt from headings (%d entries, was %d)' % (
            len(list(new.iterdescendants())), len(items))
    else:
        report.toc_note = 'left as is (it has custom structure); %d new heading(s)' % created


def _split_chapters(container, report):
    """Give every chapter heading its own file.

    A page-break style inside a file can leave a blank page when the previous
    page is already full; a file boundary never does, and it is how the other
    chapters of these books are laid out anyway."""
    n = 0
    while True:
        target = None
        for name in _html_names(container):
            body = next(container.parsed(name).iter(BODY), None)
            if body is None:
                continue
            for h in body.iter(*HEADINGS):
                text = re.sub(r'\s+', ' ', ''.join(h.itertext())).strip()
                if HEADING_RE.match(text) and any(
                        ''.join(p.itertext()).strip()
                        for p in h.itersiblings(preceding=True) if isinstance(p.tag, str)):
                    target = (name, h)
                    break
            if target:
                break
        if not target:
            break
        name, h = target
        added_id = not h.get('id')
        if added_id:
            h.set('id', 'book_cleanup_split')
        hid = h.get('id')
        new_name = split(container, name, '//*[@id="%s"]' % hid)
        # the heading is the first block of the new file now: no page-break
        # style needed, and drop the temporary id
        for el in container.parsed(new_name).iter(*HEADINGS):
            if el.get('id') == hid:
                if el.get('style') == PAGE_BREAK:
                    del el.attrib['style']
                if added_id:
                    del el.attrib['id']
                container.dirty(new_name)
                break
        n += 1
    if n:
        report.stats.add('file split before chapter heading', n=n)


def clean_container(container, report, remove_ornaments=False):
    names = _html_names(container)
    texts = list(_body_texts(container, names))
    report.dash_style = detect_dash_style(texts)

    def ornament_checker(name):
        def is_ornament(src):
            target = container.href_to_name(src, name)
            return bool(target and target in container.mime_map and
                        len(container.raw_data(target, decode=False)) < ORNAMENT_MAX_BYTES)
        return is_ornament

    heading_class = next((h.get('class') for _n, h in _heading_texts(container, names)
                          if h.get('class')), None)
    opts = Options(dash_style=report.dash_style, latin=is_latin(texts),
                   heading_class=heading_class, is_ornament=None,
                   remove_ornaments=remove_ornaments, hyphen_dash=detect_hyphen_dash(texts))

    removed = set()
    for name in names:
        root = container.parsed(name)
        opts.is_ornament = ornament_checker(name)
        before = _fingerprint(root)
        stats = clean_document(root, opts)
        if _fingerprint(root) != before:
            container.dirty(name)
            report.changed_files.append(name)
        report.stats.update(stats)
        for src in stats.removed_images:
            target = container.href_to_name(src, name)
            if target:
                removed.add(target)

    still_used = _referenced_names(container)
    for target in sorted(removed - still_used):
        container.remove_item(target)
        report.removed_files.append(target)
    if report.changed:
        _split_chapters(container, report)
        _rebuild_toc_if_safe(container, _html_names(container), report)
    return report


def _fingerprint(root):
    from lxml import etree
    return etree.tostring(root)


def clean_epub(src, dst=None, title='', remove_ornaments=False):
    """Clean the epub at src. Writes to dst when given (and something changed).
    Returns a Report; with dst=None it is a dry run."""
    report = Report(title or os.path.basename(src))
    container = get_container(src, tweak_mode=False)
    clean_container(container, report, remove_ornaments)
    if dst and report.changed:
        container.commit(dst)
    return report


def clean_book(db, book_id, dry_run=False, remove_ornaments=False, keep_original=True):
    """Clean the EPUB of one library book (db is ``new_api``).

    The first time a book is changed the untouched file is kept as
    ORIGINAL_EPUB, like calibre's own Polish does, unless ``keep_original`` is
    off. An ORIGINAL_EPUB already there is never replaced."""
    title = db.field_for('title', book_id)
    path = db.format_abspath(book_id, 'EPUB')
    if not path:
        report = Report(title)
        report.skipped = 'no EPUB format'
        return report
    tmp = tempfile.mkdtemp(prefix='book_cleanup_')
    try:
        out = os.path.join(tmp, 'cleaned.epub')
        report = clean_epub(path, None if dry_run else out, title, remove_ornaments)
        if report.changed and not dry_run:
            if keep_original and ORIGINAL_FORMAT not in db.formats(book_id):
                orig = os.path.join(tmp, 'original.epub')
                shutil.copyfile(path, orig)
                db.add_format(book_id, 'ORIGINAL_EPUB', orig, run_hooks=False)
            db.add_format(book_id, 'EPUB', out, run_hooks=False)
        return report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class BatchResult:
    "What a run over several books did: a Report per book, the ids changed, the failures."

    def __init__(self):
        self.reports = []
        self.changed_ids = []
        self.errors = []
        self.cancelled = False


def clean_books(db, book_ids, dry_run=False, keep_original=True, notifications=None, abort=None, log=None):
    """Clean the EPUB of each book, as one calibre job does.

    ``notifications`` (a Queue of ``(fraction, message)``), ``abort`` (an Event)
    and ``log`` are the three keyword arguments calibre gives a ThreadedJob's
    function; all are optional so it runs without a job too. The report of each
    book goes to the log, which is the job's details. A book that fails is
    recorded and the rest carry on."""
    result = BatchResult()
    total = len(book_ids)
    for i, book_id in enumerate(book_ids):
        if abort is not None and abort.is_set():
            result.cancelled = True
            break
        title = db.field_for('title', book_id) or str(book_id)
        if notifications is not None:
            notifications.put((i / total, title))
        try:
            report = clean_book(db, book_id, dry_run=dry_run, keep_original=keep_original)
        except Exception:
            failure = f'{title}\n{traceback.format_exc()}'
            result.errors.append(failure)
            if log is not None:
                log.error(failure)
            continue
        result.reports.append(report)
        if report.changed:
            result.changed_ids.append(book_id)
        if log is not None:
            log(report.format())
    if notifications is not None:
        notifications.put((1, ''))
    return result


def books_with_original(db, book_ids):
    "The ids among ``book_ids`` that have an ORIGINAL_EPUB."
    return [book_id for book_id in book_ids if ORIGINAL_FORMAT in db.formats(book_id)]


def delete_originals(db, book_ids, notifications=None, abort=None, log=None):
    """Delete the ORIGINAL_EPUB of each book. Returns the ids it was deleted from.

    Takes a ThreadedJob's three keyword arguments, like ``clean_books``. The
    cleaned EPUB is not touched; only the kept original goes, for good."""
    removed = []
    total = len(book_ids)
    for start in range(0, total, DELETE_CHUNK):
        if abort is not None and abort.is_set():
            break
        chunk = book_ids[start:start + DELETE_CHUNK]
        if notifications is not None:
            notifications.put((start / total, ''))
        db.remove_formats({book_id: [ORIGINAL_FORMAT] for book_id in chunk})
        removed.extend(chunk)
        if log is not None:
            log(f'Deleted {ORIGINAL_FORMAT} of {len(chunk)} book(s)')
    if notifications is not None:
        notifications.put((1, ''))
    return removed
