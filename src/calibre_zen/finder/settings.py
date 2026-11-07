#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
A search box in Preferences that finds a setting, not only a page.

calibre's Preferences is twenty-odd pages of icons, and a setting is found by
guessing which page it is on and then which tab of that page. The box in the
dialog's title bar searches the words on the pages themselves -- every label,
tick box, button, group and tab, and their tooltips -- as well as the pages'
names and descriptions. Choosing a result opens the page, brings its tab
forward, scrolls the setting into view and marks it for a moment.

Where the words come from. calibre builds a page only when it is opened
(`Preferences.show_plugin`), and much of a page is built in code, not read from
a `.ui` file, so the only complete list of what a page says is the page.
`PageIndex` builds each page the way the dialog does (create, `genesis`,
`initialize`), off screen and one page per turn of the event loop, reads its
widgets and throws it away: about two seconds for all of them, without the box
ever freezing, and results arrive as pages are read. It is started by the first
key typed and kept for the rest of the run, per language and set of pages, so
it is paid once.

How a result finds its widget again. A page built a second time is built the
same way, so a widget is named by its class, its text, and which of the widgets
with that class and text it was (`Locator`), and found by walking the new page
in the same order.

Two wraps, no upstream file edited:

`Preferences.__init__`
    Adds the box to the title bar and the results as a third page of the
    dialog's stack, after the overview and the open page.
`Preferences.hide_plugin`
    Shows the box again on the way back to the overview.
