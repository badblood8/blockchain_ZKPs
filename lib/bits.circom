pragma circom 2.0.6;

// Bit-decomposition and range-check gadgets shared by every circuit in this repo.
//
// All templates here are fully constrained: no output is assigned with `<--`
// without a matching constraint.

// Num2Bits(n): out = little-endian bits of `in`.
// Enforces 0 <= in < 2^n.  Requires n <= 253 so that the weighted sum of the
// bits cannot wrap around the BN128 scalar field (p ~ 2^253.6).
template Num2Bits(n) {
    assert(n <= 253);
    signal input in;
    signal output out[n];
    var lc = 0;
    var pow2 = 1;

    for (var i = 0; i < n; i++) {
        out[i] <-- (in >> i) & 1;
        out[i] * (out[i] - 1) === 0;   // each bit is 0 or 1
        lc += out[i] * pow2;
        pow2 = pow2 + pow2;
    }

    lc === in;                          // bits recompose to `in`
}

// AssertBits(n): enforces 0 <= in < 2^n (a pure range check).
template AssertBits(n) {
    signal input in;
    component bits = Num2Bits(n);
    bits.in <== in;
}

// AssertLessThan(k): enforces a < b.
// PRECONDITION (caller must enforce): 0 <= a, b < 2^k, and k <= 252.
// If a >= b then b - a - 1 is a negative number, i.e. a field element larger
// than p - 2^k > 2^k, which cannot be written in k bits, so the check fails.
template AssertLessThan(k) {
    assert(k <= 252);
    signal input a;
    signal input b;
    component diff = Num2Bits(k);
    diff.in <== b - a - 1;
}

// IsZero: out = 1 if in == 0, else 0.  `out` is genuinely boolean:
//   in != 0  =>  out = 1 - in*inv = 0  (inv = 1/in)
//   in == 0  =>  out = 1
// and the constraint in*out === 0 stops a prover from claiming out = 1 for in != 0.
template IsZero() {
    signal input in;
    signal output out;
    signal inv;

    inv <-- in != 0 ? 1 / in : 0;
    out <== 1 - in * inv;
    in * out === 0;
}

// IsEqual: out = 1 if in[0] == in[1], else 0.
template IsEqual() {
    signal input in[2];
    signal output out;

    component isz = IsZero();
    isz.in <== in[1] - in[0];
    out <== isz.out;
}
