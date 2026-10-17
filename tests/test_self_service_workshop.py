import unittest
from unittest.mock import Mock
from self_service_workshop import accepted, run, PROFILES


class WorkshopTests(unittest.TestCase):
    def test_stops_after_pass(self):
        evaluate = Mock(return_value={'passed': True, 'profile': PROFILES[0]})
        report = run(evaluate)
        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(report['state'], 'candidate_ready')
        self.assertFalse(report['production_changed'])

    def test_tries_smaller_candidate_after_failure(self):
        evaluate = Mock(side_effect=[{'passed': False, 'profile': PROFILES[0]},
                                     {'passed': True, 'profile': PROFILES[1]}])
        self.assertEqual(run(evaluate)['candidate'], PROFILES[1])

    def test_failures_never_promote(self):
        report = run(lambda p: {'passed': False, 'profile': p})
        self.assertEqual(report['state'], 'blocked')
        self.assertIsNone(report['candidate'])
        self.assertEqual(len(report['attempts']), 2)

    def test_answer_check_requires_whole_token(self):
        self.assertTrue(accepted('42', '42'))
        self.assertFalse(accepted('142', '42'))
        self.assertFalse(accepted('', 'clara'))
