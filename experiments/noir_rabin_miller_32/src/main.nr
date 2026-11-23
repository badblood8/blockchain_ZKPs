// Rabin-Miller (strong probable prime) test on a 32-bit n: a Noir port of
// circom/rabin_miller.circom, with the same statement and the same public inputs.
//
//   n is accepted iff n is odd, 5 <= n < 2^32 and, for each of the K public bases a
//   with 2 <= a <= n-2, writing n-1 = d * 2^r with d odd:
//       a^d == 1 (mod n)   or   a^(d * 2^j) == n-1 (mod n) for some 0 <= j < r.
//
// No custom range-check gadgets are needed: u64 arithmetic is range-checked by the
// compiler, and a * b < 2^64 whenever a, b < n < 2^32.

global K: u32 = 10;

// a, b < n < 2^32  =>  a * b < 2^64, so the u64 product cannot overflow.
fn mulmod(a: u64, b: u64, n: u64) -> u64 {
    (a * b) % n
}

// base^e mod n by square-and-multiply over the 32 bits of e.
fn modexp(base: u64, e: u64, n: u64) -> u64 {
    let bits: [bool; 32] = (e as Field).to_le_bits(); // also proves e < 2^32
    let mut result: u64 = 1;
    let mut cur = base;
    for i in 0..32 {
        let prod = mulmod(result, cur, n);
        result = if bits[i] { prod } else { result };
        cur = mulmod(cur, cur, n);
    }
    result
}

// Witness hint only: n-1 = d * 2^r with d odd.  The result is re-checked in main().
unconstrained fn two_adic(nm1: u64) -> (u64, u32) {
    let mut d = nm1;
    let mut r: u32 = 0;
    while (d % 2 == 0) & (d != 0) {
        d = d / 2;
        r += 1;
    }
    (d, r)
}

fn main(n: pub u64, a: pub [u64; K]) {
    assert(n >= 5);
    assert(n < 4294967296);
    let nm1 = n - 1;

    // Safety: the decomposition is fully constrained right below.
    let (d, r) = unsafe { two_adic(nm1) };
    assert(d % 2 == 1);
    assert(r >= 1);
    assert(r <= 31);
    let mut pow2r: u64 = 1;
    for i in 0..31 {
        if i < r {
            pow2r *= 2;
        }
    }
    assert(d * pow2r == nm1);

    for i in 0..K {
        let b = a[i];
        assert(b >= 2);
        assert(b + 2 <= n); // b <= n - 2

        let x0 = modexp(b, d, n);
        let mut x = x0;
        let mut hit = false;
        for j in 0..31 {
            if (j < r) & (x == nm1) {
                hit = true;
            }
            x = mulmod(x, x, n);
        }
        assert((x0 == 1) | hit);
    }
}

#[test]
fn accepts_prime() {
    main(982451653, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test(should_fail)]
fn rejects_composite() {
    main(982451655, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test(should_fail)]
fn rejects_even() {
    main(982451654, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test(should_fail)]
fn rejects_carmichael() {
    main(561, [2, 5, 7, 13, 17, 19, 23, 29, 31, 37]);
}

#[test]
fn accepts_large_two_adic_valuation() {
    // 3221225473 = 3 * 2^30 + 1 (prime): r = 30
    main(3221225473, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test]
fn accepts_largest_32_bit_prime() {
    main(4294967291, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test(should_fail)]
fn rejects_vacuous_base() {
    main(101, [1, 3, 5, 7, 11, 13, 17, 19, 23, 29]);
}

#[test(should_fail)]
fn rejects_strong_pseudoprime_with_witness_base() {
    // 3215031751 passes bases 2,3,5,7 but not 11
    main(3215031751, [2, 3, 5, 7, 11, 2, 2, 2, 2, 2]);
}

#[test]
fn accepts_strong_pseudoprime_when_no_witness_base_is_given() {
    main(3215031751, [2, 3, 5, 7, 2, 3, 5, 7, 2, 3]);
}
