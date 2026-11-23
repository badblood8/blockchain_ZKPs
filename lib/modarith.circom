pragma circom 2.0.6;

include "bits.circom";

// Sound modular arithmetic over the BN128 scalar field.
//
// Every value is a k-bit integer, k <= 125.  That bound is what makes these
// gadgets sound: a*b < 2^(2k) and q*n + r < 2^(2k) + 2^k both stay below the
// field prime (~2^253.6), so the equation a*b = q*n + r holds over the
// *integers*, not just modulo p.  Moduli wider than 125 bits would need
// multi-limb (bignum) arithmetic, which this library does not implement.

// ModMul(k): r = a*b mod n.
// PRECONDITIONS (the caller must enforce them; ModExp does):
//     0 <= a < n  and  0 <= b < n  and  n < 2^k.
// Enforces:  a*b = q*n + r  with  q < 2^k  and  r < n
// which, over the integers, pins r to exactly (a*b) mod n.
template ModMul(k) {
    assert(k <= 125);
    signal input a;
    signal input b;
    signal input n;
    signal output r;

    signal q;
    q <-- (a * b) \ n;
    r <-- (a * b) % n;

    // q < 2^k (given a, b < n we have q <= n - 1 < 2^k, so honest provers pass)
    component qRange = AssertBits(k);
    qRange.in <== q;

    // a*b = q*n + r   (split in two so each constraint has a single product)
    signal qn;
    qn <== q * n;
    a * b === qn + r;

    // r < n
    component rLessN = AssertLessThan(k);
    rLessN.a <== r;
    rLessN.b <== n;
}

// ModExp(k): result = base^exp mod mod, by square-and-multiply.
// Enforces (all of these make the witness unsatisfiable if violated):
//     2 <= mod < 2^k,   0 <= base < mod,   0 <= exp < 2^k.
// Cost: about 4*k^2 + 13*k constraints.
template ModExp(k) {
    assert(k >= 2 && k <= 125);
    signal input base;
    signal input exp;
    signal input mod;
    signal output result;

    // mod in [2, 2^k)
    component modRange = AssertBits(k);
    modRange.in <== mod;
    component modAtLeast2 = AssertBits(k);
    modAtLeast2.in <== mod - 2;

    // base in [0, mod)
    component baseRange = AssertBits(k);
    baseRange.in <== base;
    component baseLessMod = AssertLessThan(k);
    baseLessMod.a <== base;
    baseLessMod.b <== mod;

    // exp in [0, 2^k), as bits (little endian)
    component expBits = Num2Bits(k);
    expBits.in <== exp;

    // res[i] = base^(low i bits of exp);  cur[i] = base^(2^i)  (both mod `mod`)
    signal res[k + 1];
    signal cur[k];
    res[0] <== 1;
    cur[0] <== base;

    component mul[k];
    component sq[k - 1];

    for (var i = 0; i < k; i++) {
        mul[i] = ModMul(k);
        mul[i].a <== res[i];
        mul[i].b <== cur[i];
        mul[i].n <== mod;

        // res[i+1] = bit ? res[i]*cur[i] : res[i]     (one quadratic constraint)
        res[i + 1] <== res[i] + expBits.out[i] * (mul[i].r - res[i]);

        if (i < k - 1) {
            sq[i] = ModMul(k);
            sq[i].a <== cur[i];
            sq[i].b <== cur[i];
            sq[i].n <== mod;
            cur[i + 1] <== sq[i].r;
        }
    }

    result <== res[k];
}
