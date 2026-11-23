// Zero-knowledge proof of knowledge of the factorisation N = p * q into two distinct
// 256-bit PRIMES, without revealing p or q.
//
//   public : N  (a 512-bit number, as 5 limbs of 120 bits)
//   private: p, q (256-bit each) and a deterministic primality chain for each
//
// What the verifier learns: N is a product of two distinct 256-bit primes.
use bignum::{BigNum, U512};
use zkp_primality::chain256::{assert_prime_256, Chain256};

// Zero-extend 3 limbs into a U512 (modulus 2^512: products of two 256-bit values are exact).
fn to_u512(l: [u128; 3]) -> U512 {
    U512::from_limbs([l[0], l[1], l[2], 0, 0])
}

fn main(n: pub [u128; 5], p: [u128; 3], q: [u128; 3], cp: Chain256, cq: Chain256) {
    // p and q are prime (each is exactly 256 bits, checked inside the chain)
    assert_prime_256(p, cp);
    assert_prime_256(q, cq);

    // N = p * q as exact integers:  N < 2^512 (limb 4 has 32 bits) and U512 holds the true product
    assert(n[4] < 4294967296);
    assert(to_u512(p) * to_u512(q) == U512::from_limbs(n));

    // distinct primes (N is not a square)
    assert((p[0] != q[0]) | (p[1] != q[1]) | (p[2] != q[2]));
}
