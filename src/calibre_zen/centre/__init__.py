#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The centre pane: a preview above the book list, a strip between them, and the
list itself rebuilt as a modern table.

The second piece of the overlay that is not styling, and it follows the shape
`filters/` established: calibre's widget keeps its model, its signals and its
behaviour, and the overlay changes only what is drawn and where things sit.

The wraps below, all from outside, no upstream file edited:

`CentralContainer.initialize_with_gui`
    The centre is handed to the container exactly once, as one opaque widget
    (`central.py:423`). We hand it our wrapper around that widget instead.
    `gui.stack` keeps its identity, so everything that addresses it by index
    keeps working.

`BooksView.get_old_state` / `BooksView.write_state`
    The only two methods that name the per-library column-layout pref
    (`views.py:1001, 1127`). Pointed at a key of our own, so the overlay's
    layout persists normally and the reader's own is frozen exactly as they
    left it. On the first run the arrangement is folded into the state dict
    that `apply_state` is about to apply, which is why nothing here ever calls
    `setSectionHidden` or `moveSection` itself.

`BooksView.database_changed`
    Runs `set_delegates` -> `restore_state` -> `set_ondevice_column_visibility`
    on startup and on every library switch (`views.py:1285-1291`), so it is the
    one correct place to point the cover cache and the preview at the new
    database.

`BooksView.do_row_sizing`
    Row height is the vertical header's, not the delegate's `sizeHint`
    (`views.py:1196-1210`), and the model caches it. The height is the reader's
    choice -- see rows.py.

`DeviceBooksView.set_database` / `get_old_state` / `write_state`, and
`DeviceBooksModel.headerData` / `get_book_display_info`
    A device's list is drawn around Details too -- see device.py. The same
    delegates, the same arrangement under a key of our own, the same header, and
    the Book details panel given the linked library book's cover and metadata.

`TableView.set_delegates`
    Let calibre assign its delegates, then wrap each one. Editing, sorting,
    resizing and the column-header menu are untouched -- only `paint` and
    `sizeHint` are ours.

`BooksModel.headerData`
    One string: the title column's header reads "Details".

`CoverDelegate.set_dimensions`, and the grid's cover cache
    Wrapped -- see grid.py. Three tile densities on top of whatever size
    calibre works out, chosen from the view switcher's menu; and every
    thumbnail cropped to the tile's shape, so a shelf of covers has one edge
    rather than a ragged one -- or, from the same menu, each cover whole and
    standing on the tile's floor.

`CoverDelegate.paint` / `paint_cover` / `helpEvent`
    Wrapped -- see tiles.py. A ring around the cover under the pointer, and a
    card above the tile carrying the title, its year, the author and the
    series, in place of calibre's own tooltip for that view.

Off with `CALIBRE_ZEN_CENTRE=0`, which gives back calibre's centre exactly --
the search bar back in its own strip, the book list with the reader's own
columns, no preview.

`doubleclick_on_library_view`'s default
    Changed, not overridden -- see clicks.py. A double-click edits the cell,
    and the slow second click that used to is gone. Preferences -> Tweaks
    still sets it either way.

