// Test harness: ONE native Pocklington step (f < 2^32, n < 2^64) with all inputs free.
use zkp_primality::native::pocklington_step;

fn main(n: pub u128, f: pub u128, y: u128, inv: u128) {
    pocklington_step::<32>(n, f, y, inv);
}
