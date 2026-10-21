import importlib.util
import unittest


class BootstrapContract(unittest.TestCase):
    def test_platform_exposes_application_factory(self):
        self.assertIsNotNone(importlib.util.find_spec('server'), 'Missing project platform')
        from server.app import create_app
        self.assertTrue(callable(create_app))


if __name__ == '__main__':
    unittest.main()
