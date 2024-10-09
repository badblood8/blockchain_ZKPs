import random
import unittest

def lehmann_primality_test(n, k=5):
    """
    Lehmann primality test.

    Args:
        n (int): Number to be tested for primality.
        k (int): Number of iterations (default is 5). More iterations increase the accuracy.

    Returns:
        bool: True if n is probably prime, False if n is composite.
    """
    # 1 is not prime
    if n == 1:
        return False
    # Small primes are prime
    if n in (2, 3):
        return True
    # Eliminate even numbers
    if n % 2 == 0:
        return False
    
    # Perform k iterations
    for _ in range(k):
        # Pick a random integer a in the range [2, n-2]
        a = random.randint(2, n - 2)
        # Compute a^(n-1)/2 % n
        result = pow(a, (n - 1) // 2, n)
        
        # If result is neither 1 nor n-1, n is composite
        if result != 1 and result != n - 1:
            return False
    
    # If all iterations passed, n is probably prime
    return True


class TestLehmannPrimalityTest(unittest.TestCase):
    def test_small_primes(self):
        self.assertTrue(lehmann_primality_test(2))
        self.assertTrue(lehmann_primality_test(3))
        self.assertTrue(lehmann_primality_test(5))
        self.assertTrue(lehmann_primality_test(7))
    
    def test_small_composites(self):
        self.assertFalse(lehmann_primality_test(4))
        self.assertFalse(lehmann_primality_test(6))
        self.assertFalse(lehmann_primality_test(9))
        self.assertFalse(lehmann_primality_test(12))
    
    def test_large_primes(self):
        self.assertTrue(lehmann_primality_test(101))
        self.assertTrue(lehmann_primality_test(199))
        self.assertTrue(lehmann_primality_test(997))
    
    def test_large_composites(self):
        self.assertFalse(lehmann_primality_test(100))
        self.assertFalse(lehmann_primality_test(200))
        self.assertFalse(lehmann_primality_test(1001))
    
    def test_non_primes(self):
        # Known composite numbers like Carmichael numbers
        self.assertFalse(lehmann_primality_test(561))  # Carmichael number
        self.assertFalse(lehmann_primality_test(1105))  # Carmichael number
    
    def test_performance(self):
        self.assertTrue(lehmann_primality_test(982451653))  # Large prime
        self.assertFalse(lehmann_primality_test(982451654))  # Large composite


if __name__ == '__main__':
    unittest.main()
