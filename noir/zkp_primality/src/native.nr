// Primality steps for numbers below 2^64, over u128 so that a * b never overflows.

// Primes <= 251.  Any n < 65536 = 256^2 with no divisor in this list is prime.
global SMALL_PRIMES: [u128; 54] = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
    101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193,
    197, 199, 211, 223, 227, 229, 233, 239, 241, 251,
];

// n is prime, n in [256, 2^16).  Deterministic: trial division by every prime <= 251.
pub fn assert_prime_below_2_16(n: u128) {
    assert(n >= 256);
    assert(n < 65536);
    for i in 0..54 {
        assert(n % SMALL_PRIMES[i] != 0);
    }
}

// base^e mod n, e given as B little-endian bits.  Requires 1 < n < 2^64 and base < n.
pub fn modexp_bits<let B: u32>(base: u128, bits: [bool; B], n: u128) -> u128 {
    let mut r: u128 = 1;
    for j in 0..B {
        let i = B - 1 - j;
        let sq = (r * r) % n;
        let m = (sq * base) % n;
        r = if bits[i] { m } else { sq };
    }
    r
}

// One Pocklington step: n is prime, GIVEN that the number f is prime.
//
//   f^2 > n   and   there is y with   y^f = 1 (mod n)   and   gcd(y - 1, n) = 1.
//
// Why that suffices: for any prime p | n, y mod p is not 1 (since y - 1 is invertible) but has
// y^f = 1, so its order is exactly f (f is prime), hence f | p - 1 and p > f > sqrt(n).  This
// holds for EVERY prime factor of n, so n has a single prime factor: n is prime.  (n - 1 = f * e
// and a base a are only needed by the prover to find y = a^e; the circuit does not need them.)
// `inv` is the witness inverse of y - 1 (it proves gcd(y - 1, n) = 1).
pub fn pocklington_step<let FB: u32>(n: u128, f: u128, y: u128, inv: u128) {
    assert(FB <= 63);
    assert(n >= 3);
    assert(n < 18446744073709551616); // n < 2^64, so every product of residues fits u128
    let fbits: [bool; FB] = (f as Field).to_le_bits(); // also proves f < 2^FB
    assert(f * f > n);
    assert(y < n);
    assert(inv < n);

    let z = modexp_bits(y, fbits, n);
    assert(z == 1);

    let y_minus_1 = (y + n - 1) % n;
    assert((y_minus_1 * inv) % n == 1);
}
