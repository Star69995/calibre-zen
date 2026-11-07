#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Star

"""
The two search boxes, finder/: the matching rule they share, the English behind
a Hebrew label, and where Find an action goes on a toolbar. The boxes in the
real window and in Preferences are driven in test_gui.
"""

from calibre_zen import finder
from calibre_zen.finder import match
from calibre_zen.tests.base import ZenTestCase


def entry(title, where='', also=''):
    return match.Entry(title=title, where=where, also=also, target=title)


class TestMatch(ZenTestCase):
    def test_plain_drops_accelerators_and_tags_but_keeps_a_literal_ampersand(self):
        self.assertEqual(match.plain('&Save to disk'), 'Save to disk')
        self.assertEqual(match.plain('Look && feel'), 'Look & feel')
        self.assertEqual(match.plain('<p>Two\n  <b>lines</b>'), 'Two lines')
        self.assertEqual(match.plain('Look & feel', accelerators=False), 'Look & feel')

    def test_every_word_has_to_be_somewhere(self):
        entries = [entry('Hide column', 'Columns'), entry('Show column')]
        self.assertEqual([e.title for e in match.rank(entries, 'column hide')], ['Hide column'])
        self.assertEqual(match.rank(entries, 'colour'), [])

    def test_a_title_that_starts_with_the_query_comes_first(self):
        entries = [entry('Bulk convert'), entry('Input options', also='convert'), entry('Convert books'), entry('Reconvert')]
        self.assertEqual([e.title for e in match.rank(entries, 'conv')], ['Convert books', 'Bulk convert', 'Reconvert', 'Input options'])

    def test_the_place_and_the_english_name_are_searched_too(self):
        entries = [entry('המר ספרים', also='Convert books'), entry('Fonts', where='Look & feel')]
        self.assertEqual([e.title for e in match.rank(entries, 'convert')], ['המר ספרים'])
        self.assertEqual([e.title for e in match.rank(entries, 'feel')], ['Fonts'])

    def test_a_path_keeps_each_part_in_its_own_direction(self):
        where = match.path(['מראה ותחושה', 'Tag browser', '', 'Display'])
        self.assertEqual(where.count(match.FSI), 3, 'every part isolated, an empty one dropped')
        self.assertEqual(match.unisolated(where), 'מראה ותחושה › Tag browser › Display')
        self.assertEqual(len(match.rank([entry('Show tooltips', where)], 'browser display')), 1)

    def test_case_and_accelerators_do_not_matter(self):
        self.assertEqual(len(match.rank([entry('&Edit metadata')], 'EDIT META')), 1)

    def test_an_empty_query_keeps_everything_in_order(self):
        entries = [entry('B'), entry('A')]
        self.assertEqual(match.rank(entries, '  '), entries)


class TestEnglish(ZenTestCase):
    def test_a_hebrew_label_is_found_by_its_english(self):
        from calibre_zen.finder import english

        # The run is in English, so Hebrew's table is read directly.
        table = english._load('he')
        self.assertEqual(table.get('המר ספרים'), 'Convert books', "calibre's own catalog")
        self.assertEqual(table.get('חפש פעולה'), 'Find an action', "this fork's locales/he.po")

    def test_english_needs_no_table(self):
        from calibre_zen.finder import english

        self.assertEqual(english.table(), {})


class TestToolbarPlace(ZenTestCase):
    def test_the_button_goes_at_the_end_after_a_separator_once(self):
        self.assertEqual(finder.with_button(('Add Books', 'Preferences')), ('Add Books', 'Preferences', None, finder.ACTION_NAME))
        once = finder.with_button(('Add Books',))
        self.assertEqual(finder.with_button(once), once)

    def test_an_arranged_toolbar_gets_it_once_and_a_removal_sticks(self):
        from calibre.gui2 import gprefs

        saved = {k: gprefs.get(k) for k in (finder.OFFERED_KEY, finder.TOOLBAR_KEY)}

        def restore():
            for k, v in saved.items():
                if v is None:
                    gprefs.pop(k, None)
                else:
                    gprefs[k] = v

        self.addCleanup(restore)
        gprefs.pop(finder.OFFERED_KEY, None)
        gprefs[finder.TOOLBAR_KEY] = ['Add Books', 'Preferences']
        self.assertTrue(finder.offer_once())
        self.assertEqual(list(gprefs[finder.TOOLBAR_KEY]), ['Add Books', 'Preferences', None, finder.ACTION_NAME])
        gprefs[finder.TOOLBAR_KEY] = ['Add Books', 'Preferences']
        self.assertFalse(finder.offer_once(), 'taken off once, it stays off')
        self.assertEqual(list(gprefs[finder.TOOLBAR_KEY]), ['Add Books', 'Preferences'])

    def test_it_is_part_of_the_run_at_the_far_end(self):
        from calibre_zen import hooks
        from calibre_zen.theme import appearance

        self.assertIn(finder.ACTION_NAME, appearance.TRAILING)
        self.assertIn(finder.ACTION_NAME, hooks.TOOLBAR_ADDITIONS)


class TestSettingsWords(ZenTestCase):
    def test_what_is_worth_indexing(self):
        from calibre_zen.finder import settings

        self.assertTrue(settings.worth_indexing('&Job priority:'))
        self.assertFalse(settings.worth_indexing('...'))
        self.assertFalse(settings.worth_indexing('&X'))

    def test_a_paragraph_is_shown_by_its_first_sentence(self):
        from calibre_zen.finder import settings

        para = 'Set a pattern to guess metadata from file names. ' + 'More words follow here. ' * 10
        self.assertEqual(settings.headline(para), 'Set a pattern to guess metadata from file names…')
        self.assertEqual(settings.headline('Short label:'), 'Short label:')
