#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The English a translated label was made from, so a search finds it either way.

In a Hebrew window "convert" should still find "המר ספרים": people learn
calibre's names from English guides and forum posts, and an English plugin name
sits inside a Hebrew menu anyway. Every label on screen came out of a catalog,
so the catalog read backwards gives its English: msgstr -> msgid, calibre's own
first and this fork's (`locales/<lang>.po`) for the strings calibre does not
have.

Built once per language, the first time a search asks, from the same files the
translator was made from. A text the catalogs do not hold (a plugin's own
string, a label with a number filled in) has no English and is matched as it
is shown. In English there is nothing to add.
"""

from __future__ import annotations

import io
import traceback

_cache: dict[str, dict[str, str]] = {}


def _reverse(mo: bytes, into: dict[str, str]) -> None:
    "Add a compiled catalog's translations to `into`, each mapped to its msgid."
    from gettext import GNUTranslations

    from calibre_zen.finder.match import plain

    for msgid, msgstr in GNUTranslations(io.BytesIO(mo))._catalog.items():
        if isinstance(msgid, tuple):  # a plural form: (msgid, n)
            msgid = msgid[0]
        if not msgid or not isinstance(msgstr, str) or msgstr == msgid:
            continue
        into.setdefault(plain(msgstr), plain(msgid))


def _load(lang: str) -> dict[str, str]:
    from zipfile import ZipFile

    from calibre.utils.localization import get_lc_messages_path, zf_exists
    from calibre_zen import i18n

    ans: dict[str, str] = {}
    try:
        mpath = get_lc_messages_path(lang)
        if mpath and zf_exists():
            with ZipFile(P('localization/locales.zip', allow_user_override=False)) as zf:
                _reverse(zf.read(mpath + '/messages.mo'), ans)
    except Exception:
        traceback.print_exc()
    path = i18n.catalog_for(lang)
    compiled = i18n.compile_po(path) if path else None
    if compiled:
        _reverse(compiled, ans)
    return ans


def table() -> dict[str, str]:
    "Shown text (`match.plain`) -> its English, for the language in use."
    from calibre.utils.localization import get_lang

    lang = get_lang() or 'en'
    if lang == 'en' or lang.startswith('en_'):
        return {}
    ans = _cache.get(lang)
    if ans is None:
        ans = _cache[lang] = _load(lang)
    return ans


def english(text: str) -> str:
    "The English `text` was translated from, or '' when it has none."
    from calibre_zen.finder.match import plain

    return table().get(plain(text), '')
