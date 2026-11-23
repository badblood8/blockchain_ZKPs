// Zero-knowledge proof that the PUBLIC 64-bit number n is prime, by a real ECPP chain
//     n (64 bits) <- q1 (33 bits) <- q2 (17 bits) <- q3 (9 bits, trial division)
// Each level proves "n_i is prime given that q_i is prime".  q > (n^(1/4)+1)^2 > sqrt(n) forces the
// chain to at best halve the bit length per level.
//   level 1: k1 has 31 bits, q1 33 bits      level 2 (modulus q1): k2 16 bits, q2 17 bits
//   level 3 (modulus q2): k3 8 bits, q3 9 bits
use zkp_primality::ecpp::ecpp_step;
use zkp_primality::native::assert_prime_below_2_16;

fn main(
    n: pub u128,
    a1: u128, b1: u128, x1: u128, y1: u128, k1: u128, q1: u128, r1: u128, dinv1: u128,
    a2: u128, b2: u128, x2: u128, y2: u128, k2: u128, q2: u128, r2: u128, dinv2: u128,
    a3: u128, b3: u128, x3: u128, y3: u128, k3: u128, q3: u128, r3: u128, dinv3: u128,
) {
    ecpp_step::<31, 33>(n, a1, b1, x1, y1, k1, q1, r1, dinv1);
    ecpp_step::<16, 17>(q1, a2, b2, x2, y2, k2, q2, r2, dinv2);
    ecpp_step::<8, 9>(q2, a3, b3, x3, y3, k3, q3, r3, dinv3);
    assert_prime_below_2_16(q3);
}