"""

from __future__ import annotations

import traceback
from collections import Counter
from collections.abc import Callable
from functools import partial
from typing import NamedTuple

from qt.core import (
    QAbstractButton,
    QAbstractItemView,
    QEvent,
    QGroupBox,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QObject,
    QScrollArea,
    QShortcut,
    QStackedWidget,
    Qt,
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre_zen.finder import english, match
from calibre_zen.finder.results import ResultsView
from calibre_zen.theme.tokens import components

# Where the results go in the dialog's stack: after the overview (0) and the open page (1).
RESULTS_PAGE = 2
# A text on this many pages or more is the pages' furniture (Next, Previous),
# not a setting of any one of them.
FURNITURE_PAGES = 3
FOUND_PROPERTY = 'zenFound'

_installed = False


class Locator(NamedTuple):
    "A widget on a page, as it can be found again on the same page built afresh."

    kind: str  # its class name
    text: str  # its text, exactly as the widget has it
    nth: int  # 0 for the first widget of that kind and text on the page, and so on


def widget_text(w) -> str:
    "What a widget says on the page, or '' for one that says nothing we index."
    if isinstance(w, (QLabel, QAbstractButton)):
        return w.text()
    if isinstance(w, QGroupBox):
        return w.title()
    return ''


def worth_indexing(text: str) -> bool:
    "Words a person might search for: not empty, not an ellipsis button, not a lone symbol."
    return sum(ch.isalpha() for ch in match.plain(text)) >= 2


def headline(text: str) -> str:
    """
    A paragraph of help shortened to its first sentence, to show as a result;
    the whole of it is still searched (`Entry.also`).
    """
    if len(text) <= components.FINDER_HEADLINE:
        return text
    first = text.split('. ', 1)[0]
    if len(first) > components.FINDER_HEADLINE:
        first = first[: components.FINDER_HEADLINE].rsplit(' ', 1)[0]
    return first.rstrip('.:') + '…'


def on_page(w, page) -> bool:
    """
    Whether `w` is part of the page as it is shown, on whichever tab: not
    hidden by the page, and not in a dialog the page made ahead of time (Look &
    feel's colour editor), which a result could not take anyone to.

    Not `isVisibleTo`: a tab that is not the current one is hidden by its tab
    widget's stack, and every setting on it would be dropped.
    """
    if w.window() is not page.window():
        return False
    x = w
    while x is not None and x is not page:
        parent = x.parentWidget()
        if x.isHidden() and not isinstance(parent, QStackedWidget):
            return False
        x = parent
    return True


class Switch(NamedTuple):
    "One of the tabs or list entries that has to be chosen for a widget to show."

    name: str  # what the tab or the list row says
    select: Callable[[], None]


def _page_of(container, count: int, page_at, w) -> int:
    "Which of `container`'s `count` pages holds `w`, or -1."
    for i in range(count):
        holder = page_at(i)
        if holder is not None and (holder is w or holder.isAncestorOf(w)):
            return i
    return -1


def _list_driving(stack):
    """
    The list beside `stack` that chooses its page, if there is one: a view
    sharing its parent with one row per page. The conversion pages are made
    this way (`preferences/conversion.py`), a format list and its panels.
    """
    parent = stack.parentWidget()
    if parent is None:
        return None
    for view in parent.findChildren(QAbstractItemView, options=Qt.FindChildOption.FindDirectChildrenOnly):
        model = view.model()
        if model is not None and model.rowCount() == stack.count():
            return view
    return None


def switches_around(w, page) -> list[Switch]:
    """
    What has to be chosen on `page` for `w` to be in view, outermost first:
    each tab it is inside, and each panel of a list-and-panels layout.

    Each tab widget is asked which of its pages holds `w`, not with `indexOf`:
    calibre's ScrollingTabWidget (Look & feel) wraps each page in a scroll area
    and answers `indexOf` for the page inside it only. A panel is chosen through
    the list that drives it, so the two stay in step, as a click would leave them.
    """
    ans = []
    parent = w.parentWidget()
    while parent is not None and parent is not page.parentWidget():
        if isinstance(parent, QTabWidget):
            i = _page_of(parent, parent.count(), parent.widget, w)
            if i > -1:
                ans.append(Switch(match.plain(parent.tabText(i)), partial(parent.setCurrentIndex, i)))
        elif isinstance(parent, QStackedWidget) and not isinstance(parent.parentWidget(), QTabWidget):
            i = _page_of(parent, parent.count(), parent.widget, w)
            view = _list_driving(parent)
            if i > -1 and view is not None:
                index = view.model().index(i, 0)
                ans.append(Switch(match.plain(str(index.data() or ''), accelerators=False), partial(view.setCurrentIndex, index)))
            elif i > -1:
                ans.append(Switch('', partial(parent.setCurrentIndex, i)))
        parent = parent.parentWidget()
    return ans[::-1]


def tab_path(w, page) -> list[str]:
    "The names of the tabs and panels `w` is inside on `page`, outermost first."
    return [s.name for s in switches_around(w, page) if s.name]


def read_page(page, plugin, category_name: str) -> list[match.Entry]:
    "The entries for one built page: the page itself, then every widget that says something."
    icon = QIcon.ic(plugin.icon)
    target = (plugin.category, plugin.name, None)
    page_name = match.plain(plugin.gui_name, accelerators=False)
    entries = [
        match.Entry(
            title=page_name,
            where=match.path([match.plain(category_name, accelerators=False)]),
            also=' '.join((plugin.name, plugin.description or '', english.english(plugin.gui_name))),
            target=target,
            icon=icon,
        )
    ]
    seen: Counter = Counter()
    shown: set[str] = set()
    for w in page.findChildren(QWidget):
        raw = widget_text(w)
        if not raw:
            continue
        key = (type(w).__name__, raw)
        nth = seen[key]
        seen[key] += 1
        title = match.plain(raw)
        if not on_page(w, page) or not worth_indexing(raw) or title.casefold() in shown:
            continue
        shown.add(title.casefold())
        where = match.path([page_name, *tab_path(w, page)])
        tip = match.plain(w.toolTip())
        entries.append(
            match.Entry(
                title=headline(title),
                where=where,
                also=' '.join(x for x in (title, english.english(raw), tip, english.english(tip)) if x),
                target=(plugin.category, plugin.name, Locator(type(w).__name__, raw, nth)),
                icon=icon,
            )
        )
    for tw in page.findChildren(QTabWidget):
        if not on_page(tw, page):
            continue
        for i in range(tw.count()):
            text = tw.tabText(i)
            if worth_indexing(text) and match.plain(text).casefold() not in shown:
                shown.add(match.plain(text).casefold())
                entries.append(
                    match.Entry(
                        title=match.plain(text),
                        where=match.path([page_name, *tab_path(tw, page)]),
                        also=english.english(text),
                        target=(plugin.category, plugin.name, Locator('tab', text, i)),
                        icon=icon,
                    )
                )
    return entries


def find(page, locator: Locator):
    "The widget `locator` names on `page`, or None."
    if locator.kind == 'tab':
        for tw in page.findChildren(QTabWidget):
            if tw.tabText(locator.nth) == locator.text:
                return tw.widget(locator.nth)
        return None
    nth = 0
    for w in page.findChildren(QWidget):
        if type(w).__name__ == locator.kind and widget_text(w) == locator.text:
            if nth == locator.nth:
                return w
            nth += 1
    return None


def bring_forward(w, page) -> None:
    "Choose every tab and panel `w` is inside."
    for switch in switches_around(w, page):
        switch.select()
    # Look & feel drives its tabs from a list beside them; this is how calibre
    # itself tells a page its tab was chosen from outside (main.py, initial_plugin).
    try:
        page.initial_tab_changed()
    except Exception:
        pass


def mark(w, on: bool) -> None:
    "Light `w` up through the sheet (`25-finder.qss`), or put it back."
    w.setProperty(FOUND_PROPERTY, on)
    style = w.style()
    style.unpolish(w)
    style.polish(w)
    w.update()


def reveal(dialog, w) -> None:
    """
    Scroll `w` into view in every scroll area it is inside, focus it, and mark
    it. Called a turn of the event loop after the page opened, so the page may
    already have been closed again, and `w` with it.
    """
    if sip.isdeleted(w):
        return
    parent = w.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(w)
        parent = parent.parentWidget()
    target = w.buddy() if isinstance(w, QLabel) and w.buddy() is not None else w
    if target.focusPolicy() != Qt.FocusPolicy.NoFocus:
        target.setFocus(Qt.FocusReason.OtherFocusReason)
    mark(w, True)
    QTimer.singleShot(components.FINDER_MARK_MS, lambda: _unmark(w))


def _unmark(w) -> None:
    if not sip.isdeleted(w):  # the page may have been closed first, and the widget with it
        mark(w, False)


class PageIndex(QObject):
    """
    Every page's entries, read one page per turn of the event loop.

    One per run, per language and set of pages (`key()`); `changed` is emitted
    after each page so the results can grow while the rest are read.
    """

    changed = pyqtSignal()

    def __init__(self, gui):
        super().__init__(gui)
        from calibre.customize.ui import preferences_plugins

        self.gui = gui
        self.plugins = list(preferences_plugins())
        self.categories = {p.category: p.gui_category or p.category for p in self.plugins}
        self.entries: list[match.Entry] = []
        self.done = 0
        self.holder = None
        self.timer = QTimer(self)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.read_next)

    @staticmethod
    def key() -> tuple:
        from calibre.customize.ui import preferences_plugins
        from calibre.utils.localization import get_lang

        return (get_lang(), tuple((p.category, p.name) for p in preferences_plugins()))

    @property
    def finished(self) -> bool:
        return self.done >= len(self.plugins)

    def start(self) -> None:
        if not self.finished and not self.timer.isActive():
            self.timer.start()

    def read_next(self) -> None:
        if self.finished:
            self.timer.stop()
            return
        plugin = self.plugins[self.done]
        self.done += 1
        if self.holder is None:
            self.holder = QWidget()
        try:
            page = plugin.create_widget(self.holder)
            try:
                page.genesis(self.gui)
                page.do_on_child_tabs('genesis', self.gui)
                page.initialize()
                page.do_on_child_tabs('initialize')
                self.entries += read_page(page, plugin, self.categories.get(plugin.category, plugin.category))
            finally:
                page.setParent(None)
                page.deleteLater()
        except Exception:
            # A page that cannot be built off screen is left out of the
            # results; its name is still on the overview.
            traceback.print_exc()
        if self.finished:
            self.timer.stop()
            self.holder.deleteLater()
            self.holder = None
        self.changed.emit()

    def furniture(self) -> frozenset:
        "Titles that are on too many pages to say anything about any one of them."
        pages = Counter()
        for title, page in {(e.title.casefold(), e.target[:2]) for e in self.entries if e.target[2] is not None}:
            pages[title] += 1
        return frozenset(t for t, n in pages.items() if n >= FURNITURE_PAGES)

    def search(self, query: str) -> list[match.Entry]:
        skip = self.furniture()
        return match.rank((e for e in self.entries if e.title.casefold() not in skip), query)


_index: dict[tuple, PageIndex] = {}


def index_for(gui) -> PageIndex:
    "The run's index for the language and pages in use, made the first time it is asked for."
    key = PageIndex.key()
    ans = _index.get(key)
    if ans is None:
        ans = _index[key] = PageIndex(gui)
    return ans


class _EscapeClears(QObject):
    "Esc in a box with text in it empties the box, rather than closing the dialog."

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.KeyPress and ev.key() == Qt.Key.Key_Escape and obj.text():
            obj.clear()
            return True
        return False


class SettingsSearch(QObject):
    "The box, the results page and what choosing a result does, for one dialog."

    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.index = None

        self.field = QLineEdit(dialog.title_bar)
        self.field.setObjectName('zenFinderField')
        self.field.setPlaceholderText(_('Search settings'))
        self.field.setClearButtonEnabled(True)
        self.field.setFixedWidth(components.FINDER_FIELD_WIDTH)
        self.field.setToolTip(_('Find a setting by the words on its page, in English or in your language'))
        self.field.textChanged.connect(self.refresh)
        self.field.installEventFilter(_EscapeClears(self.field))
        dialog.title_bar.layout().addWidget(self.field)

        self.page = QWidget(dialog)
        self.page.setObjectName('zenSettingsResults')
        column = QVBoxLayout(self.page)
        column.setContentsMargins(0, 0, 0, 0)
        self.view = ResultsView(self.page)
        self.view.follow(self.field)
        self.view.chosen.connect(self.open)
        column.addWidget(self.view, 1)
        self.status = QLabel(self.page)
        self.status.setObjectName('zenFinderNone')
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(self.status)
        dialog.stack.insertWidget(RESULTS_PAGE, self.page)

        # The platform's Find key (Ctrl+F, Cmd+F) goes to the box, on the
        # overview only: a page may have a find of its own (Keyboard, Tweaks).
        self.find_key = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), dialog)
        self.find_key.activated.connect(self.focus)

    def set_shown(self, on: bool) -> None:
        "The box is the overview's: shown there and on the results, gone on a page."
        self.field.setVisible(on)
        self.find_key.setEnabled(on)

    def focus(self) -> None:
        self.field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.field.selectAll()

    def refresh(self, *args) -> None:
        text = self.field.text().strip()
        stack = self.dialog.stack
        if not text:
            if stack.currentIndex() == RESULTS_PAGE:
                stack.setCurrentIndex(0)
            return
        if self.index is None:
            self.index = index_for(self.dialog.gui)
            self.index.changed.connect(self.refresh)
            self.index.start()
        stack.setCurrentIndex(RESULTS_PAGE)
        found = self.index.search(text)
        current = self.view.current_entry()
        self.view.show_entries(found)
        if current is not None and current in found:
            # A page read while the person was choosing must not move their pick.
            self.view.setCurrentIndex(self.view.results.index(found.index(current)))
        self.view.setVisible(bool(found))
        if not self.index.finished:
            self.status.setText(_('Reading the settings pages… {0} of {1}').format(self.index.done, len(self.index.plugins)))
        elif not found:
            self.status.setText(_('No setting matches.'))
        self.status.setVisible(not self.index.finished or not found)

    def open(self, entry: match.Entry) -> None:
        from calibre.gui2.preferences import get_plugin

        category, name, locator = entry.target
        plugin = get_plugin(category, name)
        if plugin is None:
            return
        self.field.blockSignals(True)
        self.field.clear()
        self.field.blockSignals(False)
        self.set_shown(False)
        self.dialog.show_plugin(plugin)
        if self.dialog.stack.currentIndex() != 1:
            # The page refused to open (AbortInitialize): back to the overview.
            self.dialog.stack.setCurrentIndex(0)
            self.set_shown(True)
            return
        if locator is None:
            return
        page = self.dialog.showing_widget
        w = find(page, locator)
        if w is None:
            return
        bring_forward(w, page)
        # After the page has been laid out, or there is nothing to scroll to yet.
        QTimer.singleShot(0, lambda: reveal(self.dialog, w))


def install() -> bool:
    "Wrap the dialog's constructor and its way back to the overview. Safe to call twice."
    global _installed
    if _installed:
        return True
    from calibre.gui2.preferences.main import Preferences

    orig_init = Preferences.__init__
    orig_hide = Preferences.hide_plugin

    def __init__(self, gui, *args, **kwargs):
        orig_init(self, gui, *args, **kwargs)
        try:
            self.zen_settings_search = SettingsSearch(self)
            # A dialog opened straight onto a page has no overview to search.
            self.zen_settings_search.set_shown(self.stack.currentIndex() == 0)
        except Exception:
            # The dialog without the box is calibre's whole dialog.
            traceback.print_exc()

    def hide_plugin(self):
        ans = orig_hide(self)
        search = getattr(self, 'zen_settings_search', None)
        if search is not None:
            search.set_shown(True)
        return ans

    Preferences.__init__ = __init__
    Preferences.hide_plugin = hide_plugin
    _installed = True
    return True
