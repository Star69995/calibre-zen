#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Goodreads Updater and Book Cleanup, built in.

They began as Calibre plugins and are carried here so they are in every window
without installing anything. `install()` makes them calibre's own built-in
interface actions, without touching calibre's source: the same objects
`calibre.customize.builtins` lists.

Why this needs more than appending to that list: `calibre.customize.ui`
initialises its plugins when it is first imported, long before the overlay
installs, so a class added afterwards is never picked up by `interface_actions()`.
It is added to the list (so a later `initialize_plugins()`, after a plugin is
added or removed in Preferences, still has it) and initialised now.

A plugin of the same name that someone installed is dropped, as calibre does
at start-up for its own built-ins: the old zip of these two, from before they
were built in, must not give a second button.

This module stays light -- the Qt code is in actions.py, loaded when the window
makes its actions.
"""

from calibre.customize import InterfaceActionBase

_installed = False


class GoodreadsUpdaterBase(InterfaceActionBase):
    name = 'Goodreads Updater'
    description = 'Sets the #goodreads_linked yes/no column according to whether each book has a goodreads identifier'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Star'
    version = (1, 1, 0)
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = 'calibre_zen.books.actions:GoodreadsUpdaterAction'


class BookCleanupBase(InterfaceActionBase):
    name = 'Book Cleanup'
    description = 'Fixes PDF-converted EPUBs: chapter headings and blank pages, broken paragraphs, spacing around punctuation and dashes'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Star'
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)

    actual_plugin = 'calibre_zen.books.actions:BookCleanupAction'


PLUGINS = (GoodreadsUpdaterBase, BookCleanupBase)


def register(plugin_classes=PLUGINS) -> list[str]:
    """
    Make `plugin_classes` calibre built-ins, initialised now. Returns the names
    newly added; a class already registered is left alone.
    """
    from calibre.customize import ui as plugin_ui
    from calibre.customize.builtins import plugins as builtin_plugins

    added = []
    for cls in plugin_classes:
        if cls in builtin_plugins:
            continue
        # An installed plugin of this name loses, whether it was initialised
        # at import or is only recorded in the config for the next start. Only
        # the record goes: `remove_plugin` would also delete the zip it names,
        # and that can be a file in calibre's own settings folder.
        plugin_ui._initialized_plugins[:] = [p for p in plugin_ui._initialized_plugins if p.name != cls.name]
        installed = plugin_ui.config['plugins']
        if cls.name in installed:
            installed.pop(cls.name)
            plugin_ui.config['plugins'] = installed
        builtin_plugins.append(cls)
        plugin_ui._initialized_plugins.append(plugin_ui.initialize_plugin(cls))
        added.append(cls.name)
    if added:
        plugin_ui.builtin_names = frozenset(p.name for p in builtin_plugins)
        plugin_ui._initialized_plugins.sort(key=lambda p: p.priority, reverse=True)
    return added


def install() -> bool:
    "Register the two actions. Safe to call twice."
    global _installed
    if _installed:
        return True
    register()
    _installed = True
    return True
