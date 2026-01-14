import unittest

from src.lattix.utils import exceptions


class TestErrors(unittest.TestCase):
    def test_error_all(self):
        for name in exceptions.__all__:
            self.assertTrue(hasattr(exceptions, name), f"Missing export: {name}")
        # print("All exports present.")
