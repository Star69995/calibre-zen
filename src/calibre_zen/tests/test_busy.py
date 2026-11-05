#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Settings that open while jobs run (busy.py): which page is held back and why,
and the one question calibre asks at the door.
"""

from calibre_zen import busy
from calibre_zen.tests.base import ZenTestCase


class Job:
    "What the overlay reads of a calibre job."

    WAITING, RUNNING = 0, 1

    def __init__(self, description='', percent=0, running=True):
        self.description = description
        self.percent = percent
        self.is_running = running
        self.is_finished = False
        self.run_state = self.RUNNING if running else self.WAITING
        self.status_text = 'Working...' if running else 'Waiting...'
        self.duration = None


class Manager:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)

    def unfinished_jobs(self):
        return self.jobs

    def has_jobs(self):
        return any(j.is_running for j in self.jobs)


def page(module, **attrs):
    "A stand-in for a Preferences page living in calibre.gui2.preferences.<module>."
    return type('ConfigWidget', (), {'__module__': 'calibre.gui2.preferences.' + module, **attrs})()


class TestWhichPageWaits(ZenTestCase):
    def test_an_ordinary_page_does_not_clash(self):
        self.assertEqual(busy.clash_reason(page('look_feel')), '')
        self.assertEqual(busy.clash_reason(page('toolbar')), '')

    def test_the_plugins_page_clashes_and_says_why(self):
        self.assertIn('plugin', busy.clash_reason(page('plugins')))

    def test_a_page_that_needs_a_restart_clashes_without_being_listed(self):
        self.assertNotIn('columns', busy.CLASHES)
        self.assertIn('restart', busy.clash_reason(page('columns', restart_critical=True)))


class TestTheNotice(ZenTestCase):
    def test_it_names_the_jobs_and_how_far_they_have_got(self):
        text = busy.message('Why.', [Job('Convert A', 40), Job('Send B')])
        self.assertTrue(text.startswith('Why.'))
        self.assertIn('Convert A (40%)', text)
        self.assertIn('Send B', text)
        self.assertNotIn('Send B (', text)

    def test_a_long_list_is_cut_and_the_rest_counted(self):
        text = busy.message('Why.', [Job(f'job {i}') for i in range(8)], limit=5)
        self.assertIn('job 4', text)
        self.assertNotIn('job 5', text)
        self.assertIn('3', text.splitlines()[-1])

    def test_a_job_with_no_description_still_has_a_line(self):
        self.assertTrue(busy.describe(Job('')))

    def test_only_running_jobs_are_listed(self):
        manager = Manager([Job('a'), Job('b', running=False)])
        self.assertEqual([j.description for j in busy.running_jobs(manager)], ['a'])


class TestTheDoor(ZenTestCase):
    def test_the_next_question_is_answered_no_and_the_one_after_is_true_again(self):
        manager = Manager([Job('Convert')])
        self.assertTrue(manager.has_jobs())
        busy.open_once(manager)
        self.assertFalse(manager.has_jobs())
        self.assertTrue(manager.has_jobs())
