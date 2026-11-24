// Test harness: ONE ECPP level (k: 8 bits, q: 9 bits) with all inputs free.
use zkp_primality::ecpp::ecpp_step;

fn main(n: pub u128, a: u128, b: u128, x: u128, y: u128, k: u128, q: u128, r: u128, dinv: u128) {
    ecpp_step::<8, 9>(n, a, b, x, y, k, q, r, dinv);
}