**Known gaps.** The reference's "Add column" pill is not built -- calibre's
column-header context menu already does that job.
"""

from calibre_zen import features

_installed = False


def enabled() -> bool:
    return features.enabled('centre')


def install() -> bool:
    """
    Wrap the methods above. Safe to call twice.

    Must not run before there is a QApplication, for the same reason
    `filters.install()` must not -- importing calibre's library views pulls in
    modules that evaluate `QIcon.ic()` at import time.
    """
    global _installed
    if _installed or not enabled():
        return _installed
    from qt.core import Qt

    from calibre.gui2 import gprefs, qapplication_or_fail
    from calibre.gui2.central import CentralContainer
    from calibre.gui2.library.models import BooksModel, DeviceBooksModel
    from calibre.gui2.library.views import BooksView, DeviceBooksView
    from calibre.gui2.pin_columns import TableView
    from calibre_zen.centre import clicks, device, grid, rows, table, tiles
    from calibre_zen.centre.layout import ZenCentre

    orig_initialize = CentralContainer.initialize_with_gui
    orig_get_old_state = BooksView.get_old_state
    orig_write_state = BooksView.write_state
    orig_database_changed = BooksView.database_changed
    orig_do_row_sizing = BooksView.do_row_sizing
    orig_set_delegates = TableView.set_delegates
    orig_header_data = BooksModel.headerData
    orig_device_header_data = DeviceBooksModel.headerData
    orig_device_display_info = DeviceBooksModel.get_book_display_info
    orig_device_set_database = DeviceBooksView.set_database
    orig_device_get_old_state = DeviceBooksView.get_old_state
    orig_device_write_state = DeviceBooksView.write_state

    def state_key(view) -> str:
        name = str(view.objectName())
        return '' if not name else table.STATE_KEY_PREFIX + name + ' books view state'

    def initialize_with_gui(self, gui, book_list_widget):
        try:
            centre = ZenCentre(gui, book_list_widget, self)
        except Exception:
            # Losing the wrapper costs the preview and the strip. Losing the
            # centre costs the window, so fall back to calibre's own.
            import traceback

            traceback.print_exc()
            return orig_initialize(self, gui, book_list_widget)
        gui.zen_centre = centre
        try:
            grid.attach(gui)
            tiles.attach(gui)
        except Exception:
            import traceback

            traceback.print_exc()
        return orig_initialize(self, gui, centre)

    def get_old_state(self):
        key = state_key(self)
        db = getattr(self.model(), 'db', None)
        if not key or db is None:
            return orig_get_old_state(self)
        ans = db.new_api.pref(key)
        if ans is not None:
            return ans
        # First run with the overlay on: start from whatever layout the reader
        # already had -- letting the original run also does its gprefs-to-db
        # migration and its injected-column bookkeeping -- and fold the Details
        # arrangement into it.
        return table.arrange(orig_get_old_state(self) or self.get_default_state(), self.column_map)

    def write_state(self, state):
        key = state_key(self)
        db = getattr(self.model(), 'db', None)
        if not key or db is None:
            return orig_write_state(self, state)
        db.new_api.set_pref(key, state)

    def database_changed(self, db):
        ans = orig_database_changed(self, db)
        if not self.is_library_view:
            return ans
        try:
            from calibre.gui2.ui import get_gui

            table.cover_cache().set_database(self._model.db)
            table.setup_view(self)
            table.repaint_on_render(self)
            gui = get_gui()
            centre = None if gui is None else getattr(gui, 'zen_centre', None)
            if centre is not None:
                centre.attach()
        except Exception:
            import traceback

            traceback.print_exc()
        return ans

    def do_row_sizing(self):
        ans = orig_do_row_sizing(self)
        for view in (self, self.pin_view) if self.is_library_view else (self,):
            rows.size(view)
        return ans

    def set_delegates(self):
        ans = orig_set_delegates(self)
        table.wrap_delegates(self)
        return ans

    def device_set_database(self, db):
        ans = orig_device_set_database(self, db)
        try:
            table.setup_view(self)
            table.wrap_delegates(self)
            table.repaint_on_render(self)
            rows.size(self)
        except Exception:
            import traceback

            traceback.print_exc()
        return ans

    def device_get_old_state(self):
        key = state_key(self)
        ans = gprefs.get(key) if key else None
        if ans is not None:
            return ans
        # As for the library: start from the layout the reader had, with the
        # Details arrangement folded in, under a key of our own.
        return table.arrange(orig_device_get_old_state(self) or self.get_default_state(), self.column_map)

    def device_write_state(self, state):
        key = state_key(self)
        if not key:
            return orig_device_write_state(self, state)
        gprefs.set(key, state)

    def device_book_display_info(self, idx):
        info = orig_device_display_info(self, idx)
        try:
            link = device.linked(self.db[self.map[idx]])
            if link is not None:
                device.fill_from_library(info, link)
        except Exception:
            import traceback

            traceback.print_exc()
        return info

    def details_header(orig):
        "`orig` with the Details column's header, for the library's model and a device's both."

        def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
            if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
                try:
                    if self.column_map[section] == table.DETAILS_COLUMN:
                        return _('Details')
                except IndexError, AttributeError:
                    pass
            return orig(self, section, orientation, role)

        return headerData

    grid.install()
    tiles.install()
    clicks.install()

    def repaint_for_palette():
        "Everything the overlay draws by hand in the centre, re-inked."
        from calibre.gui2.ui import get_gui

        table.forget_colors()
        gui = get_gui()
        centre = None if gui is None else getattr(gui, 'zen_centre', None)
        if centre is not None:
            centre.refresh_palette()
        view = None if gui is None else getattr(gui, 'library_view', None)
        if view is not None:
            view.viewport().update()
        # The cover grid's rings are ours too, and so is the hover card.
        grid_view = None if gui is None else getattr(gui, 'grid_view', None)
        if grid_view is not None:
            grid_view.viewport().update()

    qapplication_or_fail().palette_changed.connect(repaint_for_palette, type=Qt.ConnectionType.QueuedConnection)

    try:
        CentralContainer.initialize_with_gui = initialize_with_gui
        BooksView.get_old_state = get_old_state
        BooksView.write_state = write_state
        BooksView.database_changed = database_changed
        BooksView.do_row_sizing = do_row_sizing
        TableView.set_delegates = set_delegates
        BooksModel.headerData = details_header(orig_header_data)
        DeviceBooksModel.headerData = details_header(orig_device_header_data)
        DeviceBooksModel.get_book_display_info = device_book_display_info
        DeviceBooksView.set_database = device_set_database
        DeviceBooksView.get_old_state = device_get_old_state
        DeviceBooksView.write_state = device_write_state
    except AttributeError, TypeError:
        return False
    _installed = True
    return True
