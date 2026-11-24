// Rabin-Miller on a 256-bit public n, using noir-bignum's RuntimeBigNum.
// (The Circom library in lib/ is limited to 125-bit numbers.)
//
// Statement: n is odd, has exactly 256 bits, and passes the strong probable-prime
// test for each of the K public bases a (2 <= a < 2^64 <= n-2).
//
// Technique (no explicit decomposition n-1 = d * 2^r is needed):
//   Let e = n - 1 and process its bits from the top.  After handling bit i the
//   running value is  s_i = a^(e >> i).  With r = number of trailing zero bits of e:
//       s_r     = a^d                      (the x_0 of the textbook test)
//       s_(r-j) = a^(d * 2^j)              (the j-th squaring)
//   The base passes iff  s_r == 1   or   s_i == n-1 for some 1 <= i <= r.
// The prover hints which of the two it is and, for the second, the index i.  The
// circuit selects s_i with cheap field arithmetic and does ONE big-number equality
// check per base, instead of one per bit.
//
// Security notes (from noir-bignum's README): the modulus is a PUBLIC input, which is
// required for RuntimeBigNum.  `redc_param` is an unvalidated witness: it only
// affects unconstrained witness generation (see tests in this directory).

use bignum::params::BigNumParams;
use bignum::RuntimeBigNum;

global K: u32 = 1;

type RBN = RuntimeBigNum<3, 256>;

fn main(
    n: pub [u128; 3],      // 3 limbs of 120 bits, little endian; top limb has 16 bits
    a: pub [u64; K],
    redc_param: [u128; 3], // floor(2^518 / n), witness
    idx: [u32; K],         // hint: position i of the s_i that equals n-1 (1 <= i <= r)
    use_one: [bool; K],    // hint: true when s_r == 1 instead
) {
    // Validates the limbs and that n really has 256 bits; derives double_modulus.
    let params: BigNumParams<3, 256> = BigNumParams::new(false, n, redc_param);

    // ---- bits of e = n - 1
    let b0: [bool; 120] = (n[0] as Field).to_le_bits();
    let b1: [bool; 120] = (n[1] as Field).to_le_bits();
    let b2: [bool; 16] = (n[2] as Field).to_le_bits();
    let mut e: [bool; 256] = [false; 256];
    for i in 0..120 {
        e[i] = b0[i];
        e[120 + i] = b1[i];
    }
    for i in 0..16 {
        e[240 + i] = b2[i];
    }
    assert(e[0]); // n is odd: NECESSARY (model_check.py)
    e[0] = false; // e = n - 1

    // z[i] == true  <=>  the lowest i bits of e are all zero  <=>  i <= r
    let mut z: [bool; 257] = [false; 257];
    z[0] = true;
    for i in 0..256 {
        z[i + 1] = z[i] & !e[i];
    }

    let one: RBN = RuntimeBigNum::from_array(params, [1, 0, 0]);
    let nm1: RBN = RuntimeBigNum::from_array(params, [n[0] - 1, n[1], n[2]]);

    for k in 0..K {
        assert(a[k] >= 2);
        let base: RBN = RuntimeBigNum::from_array(params, [a[k] as u128, 0, 0]);

        let mut x = one;
        let mut sel_idx: [Field; 3] = [0; 3];
        let mut sel_r: [Field; 3] = [0; 3];
        let mut hits: u32 = 0;

        for j in 0..256 {
            let i = 255 - j;
            let sq = x * x;
            let m = sq * base;
            x = if e[i] { m } else { sq }; // x = s_i now

            // s_i for the hinted index i == idx[k]
            let at_idx = i == idx[k];
            if at_idx {
                assert(z[i]); // i <= r: NECESSARY (model_check.py: dropping it accepts composites)
                assert(i >= 1); // provably redundant (s_0 = -1 is impossible for odd n); defense in depth
                hits += 1;
            }
            // s_r : the unique i with z[i] and e[i]
            let at_r = z[i] & e[i];
            for l in 0..3 {
                sel_idx[l] += (at_idx as Field) * (x.limbs[l] as Field);
                sel_r[l] += (at_r as Field) * (x.limbs[l] as Field);
            }
        }
        assert(hits == 1); // redundant given the final equality (no hit => candidate = 0 != n-1)

        let chosen = if use_one[k] { sel_r } else { sel_idx };
        let candidate: RBN = RuntimeBigNum::from_array(
            params,
            [chosen[0] as u128, chosen[1] as u128, chosen[2] as u128],
        );
        let target = if use_one[k] { one } else { nm1 };
        assert(candidate == target);
    }
}
