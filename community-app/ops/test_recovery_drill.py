"""Safety checks for the opt-in, clone-only recovery drill."""
import os
import unittest
from unittest.mock import patch
from recovery_drill import guard


class RecoveryGuardTests(unittest.TestCase):
    base = {
        'RECOVERY_DRILL': '1',
        'MYSQL_HOST': 'dbod-ernest-community-clone-20260912230201.cern.ch',
        'MYSQL_PORT': '5546',
        'RECOVERY_EXPECTED_HOST': 'dbod-ernest-community-clone-20260912230201.cern.ch',
        'RECOVERY_EXPECTED_PORT': '5546',
    }

    def test_explicit_clone_allowed(self):
        with patch.dict(os.environ, self.base, clear=True):
            guard()

    def test_unsafe_configuration_rejected(self):
        for change in (
            {'RECOVERY_DRILL': '0'},
            {'MYSQL_HOST': 'dbod-ernest-community.cern.ch',
             'RECOVERY_EXPECTED_HOST': 'dbod-ernest-community.cern.ch'},
            {'MYSQL_PORT': '5557', 'RECOVERY_EXPECTED_PORT': '5557'},
            {'MYSQL_PORT': '3306'},
            {'EMAIL_HOST_PASSWORD': 'synthetic-test-only'},
            {'RECOVERY_EXPECTED_HOST': ''},
            {'MYSQL_HOST': 'dbod-gc006.cern.ch', 'RECOVERY_EXPECTED_HOST': 'dbod-gc006.cern.ch'},
        ):
            with self.subTest(change=change), patch.dict(os.environ, {**self.base, **change}, clear=True):
                with self.assertRaises(RuntimeError):
                    guard()


if __name__ == '__main__':
    unittest.main()
