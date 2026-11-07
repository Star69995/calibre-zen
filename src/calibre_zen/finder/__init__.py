#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Two search boxes: one for what the window can do, one for Preferences.

- **Find an action** (`actions.py`), a button at the far end of the main
  toolbar and `Ctrl+K`: every action, menu item and settings page by name.
- **Search settings** (`settings.py`), a box in Preferences' title bar: every
  setting by the words on its page, and a click takes you to it.

Both list `match.Entry` rows in the same `results.ResultsView`, ranked by the
same `match.rank`, and both find a label by its English as well as by the
window's language (`english.py`), so "convert" finds "המר ספרים".

Each has its own switch in the features menu (`features.py`):
`CALIBRE_ZEN_ACTION_SEARCH` and `CALIBRE_ZEN_SETTINGS_SEARCH`.

This module stays free of Qt: `hooks.py` imports it while the application is
still being built.
"""

from calibre.customize import InterfaceActionBase
from calibre_zen import features

# The action's name in gui.iactions and in the toolbar layouts.
ACTION_NAME = 'Find Action'
# Set once the button has been put on a toolbar someone had arranged, so taking
# it off again in Preferences is final.
OFFERED_KEY = 'zen_find_action_offered'
TOOLBAR_KEY = 'action-layout-toolbar'

_installed = False


class FindActionBase(InterfaceActionBase):
    name = ACTION_NAME
    description = 'Find any action, menu item or settings page by name'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Star'
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = 'calibre_zen.finder.actions:ActionSearchAction'


def with_button(layout) -> tuple:
    "`layout` with the button at its end, after a separator, unless it is already there."
    layout = tuple(layout or ())
    return layout if ACTION_NAME in layout else layout + (None, ACTION_NAME)


def offer_once() -> bool:
    """
    Put the button on a main toolbar the person has arranged themselves, once.

    A new install gets it from the default layout (`hooks.TOOLBAR_ADDITIONS`);
    an arranged toolbar is a stored setting, which a default never reaches. So
    it is added the first time this runs, and never again: if it is then taken
    off, it stays off. Returns whether the layout was changed.
    """
    from calibre.gui2 import gprefs

    if gprefs.get(OFFERED_KEY):
        return False
    gprefs[OFFERED_KEY] = True
    if TOOLBAR_KEY not in gprefs:
        return False
    current = tuple(gprefs[TOOLBAR_KEY] or ())
    wanted = with_button(current)
    if wanted == current:
        return False
    gprefs[TOOLBAR_KEY] = list(wanted)
    return True


def install_actions() -> bool:
    "Register Find an action as a calibre built-in and put it on the toolbar."
    if not features.enabled('action-search'):
        return False
    from calibre_zen import books

    books.register((FindActionBase,))
    offer_once()
    return True


def install_settings() -> bool:
    "The search box in Preferences."
    global _installed
    if not features.enabled('settings-search'):
        return False
    if _installed:
        return True
    from calibre_zen.finder import settings

    _installed = settings.install()
    return _installed
