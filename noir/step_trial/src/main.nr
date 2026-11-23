// Test harness: the trial-division base case.
use zkp_primality::native::assert_prime_below_2_16;

fn main(n: pub u128) {
    assert_prime_below_2_16(n);
}
