#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Find an action: one box that finds anything the window can do, by name.

calibre's actions are spread over a toolbar, a dozen dropdowns and their
submenus, and the right-click menus, and the way to find one is to remember
where it lives. Here every action the window has registered -- calibre's, this
fork's and every plugin's, because all of them are `gui.iactions` -- is one list
to type into: the toolbar buttons and everything in their menus, with the menu
each one is in, its shortcut, and greyed when it cannot run right now (no book
selected). Preferences' pages are in it too, since they are the Preferences
button's menu.

It is calibre's own kind of thing, an `InterfaceAction` registered as a
built-in (`calibre_zen.books.register`), so Preferences -> Toolbars & menus
places it, the Keyboard page rebinds it (`Ctrl+K` to start), and taking it off
the toolbar is the same as for any other button.

Nothing is copied out of the menus: the list is read off them each time the box
opens, so a plugin installed a minute ago, a menu calibre rebuilt and the
selection's effect on what is enabled are all current. Choosing a row triggers
that row's own QAction, the same as clicking it in its menu.
"""

from __future__ import annotations

from qt.core import QFrame, QLabel, QLayout, QLineEdit, QPoint, Qt, QTimer, QVBoxLayout

from calibre.gui2.actions import InterfaceAction
from calibre_zen import popovers
from calibre_zen.finder import ACTION_NAME, english, match
from calibre_zen.finder.results import ResultsView
from calibre_zen.theme.tokens import components

# calibre's All actions button is a menu of copies of the others' actions;
# listing it would list everything twice.
NOT_LISTED = frozenset({ACTION_NAME, 'All GUI actions'})


def _also(action, *more) -> str:
    "What an entry is found by besides its title: its English, its tooltip."
    title = match.plain(action.text())
    tip = match.plain(action.toolTip())
    parts = [english.english(title)]
    if tip and tip != title:
        parts += [tip, english.english(tip)]
    return ' '.join(p for p in (*parts, *more) if p)


def collect(gui) -> list[match.Entry]:
    """
    Every action reachable from `gui.iactions`, top-level first and then its
    menu, depth first, in the order the menus show them. An action that is in
    two menus is listed once, where it is met first.
    """
    seen: set[int] = set()
    entries: list[match.Entry] = []

    def add(action, path, *more, shortcut=None) -> None:
        title = match.plain(action.text())
        if not title or id(action) in seen:
            return
        seen.add(id(action))
        entries.append(
            match.Entry(
                title=title,
                where=match.path(path),
                also=_also(action, *more),
                target=action,
                icon=action.icon(),
                shortcut=shortcut if shortcut is not None else action.shortcut(),
                enabled=action.isEnabled(),
            )
        )

    def walk(menu, path) -> None:
        for action in menu.actions():
            if action.isSeparator() or not action.isVisible():
                continue
            sub = action.menu()
            if sub is not None:
                walk(sub, (*path, match.plain(action.text())))
            else:
                add(action, path)

    for name, iaction in gui.iactions.items():
        qaction = getattr(iaction, 'qaction', None)
        if name in NOT_LISTED or qaction is None or not qaction.isVisible():
            continue
        top = match.plain(qaction.text()) or name
        # The button's key is on its twin, the action calibre keeps out of
        # menus so the key is not taken twice (`InterfaceAction.create_action`).
        # The twin is never listed: it does what the button does.
        twin = getattr(iaction, 'menuless_qaction', None)
        if twin is not None:
            seen.add(id(twin))
        keys = qaction.shortcut()
        if keys.isEmpty() and twin is not None:
            keys = twin.shortcut()
        # A plugin's internal name is English whatever the window's language.
        add(qaction, (), name, shortcut=keys)
        menu = qaction.menu()
        if menu is not None:
            walk(menu, (top,))
    return entries


class ActionSearchPopup(QFrame):
    """
    The box and its list, in a popup like a menu's.

    The window is transparent and holds one frame that the sheet paints
    (`#zenActionSearch`, from `popovers.painted_body`).
    """

    def __init__(self, gui):
        super().__init__(gui, Qt.WindowType.Popup)
        self.gui = gui
        self.entries: list[match.Entry] = []
        self.setObjectName('zenActionSearchWindow')
        self.body = body = popovers.painted_body(self, 'zenActionSearch')
        # The window follows its contents: fewer matches, a shorter popup.
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        body.setFixedWidth(components.FINDER_POPUP_WIDTH)
        pad = components.FINDER_PAD
        column = QVBoxLayout(body)
        column.setContentsMargins(pad, pad, pad, pad)
        column.setSpacing(pad)

        self.field = QLineEdit(body)
        self.field.setObjectName('zenFinderField')
        self.field.setPlaceholderText(_('Find an action, a menu item or a settings page'))
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self.refresh)
        column.addWidget(self.field)

        self.view = ResultsView(body)
        self.view.follow(self.field)
        self.view.chosen.connect(self.run)
        column.addWidget(self.view)

        self.none = QLabel(_('No action matches.'), body)
        self.none.setObjectName('zenFinderNone')
        self.none.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.none.setVisible(False)
        column.addWidget(self.none)

    def refresh(self, *args) -> None:
        found = match.rank(self.entries, self.field.text())
        self.view.show_entries(found)
        # As tall as its rows, up to the popup's limit, so three matches are not
        # three rows on top of a blank page.
        rows = len(found) * components.FINDER_ROW_HEIGHT + 2 * self.view.frameWidth()
        self.view.setFixedHeight(min(rows, components.FINDER_POPUP_HEIGHT))
        self.view.setVisible(bool(found))
        self.none.setVisible(not found)

    def run(self, entry: match.Entry) -> None:
        self.close()
        # After the popup has gone: an action that opens a dialog would
        # otherwise open it under a popup that is still grabbing the mouse.
        QTimer.singleShot(0, entry.target.trigger)

    def open_at(self, anchor) -> None:
        "Fresh entries, an empty box, and the popup under `anchor` or atop the window."
        self.entries = collect(self.gui)
        self.field.clear()
        self.refresh()
        if anchor is not None and anchor.isVisible():
            popovers.place(self, anchor, above=False, gap=components.FINDER_GAP)
        else:
            top = self.gui.mapToGlobal(QPoint(0, 0))
            x = top.x() + (self.gui.width() - self.sizeHint().width()) // 2
            self.move(x, top.y() + components.FINDER_POPUP_TOP)
        self.show()
        self.field.setFocus(Qt.FocusReason.PopupFocusReason)


class ActionSearchAction(InterfaceAction):
    name = ACTION_NAME
    action_spec = (_('Find an action'), 'search.png', _('Find any action, menu item or settings page by name'), 'Ctrl+K')
    # A box that opens over the window; it has no business on a book's menu.
    dont_add_to = frozenset({'context-menu', 'context-menu-split', 'context-menu-device', 'context-menu-cover-browser'})

    def genesis(self) -> None:
        self.popup = None
        self.qaction.triggered.connect(self.show_popup)

    def anchor(self):
        "The button on whichever main toolbar is showing, if this action has one."
        for bar in getattr(self.gui.bars_manager, 'main_bars', ()):
            if bar.isVisible():
                widget = bar.widgetForAction(self.qaction)
                if widget is not None and widget.isVisible():
                    return widget
        return None

    def show_popup(self) -> None:
        if self.popup is None:
            self.popup = ActionSearchPopup(self.gui)
        self.popup.open_at(self.anchor())
