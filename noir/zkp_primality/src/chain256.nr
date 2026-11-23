// A complete primality proof for a 256-bit number: the Pocklington chain
//     n (256) <- n128 <- n64 <- n32 <- n16 (trial division)
// Everything except n itself is private witness.
use crate::native::{assert_prime_below_2_16, pocklington_step};
use crate::pocklington::pocklington_step_big;

pub struct Chain256 {
    // level 256: f = n128, y of order f modulo n, inv = (y - 1)^-1, redc = Barrett constant
    pub redc256: [u128; 3],
    pub y256: [u128; 3],
    pub inv256: [u128; 3],
    // level 128: f = n64
    pub n128: [u128; 2],
    pub redc128: [u128; 2],
    pub y128: [u128; 2],
    pub inv128: [u128; 2],
    // level 64: f = n32
    pub n64: u128,
    pub y64: u128,
    pub inv64: u128,
    // level 32: f = n16
    pub n32: u128,
    pub y32: u128,
    pub inv32: u128,
    // level 16: trial division
    pub n16: u128,
}

// n (3 limbs of 120 bits, exactly 256 bits) is prime.
pub fn assert_prime_256(n: [u128; 3], c: Chain256) {
    pocklington_step_big::<3, 256, 2, 128>(n, c.redc256, c.n128, c.y256, c.inv256);
    pocklington_step_big::<2, 128, 1, 64>(c.n128, c.redc128, [c.n64], c.y128, c.inv128);
    pocklington_step::<32>(c.n64, c.n32, c.y64, c.inv64);
    pocklington_step::<16>(c.n32, c.n16, c.y32, c.inv32);
    assert_prime_below_2_16(c.n16);
}
