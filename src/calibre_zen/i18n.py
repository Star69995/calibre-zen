#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Translations for the strings this fork adds.

calibre's translations are one compiled catalog per language, inside the binary
this fork is laid on top of, and it knows nothing of a string only we wrote. So
those stayed English in an otherwise translated window. Ours live beside the
code, as `locales/<lang>.po`, and are added to calibre's translator as a
*fallback*: calibre's own catalog is asked first and keeps every string it has,
and ours answer only for the ones it has no entry for.

Two things make "add them once" not enough:

* calibre changes language while running -- the welcome wizard's language box
  calls `set_translators()` again, which builds a new translator and drops the
  fallback. The call is wrapped, so the new translator gets ours too.
* a string translated at import needs the catalog already there, so
  `hooks.py` installs this before it imports the rest. (Tables of texts are
  kept in English with `N_()` instead, so a language switch reaches them.)

The layout direction rides on the same catalog. Qt mirrors the whole
application when its translator turns `QT_LAYOUT_DIRECTION` into "RTL";
calibre's catalogs never do, so calibre is left to right even in Hebrew. Ours
does (`LAYOUT_DIRECTION`), and `follow_translator_direction` has Qt read it
again each time calibre installs its translator, since that sends Qt no
LanguageChange of its own.

A `.po` is compiled with calibre's own `msgfmt`, in memory, when the language
is picked; nothing is written to the install directory, which a package may
have installed read-only. A language with no file here is left alone.
"""

import io
import os
import sys
import traceback
from functools import wraps

LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')

_installed = False
_attached_to = None  # the translator the catalog was last added to
_own = None  # our catalog alone, for override()


def catalog_for(lang: str | None) -> str | None:
    "The .po for a language code like `he` or `pt_BR`: exact match, then the bare language."
    if not lang:
        return None
    for code in (lang, lang.split('_')[0].lower()):
        path = os.path.join(LOCALES, code + '.po')
        if os.path.exists(path):
            return path
    return None


def compile_po(path: str) -> bytes | None:
    """
    A .po as the bytes of a .mo, or None if calibre's compiler gives up on it.

    `make_with_stats`, not `make`: msgfmt keeps its messages in a module-level
    dict that `make` only ever adds to, so a second catalog would arrive with
    the first one's strings in it. It also exits the process on a malformed
    file, which is not an `Exception`.
    """
    from calibre.translations import msgfmt

    buf = io.BytesIO()
    try:
        msgfmt.make_with_stats(path, buf)
    except Exception, SystemExit:
        traceback.print_exc()
        return None
    return buf.getvalue()


def attach() -> bool:
    "Add our catalog to calibre's current translator. Returns whether one was added."
    global _attached_to
    from calibre.utils import localization
    from calibre_extensions.translator import Translator

    global _own
    current = localization.default_translator
    if current is _attached_to:
        return False
    _own = None
    path = catalog_for(localization.get_lang())
    if path is None:
        return False
    compiled = compile_po(path)
    if compiled is None:
        return False
    _own = Translator(compiled)
    current.add_fallback(Translator(compiled))
    _attached_to = current
    return True


def redetect_direction() -> None:
    """
    Have Qt read `LAYOUT_DIRECTION` again, from the translator just installed.

    Qt reads it on a LanguageChange, and installing calibre's translator sends
    none: calibre's is a QTranslator subclass with no file loaded, which Qt
    takes for an empty one and installs without a word. Setting the direction
    back to automatic is Qt's own way to make it look again, and every window
    is told of the change.
    """
    from qt.core import QGuiApplication, Qt

    if QGuiApplication.instance() is not None:
        QGuiApplication.setLayoutDirection(Qt.LayoutDirection.LayoutDirectionAuto)


def N_(msgid: str) -> str:
    """
    `msgid`, unchanged: a mark that a string in a table is translated later, by
    `_()` where it is shown. It is what lets `locales/<lang>.po` and the tests
    see the string, which a bare literal in a tuple would hide from them.
    """
    return msgid


# Qt lays the whole application out right to left when its translator turns
# this string into "RTL" (QGuiApplication reads it on every LanguageChange).
# calibre's catalogs have no entry for it, so calibre stays left to right in
# Hebrew and Arabic; a catalog here that should mirror the window translates
# it, and Qt does the rest -- the main window, menus, dialogs and the welcome
# wizard, at start and after the wizard switches language.
LAYOUT_DIRECTION = N_('QT_LAYOUT_DIRECTION')


def override(msgid: str) -> str:
    """
    `msgid` as our catalog has it, else as calibre's does.

    The fallback above never answers for a string calibre already translates,
    which is right for ours and wrong for the few of calibre's we word
    differently ("Save to disk" is a line long in Hebrew). The source has to
    spell the string out as the argument, so the tests can see it is in use.
    """
    if _own is not None:
        ans = _own.gettext(msgid)
        if ans != msgid:
            return ans
    return _(msgid)


def follow_translator_direction() -> None:
    """
    Re-detect the layout direction whenever calibre installs Qt's translator:
    in Application.__init__, and after the welcome wizard's language box
    switches language (both go through `Application.load_translations`).
    """
    from calibre.gui2 import Application

    orig = Application.load_translations
    if hasattr(orig, '__wrapped__'):
        return

    @wraps(orig)
    def load_translations(self):
        orig(self)
        try:
            redetect_direction()
        except Exception:
            traceback.print_exc()

    Application.load_translations = load_translations


def install() -> bool:
    "Attach now and after every language switch. Safe to call twice; never raises."
    global _installed
    if _installed:
        return True
    try:
        from calibre.utils import localization

        cls = type(localization.set_translators)
        orig = cls.__call__
        if not hasattr(orig, '__wrapped__'):  # an earlier call got as far as wrapping

            @wraps(orig)
            def __call__(self, *args, **kwargs):
                result = orig(self, *args, **kwargs)
                try:
                    attach()
                except Exception:
                    traceback.print_exc()
                return result

            cls.__call__ = __call__
        follow_translator_direction()
        attach()
    except Exception:
        # Untranslated strings are an acceptable Tuesday; a window that does not
        # open is not.
        traceback.print_exc()
        print('calibre-zen: translations did not install and are off for this session', file=sys.stderr)
        return False
    _installed = True
    return True
