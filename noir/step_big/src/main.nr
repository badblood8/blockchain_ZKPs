// Test harness: ONE bignum Pocklington step (n: 128 bits, f < 2^64) with all inputs free.
use zkp_primality::pocklington::pocklington_step_big;

fn main(n: pub [u128; 2], f: pub [u128; 1], redc: [u128; 2], y: [u128; 2], inv: [u128; 2]) {
    pocklington_step_big::<2, 128, 1, 64>(n, redc, f, y, inv);
}
