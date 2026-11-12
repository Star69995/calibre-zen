#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Build the small library the website's screenshots show: well-known public
domain classics from Project Gutenberg, with their covers and catalog data and
no book files (a screenshot never opens one).

    calibre-debug -e scripts/showcase_library.py -- [<out dir>]

Default out dir: .calibre-zen/showcase-library. Downloads pg_catalog.csv and
one small cover per book into .calibre-zen/showcase-sources, pausing between
requests as Gutenberg asks of scripts, and reuses them on the next run.
"""

import csv
import os
import random
import re
import shutil
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCES = os.path.join(ROOT, '.calibre-zen', 'showcase-sources')
CATALOG = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'
COVER = 'https://www.gutenberg.org/cache/epub/{id}/pg{id}.cover.medium.jpg'
PAUSE = 2.5
IDS = (
    1342, 84, 11, 1661, 2701, 98, 345, 174, 76, 74, 1260, 768, 158, 161, 2554, 120,
    35, 36, 43, 16, 55, 1400, 46, 64317, 5200, 219, 2814, 514, 236, 25344, 1952, 205,
)  # fmt: skip


def fetch(url, path):
    if os.path.exists(path):
        return False
    req = urllib.request.Request(url, headers={'User-Agent': 'calibre-zen-margin website screenshots'})
    with urllib.request.urlopen(req, timeout=60) as r, open(path + '.part', 'wb') as f:
        f.write(r.read())
    os.replace(path + '.part', path)
    return True


def authors(field):
    "Gutenberg's 'Austen, Jane, 1775-1817; ...' as calibre's ['Jane Austen', ...]."
    out = []
    for a in field.split(';'):
        parts = [p.strip() for p in a.split(',') if p.strip() and not p.strip()[:1].isdigit()]
        parts = [p for p in parts if '[' not in p]
        if len(parts) >= 2:
            first = re.sub(r'\s*\([^)]*\)', '', parts[1])
            out.append(f'{first} {parts[0]}')
        elif parts:
            out.append(parts[0])
    # The writer only: illustrators and translators follow, and crowd the list.
    return out[:1] or ['Unknown']


def tags(row):
    shelves = [s.strip() for s in row['Bookshelves'].split(';')]
    return sorted({s.split(':', 1)[1].strip() for s in shelves if s.startswith('Category:')})[:3]


def main():
    out = os.path.abspath(sys.argv[-1]) if len(sys.argv) > 1 and not sys.argv[-1].endswith('.py') else os.path.join(ROOT, '.calibre-zen', 'showcase-library')
    os.makedirs(os.path.join(SOURCES, 'covers'), exist_ok=True)
    catalog_path = os.path.join(SOURCES, 'pg_catalog.csv')
    if fetch(CATALOG, catalog_path):
        time.sleep(PAUSE)
    with open(catalog_path, encoding='utf-8') as f:
        catalog = {row['Text#']: row for row in csv.DictReader(f)}

    from calibre.ebooks.metadata.book.base import Metadata
    from calibre.library import db as open_db
    from calibre.utils.date import parse_date

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    api = open_db(out).new_api
    rnd = random.Random(7)
    for pg_id in IDS:
        row = catalog.get(str(pg_id))
        if row is None:
            print('not in the catalog:', pg_id)
            continue
        cover_path = os.path.join(SOURCES, 'covers', f'{pg_id}.jpg')
        try:
            if fetch(COVER.format(id=pg_id), cover_path):
                time.sleep(PAUSE)
        except Exception as e:
            print('no cover for', pg_id, e)
        title = row['Title'].split('\n')[0].split(';')[0].strip()
        mi = Metadata(title, authors(row['Authors']))
        mi.tags = tags(row)
        mi.languages = [row['Language'].split(';')[0].strip() or 'en']
        mi.publisher = 'Project Gutenberg'
        mi.pubdate = parse_date(row['Issued'])
        mi.rating = rnd.choice((6, 8, 8, 10, 10))
        mi.identifiers = {'gutenberg': str(pg_id)}
        cover = None
        if os.path.exists(cover_path):
            with open(cover_path, 'rb') as f:
                cover = f.read()
        api.create_book_entry(mi, cover=cover)
        print(pg_id, title, '/', ', '.join(mi.authors), flush=True)
    print('library:', out)


main()
