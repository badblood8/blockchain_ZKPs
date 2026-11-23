// Pocklington step for n with 121..=512 bits, over noir-bignum's RuntimeBigNum
// (modulus n is a witness; its limbs are the SAME witness used everywhere else in the
// circuit, which is what ties the arithmetic to the number being certified).
use bignum::{BigNum, RuntimeBigNum, U512};
use bignum::params::BigNumParams;

// Zero-extend K limbs (120 bits each) into a U512.  U512 has modulus 2^512, so products
// of values below 2^256 are exact integers there.
fn to_u512<let K: u32>(limbs: [u128; K]) -> U512 {
    assert(K <= 5);
    let mut l: [u128; 5] = [0; 5];
    for i in 0..K {
        l[i] = limbs[i];
    }
    U512::from_limbs(l)
}

// Little-endian bits of a K-limb number that must fit in exactly B bits
// (120 * (K - 1) < B <= 120 * K).  Fails if any bit at position >= B is set.
fn limbs_to_bits<let K: u32, let B: u32>(limbs: [u128; K]) -> [bool; B] {
    assert(120 * (K - 1) < B);
    assert(B <= 120 * K);
    let mut bits: [bool; B] = [false; B];
    for k in 0..K {
        let limb_bits: [bool; 120] = (limbs[k] as Field).to_le_bits();
        for i in 0..120 {
            let pos = 120 * k + i;
            if pos < B {
                bits[pos] = limb_bits[i];
            } else {
                assert(!limb_bits[i]);
            }
        }
    }
    bits
}

// One Pocklington step: n (N limbs, MB bits) is prime, GIVEN that f is prime.
//   f^2 > n                                   (exact, in U512: f < 2^FB <= 2^256)
//   y^f = 1 (mod n)  and  y - 1 invertible mod n   (gcd(y - 1, n) = 1)
// See zkp_primality::native::pocklington_step for why this proves n prime.
// `redc` is noir-bignum's Barrett constant floor(2^(2 MB + 6) / n): an unvalidated witness
// that only steers unconstrained witness generation (documented by the library).
pub fn pocklington_step_big<let N: u32, let MB: u32, let FL: u32, let FB: u32>(
    n_limbs: [u128; N],
    redc: [u128; N],
    f_limbs: [u128; FL],
    y_limbs: [u128; N],
    inv_limbs: [u128; N],
) {
    // validates the limbs and that n has exactly MB bits (so n >= 2^(MB-1) > 1)
    let params: BigNumParams<N, MB> = BigNumParams::new(false, n_limbs, redc);

    // ---- f^2 > n as exact integers (U512: modulus 2^512, every value below 2^257)
    let fbits: [bool; FB] = limbs_to_bits(f_limbs); // f < 2^FB
    let fu = to_u512(f_limbs);
    assert(fu * fu > to_u512(n_limbs));

    // ---- arithmetic modulo n
    let one: RuntimeBigNum<N, MB> = RuntimeBigNum::one(params);
    let y: RuntimeBigNum<N, MB> = RuntimeBigNum::from_array(params, y_limbs);
    let mut z = one;
    for j in 0..FB {
        let i = FB - 1 - j;
        let sq = z * z;
        let m = sq * y;
        z = if fbits[i] { m } else { sq };
    }
    assert(z == one); // y^f = 1

    let inv: RuntimeBigNum<N, MB> = RuntimeBigNum::from_array(params, inv_limbs);
    assert((y - one) * inv == one); // gcd(y - 1, n) = 1
}
