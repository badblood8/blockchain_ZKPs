import random
import unittest

def rabin_miller_primality_test(n, k=10):
    if n <= 1:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    r, d = 0, n - 1
    while d % 2 == 0:
        d //= 2
        r += 1

    for _ in range(k):
        a = random.randint(2, n - 2)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


class TestRabinMillerPrimalityTest(unittest.TestCase):
    def test_small_primes(self):
        self.assertTrue(rabin_miller_primality_test(2))
        self.assertTrue(rabin_miller_primality_test(3))
        self.assertTrue(rabin_miller_primality_test(5))
        self.assertTrue(rabin_miller_primality_test(7))
        self.assertTrue(rabin_miller_primality_test(11))

    def test_small_composites(self):
        self.assertFalse(rabin_miller_primality_test(4))
        self.assertFalse(rabin_miller_primality_test(6))
        self.assertFalse(rabin_miller_primality_test(8))
        self.assertFalse(rabin_miller_primality_test(9))
        self.assertFalse(rabin_miller_primality_test(10))

    def test_large_primes(self):
        self.assertTrue(rabin_miller_primality_test(101))
        self.assertTrue(rabin_miller_primality_test(103))
        self.assertTrue(rabin_miller_primality_test(199))
        self.assertTrue(rabin_miller_primality_test(997))
        self.assertTrue(rabin_miller_primality_test(982451653))  # Large prime

    def test_large_composites(self):
        self.assertFalse(rabin_miller_primality_test(100))
        self.assertFalse(rabin_miller_primality_test(102))
        self.assertFalse(rabin_miller_primality_test(200))
        self.assertFalse(rabin_miller_primality_test(1001))
        self.assertFalse(rabin_miller_primality_test(982451654))  # Large composite

    def test_special_composites(self):
        self.assertFalse(rabin_miller_primality_test(561))   # Carmichael number
        self.assertFalse(rabin_miller_primality_test(1105))  # Carmichael number
        self.assertFalse(rabin_miller_primality_test(1729))  # Carmichael number
        self.assertFalse(rabin_miller_primality_test(2465))  # Carmichael number
        self.assertFalse(rabin_miller_primality_test(6601))  # Carmichael number

    def test_very_large_primes(self):
        # 20-digit known large primes
        self.assertTrue(rabin_miller_primality_test(1031577516580419144125541136857407098405418233335121395712519))  # Example large prime
        self.assertTrue(rabin_miller_primality_test(1094162694805624007639577885987470218368391086996193201922299))  # Example large prime
        self.assertTrue(rabin_miller_primality_test(1128346382651093976551729960465893580305556728456980302027071))  # Example large prime
        self.assertTrue(rabin_miller_primality_test(919890957903935253868784939341778764363353748211104963976303)) # Example large prime
        self.assertTrue(rabin_miller_primality_test(1536948723419419809754503920373191315856923885015301957250459)) # Example large prime

    def test_very_large_composites(self):
        # 20-digit large composites
        self.assertFalse(rabin_miller_primality_test(11111111111111111110))  # Example large composite
        self.assertFalse(rabin_miller_primality_test(99999999999999999950))  # Example large composite
        self.assertFalse(rabin_miller_primality_test(100000000000000000002)) # Example large composite
        self.assertFalse(rabin_miller_primality_test(100000000000000000004)) # Example large composite
        self.assertFalse(rabin_miller_primality_test(100000000000000000005)) # Example large composite


if __name__ == '__main__':
    unittest.main()
