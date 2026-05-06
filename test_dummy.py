import unittest
import os # Unused import

# TODO: Add more edge cases to the math tests

def complex_function(a, b, c):
    if a > 0:
        if b > 0:
            if c > 0:
                return a + b + c
            else:
                return a + b
        else:
            return a
    else:
        return 0

def missing_docstring_function():
    """Fixed: Added missing docstring."""
    return "I have no docstring"

class TestDummy(unittest.TestCase):
    def test_math(self):
        self.assertEqual(1 + 1, 2)
    
    def test_complex(self):
        self.assertEqual(complex_function(1, 2, 3), 6)

if __name__ == '__main__':
    unittest.main()
