// Zero-knowledge proof that the PUBLIC 256-bit number n is prime (deterministic Pocklington chain).
use zkp_primality::chain256::{assert_prime_256, Chain256};

fn main(n: pub [u128; 3], c: Chain256) {
    assert_prime_256(n, c);
}
