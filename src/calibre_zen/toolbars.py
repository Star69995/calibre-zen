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

One button stands for two. Send to device acts on the library's books and Add
books to library on the device's, and calibre greys out whichever does not
apply where you are -- so the bar showed a dead button either way. Here they
share a place: wherever the device bar has Send to device, Add books to library
is put right after it (`with_partners`), and only the one for the list in view
is shown (`PARTNERS`, applied from each action's `location_selected`). Moving to
the device's books turns Send to device into Add to library, and back.
"""

from __future__ import annotations

import traceback

from calibre_zen.i18n import N_

# What a device adds, until the reader chooses otherwise in Preferences -> Toolbars & menus.
DEVICE_ADDITIONS = ('Send To Device', 'Update On Device', 'Location Manager')

# A button for the library's books, and the one that takes its place on the bar
# while a device's books are in view.
PARTNERS = {'Send To Device': 'Add To Library'}

# Strings of calibre's own, shown in the dialogs this file changes, that calibre's
# Hebrew catalog does not have. Listed so locales/<lang>.po can answer them: the
# catalog is only consulted for what is named in this package (tests/test_i18n.py).
CALIBRE_LOCATION_NAMES = (
    N_('The buttons on the search bar'),
    N_('The context menu for the books in the calibre library'),
    N_('The context menu for the split book list'),
    N_('The context menu for the books on the device'),
    N_('The context menu for the Cover browser'),
    N_('You can also customise the plugin locations using <b>Preferences -> Interface -> Toolbars</b>'),
)

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


def with_partners(layout) -> tuple:
    "`layout` with each button of PARTNERS followed by its partner, unless the partner is already there."
    layout = tuple(layout or ())
    out = []
    for name in layout:
        out.append(name)
        partner = PARTNERS.get(name)
        if partner is not None and partner not in layout:
            out.append(partner)
    return tuple(out)


def shown_at(name: str, location: str) -> bool | None:
    """
    Whether a button of PARTNERS shows at `location` ('library', 'main',
    'carda', 'cardb'): the lead in the library, its partner on a device. None
    for any other button, which is left as it is.
    """
    in_library = location == 'library'
    if name in PARTNERS:
        return in_library
    if name in PARTNERS.values():
        return not in_library
    return None


# The places whose layout keeps the application's own buttons at the far end
# (`appearance.TRAILING`), so a button added to them goes in before that run.
KEEPS_TRAILING = frozenset({'toolbar'})


def with_new_button(layout, name, key: str) -> tuple:
    """
    `layout`, the buttons already in place `key`, with `name` added where an
    install puts it.

    calibre appends, which on the main toolbar puts a new plugin after Help and
    Preferences, and a bar that no longer ends with them has no far end to push
    them to (`appearance.trailing_start`). So there it goes in before that run;
    anywhere else it goes last. Used by the picture the install dialog draws and
    by the install itself, so what is shown is what is done.
    """
    layout = list(layout or ())
    if key not in KEEPS_TRAILING:
        return tuple(layout + [name])
    from calibre_zen.theme.appearance import TRAILING

    at = len(layout)
    while at > 0 and (layout[at - 1] is None or layout[at - 1] in TRAILING):
        at -= 1
    return tuple(layout[:at] + [name] + layout[at:])


def placed(before, after, key: str) -> tuple:
    """
    What `key`'s layout should be once an install has changed it from `before`
    to `after`: the buttons the install appended, put where `with_new_button`
    says. A change that is not an append is left exactly as it is.
    """
    before, after = tuple(before or ()), tuple(after or ())
    if after == before or after[: len(before)] != before:
        return after
    ans = before
    for name in after[len(before) :]:
        ans = with_new_button(ans, name, key)
    return ans


def recommended_label(text: str) -> str:
    "A place the plugin itself asked for, as the install dialog lists it."
    return _('{} · Recommended').format(text)


def device_label(key: str, text: str) -> str:
    "The Preferences wording for a location: only the device toolbar's differs."
    return _('Added to the main toolbar when a device is connected') if key == 'toolbar-device' else text


def install() -> bool:
    "Build the connected-device toolbar from the main one, and say so in Preferences."
    global _installed
    if _installed:
        return True
    from calibre.gui2.actions import InterfaceAction
    from calibre.gui2.bars import BarsManager
    from calibre.gui2.dialogs.choose_plugin_toolbars import ChoosePluginToolbarsDialog
    from calibre.gui2.preferences.plugins import ConfigWidget as PluginsConfigWidget
    from calibre.gui2.preferences.toolbar import ConfigWidget

    orig_check = PluginsConfigWidget.check_for_add_to_toolbars
    orig_init_bars = BarsManager.init_bars
    orig_location_selected = InterfaceAction.location_selected
    orig_genesis = ConfigWidget.genesis
    orig_dialog = ChoosePluginToolbarsDialog.__init__

    def init_bars(self):
        ans = orig_init_bars(self)
        try:
            main, extras = self.bar_actions[0], self.bar_actions[1]
            layout = with_partners(device_layout(main, extras, self.gui.iactions))
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
        says = getattr(plugin, 'default_add_to', None) is not None
        for row, (key, text) in enumerate(locations):
            item = self._locations_list.item(row)
            if item is not None:
                item.setSelected(key in wanted)
                if says and key in wanted:
                    item.setText(recommended_label(device_label(key, text)))
        try:
            from calibre_zen import placement

            placement.attach(self, getattr(parent, 'gui', None), plugin)
        except Exception:
            # The dialog without its picture is calibre's whole dialog.
            traceback.print_exc()

    def check_for_add_to_toolbars(self, plugin, previously_installed=True):
        from calibre.gui2 import gprefs

        keys = ['action-layout-' + key for key in KEEPS_TRAILING]
        before = {k: tuple(gprefs.get(k) or ()) for k in keys}
        ans = orig_check(self, plugin, previously_installed)
        try:
            for k in keys:
                now = tuple(gprefs.get(k) or ())
                fixed = placed(before[k], now, k[len('action-layout-') :])
                if fixed != now:
                    gprefs[k] = fixed
        except Exception:
            traceback.print_exc()
        return ans

    def follow_location(cls):
        "Wrap one partner action's location_selected so its button shows only where it applies."
        orig = cls.__dict__.get('location_selected', orig_location_selected)

        def location_selected(self, loc):
            ans = orig(self, loc)
            show = shown_at(self.name, loc)
            if show is not None:
                self.qaction.setVisible(show)
            return ans

        cls.location_selected = location_selected

    from calibre.gui2.actions.add_to_library import AddToLibraryAction
    from calibre.gui2.actions.device import SendToDeviceAction

    for cls in (SendToDeviceAction, AddToLibraryAction):
        follow_location(cls)
    BarsManager.init_bars = init_bars
    ConfigWidget.genesis = genesis
    ChoosePluginToolbarsDialog.__init__ = dialog_init
    PluginsConfigWidget.check_for_add_to_toolbars = check_for_add_to_toolbars
    _installed = True
    return True
