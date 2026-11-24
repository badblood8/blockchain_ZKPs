// Elliptic Curve Primality Proving (Atkin-Goldwasser-Kilian), one level, for n < 2^64 (u128 arithmetic).
//
// Theorem.  n coprime to 6, E: y^2 = x^3 + a x + b over Z/n, P a point, k an integer and q a prime with
// q > (n^(1/4) + 1)^2.  If R = [k]P is an AFFINE point (every inverse met while computing it exists mod n)
// and [q]R = O, then n is prime.   (Mod any prime p | n, R has order exactly q, so
// q <= #E(F_p) <= (sqrt(p) + 1)^2 <= (n^(1/4) + 1)^2: a contradiction.)
//
// This circuit checks, with every inverse supplied as a verified hint:
//   * n odd, n % 3 != 0;   P on E;   4a^3 + 27b^2 a unit                      (the last two are redundant
//     for soundness, see model_check.py: the group law never uses b and the size bound already excludes
//     singular curves; they are kept as cheap defense in depth)
//   * (r+1)^4 > n  and  q >= (r+2)^2                          which implies q > (n^(1/4) + 1)^2
//   * R = [k]P by double-and-add, then [q-1]R == -R           which is [q]R = O
// q is prime GIVEN by the next level of the chain (or by trial division at the bottom).
//
// Costs about 9 modular multiplications per scalar bit, so a level is 9 * (KB + QB) mulmods.

struct Pt {
    x: u128,
    y: u128,
}

fn mulmod(a: u128, b: u128, n: u128) -> u128 {
    (a * b) % n // a, b < n < 2^64: the product fits u128
}

// Witness hint only: a^-1 mod n by the extended Euclidean algorithm (0 if gcd(a, n) != 1).
// Every use is re-checked by a * inv % n == 1.
unconstrained fn inv_mod_hint(a: u128, n: u128) -> u128 {
    let mut r0 = n;
    let mut r1 = a % n;
    let mut t0: u128 = 0;
    let mut t1: u128 = 1;
    while r1 != 0 {
        let q = r0 / r1;
        let r2 = r0 - q * r1;
        let qt = ((q % n) * t1) % n;
        let t2 = (t0 + n - qt) % n;
        r0 = r1;
        r1 = r2;
        t0 = t1;
        t1 = t2;
    }
    if r0 == 1 {
        t0
    } else {
        0
    }
}

// a * inv = 1 (mod n), with inv supplied by the hint above.
fn checked_inverse(a: u128, n: u128) -> u128 {
    // Safety: the result is constrained on the next line.
    let inv = unsafe { inv_mod_hint(a, n) };
    assert((a * inv) % n == 1);
    inv
}

// 2P (needs 2y invertible)
fn ec_double(p: Pt, a: u128, n: u128) -> Pt {
    let inv = checked_inverse((2 * p.y) % n, n);
    let num = (3 * mulmod(p.x, p.x, n) + a) % n;
    let lam = mulmod(num, inv, n);
    let x3 = (mulmod(lam, lam, n) + 2 * n - 2 * p.x) % n;
    let y3 = (mulmod(lam, (p.x + n - x3) % n, n) + n - p.y) % n;
    Pt { x: x3, y: y3 }
}

// R + P if `bit`, else R.  When bit is false the denominator is replaced by 1 so a coincidental
// x_R = x_P does not matter; when bit is true x_P - x_R must be invertible.
fn ec_add_if(r: Pt, p: Pt, bit: bool, n: u128) -> Pt {
    let dx = (p.x + n - r.x) % n;
    let den = if bit { dx } else { 1 };
    let inv = checked_inverse(den, n);
    let lam = mulmod((p.y + n - r.y) % n, inv, n);
    let x3 = (mulmod(lam, lam, n) + 2 * n - r.x - p.x) % n;
    let y3 = (mulmod(lam, (r.x + n - x3) % n, n) + n - r.y) % n;
    if bit {
        Pt { x: x3, y: y3 }
    } else {
        r
    }
}

// [scalar]P for a scalar with exactly B bits (top bit set), left to right.
fn ec_mul<let B: u32>(p: Pt, bits: [bool; B], a: u128, n: u128) -> Pt {
    assert(bits[B - 1]);
    let mut r = p;
    for j in 0..(B - 1) {
        let i = B - 2 - j;
        r = ec_double(r, a, n);
        r = ec_add_if(r, p, bits[i], n);
    }
    r
}

// One ECPP level: n is prime GIVEN that q is prime.
//   k has exactly KB bits, q has exactly QB bits.  r is the fourth-root witness, dinv the inverse
//   of the discriminant.
pub fn ecpp_step<let KB: u32, let QB: u32>(
    n: u128,
    a: u128,
    b: u128,
    x: u128,
    y: u128,
    k: u128,
    q: u128,
    r: u128,
    dinv: u128,
) {
    assert(KB >= 2);
    assert(QB >= 3);
    assert(n < 18446744073709551616); // n < 2^64
    assert(n % 2 == 1);
    assert(n % 3 != 0);
    assert(a < n);
    assert(b < n);
    assert(x < n);
    assert(y < n);

    // P on E, and the discriminant is a unit (defense in depth, see header)
    let x3 = mulmod(mulmod(x, x, n), x, n);
    assert(mulmod(y, y, n) == (x3 + mulmod(a, x, n) + b) % n);
    let a3 = mulmod(mulmod(a, a, n), a, n);
    let disc = (4 * a3 + 27 * mulmod(b, b, n)) % n;
    assert((disc * dinv) % n == 1);

    // q > (n^(1/4) + 1)^2   via   (r + 1)^4 > n  and  q >= (r + 2)^2
    assert(r < 65536);
    let r1 = r + 1;
    assert(r1 * r1 * r1 * r1 > n);
    assert(q >= (r + 2) * (r + 2));

    let kbits: [bool; KB] = (k as Field).to_le_bits(); // k < 2^KB
    let qm1_bits: [bool; QB] = ((q - 1) as Field).to_le_bits(); // q - 1 < 2^QB
    assert(q >= 3);

    let p = Pt { x: x, y: y };
    let big_r = ec_mul(p, kbits, a, n); // R = [k]P, an affine point
    let big_q = ec_mul(big_r, qm1_bits, a, n); // [q - 1]R
    assert(big_q.x == big_r.x);
    assert((big_q.y + big_r.y) % n == 0); // [q - 1]R = -R   i.e.   [q]R = O
}
