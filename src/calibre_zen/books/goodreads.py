#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
Keep the yes/no column `#goodreads_linked` in step with the `goodreads`
identifier: yes if a book has one, no if it does not.

No Qt, and it works on calibre's `new_api`, so it can be tested on a throwaway
library without a window.
"""

LINKED_COLUMN = '#goodreads_linked'
LINKED_COLUMN_HEADING = 'Goodreads linked'
IDENTIFIER_TYPE = 'goodreads'


class MissingColumnError(Exception):
    """The library has no `#goodreads_linked` column; `create_linked_column` can make it."""


class WrongColumnTypeError(Exception):
    """`#goodreads_linked` exists but is not yes/no; it cannot be replaced from here."""


def create_linked_column(db) -> None:
    """
    Add the yes/no column `#goodreads_linked` to the library. `db` is calibre's
    new_api Cache.

    Calibre reads its columns when a library is opened, so the column cannot be
    filled until calibre is restarted.
    """
    db.create_custom_column(LINKED_COLUMN.removeprefix('#'), LINKED_COLUMN_HEADING, 'bool', False)


def update_goodreads_linked(db) -> tuple[set[int], int]:
    """
    Set the #goodreads_linked column of every book to whether it has a
    goodreads identifier. `db` is calibre's new_api Cache.

    Only books whose value actually changes are written.
    Returns (changed_ids, total_books).
    """
    meta = db.field_metadata.get(LINKED_COLUMN)
    if meta is None:
        raise MissingColumnError(_("The library has no column with the lookup name '{0}'.").format(LINKED_COLUMN))
    if meta['datatype'] != 'bool':
        raise WrongColumnTypeError(
            _("The library's column '{0}' is not a yes/no column.\nRename it under Preferences → Add your own columns, then run this again.").format(
                LINKED_COLUMN
            )
        )

    all_ids = db.all_book_ids()
    identifiers = db.all_field_for('identifiers', all_ids)
    current = db.all_field_for(LINKED_COLUMN, all_ids)

    changes = {}
    for book_id in all_ids:
        linked = bool(identifiers.get(book_id, {}).get(IDENTIFIER_TYPE))
        if current.get(book_id) is not linked:
            changes[book_id] = linked

    if changes:
        db.set_field(LINKED_COLUMN, changes)
    return set(changes), len(all_ids)
