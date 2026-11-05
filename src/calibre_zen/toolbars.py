#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
One main toolbar, with the device's buttons added to it.

calibre keeps two main toolbars, each a full layout of its own: the main one,
and "the main toolbar when a device is connected", and swaps one for the other
when a reader is plugged in. Two lists to keep in step, and every change to one
has to be made again in the other.

Here the second list is only what a device *adds*. The bar a connected device
shows is the main toolbar with those buttons put in after the books' own, ahead
of the application's run at the far end (Preferences, Help -- see
`appearance.TRAILING`). Nothing is rebuilt per connection: calibre still has two
`ToolBar`s and still swaps them (`BarsManager.update_bars`), which is what keeps
its workaround for popup menus and modal dialogs in place. The second is built
from the first, so they cannot drift.

The preference keeps its key, `action-layout-toolbar-device`, and a layout saved
under it by calibre still works: everything in it that the main toolbar already
has is dropped as a duplicate, which for calibre's own default leaves Send to
device and the Location manager, the two buttons that only mean something with
a device.
"""

from __future__ import annotations

import traceback

# What a device adds, until the reader chooses otherwise in Preferences -> Toolbars & menus.
DEVICE_ADDITIONS = ('Send To Device', 'Location Manager')

_installed = False

# Where a new plugin's button is offered, for a plugin that does not say.
DEFAULT_ADD_TO = frozenset({'toolbar'})


def wanted_locations(plugin) -> frozenset:
    """
    The locations the install dialog ticks for `plugin`, an InterfaceAction.

    A plugin says where it belongs with a class attribute, in the same terms as
    `dont_add_to` (`InterfaceAction.all_locations`)::

        class MyAction(InterfaceAction):
            default_add_to = frozenset({'toolbar', 'searchbar'})

    `'toolbar-device'` is what a device *adds* to the main toolbar -- see the
    top of this file -- so a plugin that only makes sense with a device names
    that alone. A plugin that says nothing gets the main toolbar, where
    calibre's own dialog also ticked the device bar. A name the plugin cannot
    be added to (`dont_add_to`) is ignored, and so is one that is not a
    location, so a typo does not leave the dialog with nothing ticked.
    """
    asked = getattr(plugin, 'default_add_to', None)
    if asked is None:
        return DEFAULT_ADD_TO
    if isinstance(asked, str):
        asked = (asked,)
    return frozenset(asked) - frozenset(getattr(plugin, 'dont_add_to', ()))


def device_layout(main, extras, iactions=None) -> tuple:
    """
    `main` with `extras` put in after its last book action and before the run of
    separators and application buttons at its end, behind one separator.

    A button `main` already has is not added again, a separator in `extras` is
    ignored, and an action that cannot go on the device toolbar
    (`dont_add_to`, which the LLM actions use) is left out of the result
    altogether, since the bar is the main toolbar and nothing else. `iactions`
    is the GUI's name -> action table; without it nothing is filtered.
    """
    from calibre_zen.theme.appearance import TRAILING

    def allowed(name) -> bool:
        ac = (iactions or {}).get(name)
        return name is None or ac is None or 'toolbar-device' not in getattr(ac, 'dont_add_to', ())

    main = [x for x in (main or ()) if allowed(x)]
    have = set(main)
    added = []
    for name in extras or ():
        if name is not None and name not in have and allowed(name):
            added.append(name)
            have.add(name)
    if not added:
        return tuple(main)
    at = len(main)
    while at > 0 and (main[at - 1] is None or main[at - 1] in TRAILING):
        at -= 1
    return tuple(main[:at] + ([None] if at else []) + added + main[at:])


def device_label(key: str, text: str) -> str:
    "The Preferences wording for a location: only the device toolbar's differs."
    return _('Added to the main toolbar when a device is connected') if key == 'toolbar-device' else text


def install() -> bool:
    "Build the connected-device toolbar from the main one, and say so in Preferences."
    global _installed
    if _installed:
        return True
    from calibre.gui2.bars import BarsManager
    from calibre.gui2.dialogs.choose_plugin_toolbars import ChoosePluginToolbarsDialog
    from calibre.gui2.preferences.toolbar import ConfigWidget

    orig_init_bars = BarsManager.init_bars
    orig_genesis = ConfigWidget.genesis
    orig_dialog = ChoosePluginToolbarsDialog.__init__

    def init_bars(self):
        ans = orig_init_bars(self)
        try:
            main, extras = self.bar_actions[0], self.bar_actions[1]
            layout = device_layout(main, extras, self.gui.iactions)
            self.bar_actions = (main, layout) + tuple(self.bar_actions[2:])
            self.main_bars[1].init_bar(layout)
        except Exception:
            traceback.print_exc()
        return ans

    def genesis(self, gui):
        # An instance attribute, read by genesis() in place of the class's list:
        # the wording is translated now, in the language the reader chose, not
        # when this module was imported.
        self.LOCATIONS = [(key, device_label(key, text)) for key, text in ConfigWidget.LOCATIONS]
        return orig_genesis(self, gui)

    def dialog_init(self, parent, plugin, locations):
        # calibre ticks the two main toolbars for every plugin; here the plugin
        # chooses (wanted_locations), and the device entry is worded as above.
        orig_dialog(self, parent, plugin, [(key, device_label(key, text)) for key, text in locations])
        self.locations = locations
        wanted = wanted_locations(plugin)
        for row, (key, _text) in enumerate(locations):
            item = self._locations_list.item(row)
            if item is not None:
                item.setSelected(key in wanted)

    BarsManager.init_bars = init_bars
    ConfigWidget.genesis = genesis
    ChoosePluginToolbarsDialog.__init__ = dialog_init
    _installed = True
    return True
