// Zero-knowledge proof that the PUBLIC 256-bit number n is prime, by a Pocklington chain
//     n256 <- n128 <- n64 <- n32 <- n16 (trial division)
// where every lower level is a private witness.  Deterministic: no error probability.
use zkp_primality::native::{assert_prime_below_2_16, pocklington_step};
use zkp_primality::pocklington::pocklington_step_big;

fn main(
    n: pub [u128; 3],
    // level 256: f = n128, y of order f modulo n
    redc256: [u128; 3],
    y256: [u128; 3],
    inv256: [u128; 3],
    // level 128: f = n64
    n128: [u128; 2],
    redc128: [u128; 2],
    y128: [u128; 2],
    inv128: [u128; 2],
    // level 64: f = n32
    n64: u128,
    y64: u128,
    inv64: u128,
    // level 32: f = n16
    n32: u128,
    y32: u128,
    inv32: u128,
    // level 16: trial division
    n16: u128,
) {
    pocklington_step_big::<3, 256, 2, 128>(n, redc256, n128, y256, inv256);
    pocklington_step_big::<2, 128, 1, 64>(n128, redc128, [n64], y128, inv128);
    pocklington_step::<32>(n64, n32, y64, inv64);
    pocklington_step::<16>(n32, n16, y32, inv32);
    assert_prime_below_2_16(n16);
}
