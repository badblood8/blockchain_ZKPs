pragma circom 2.0.6;

include "bits.circom";

// Witness-only helper (used inside `<--` hints; every result is re-constrained):
// number of times 2 divides x (0 for x == 0).
function twoAdicValuation(x) {
    var r = 0;
    var t = x;
    if (t == 0) {
        return 0;
    }
    while (t % 2 == 0) {
        t = t \ 2;
        r++;
    }
    return r;
}

// CheckTwoAdicDecomposition(nBits): constrains  n - 1 = d * 2^r  with d odd and
// 1 <= r <= nBits - 1, where r is encoded one-hot in sel[1..nBits-1]
// (sel[j] = 1 iff r == j; sel[0] is unused and forced to 0).
//
// Why this pins (d, r) uniquely: d is odd, and the factorisation of a positive
// integer as odd * 2^r is unique.  r >= 1 means n - 1 is even, i.e. n is odd.
// r <= nBits - 1 loses nothing: d >= 1, so 2^r <= n - 1 < 2^nBits.
// PRECONDITION: none -- everything it relies on (d < 2^nBits) is enforced here.
template CheckTwoAdicDecomposition(nBits) {
    assert(nBits >= 3);
    var maxR = nBits - 1;

    signal input n;
    signal input d;
    signal input sel[maxR + 1];

    sel[0] === 0;
    var selSum = 0;
    var pow2rLc = 0;
    for (var j = 1; j <= maxR; j++) {
        sel[j] * (sel[j] - 1) === 0;          // boolean
        selSum += sel[j];
        pow2rLc += sel[j] * (2 ** j);
    }
    selSum === 1;                              // exactly one r

    signal pow2r;
    pow2r <== pow2rLc;
    n - 1 === d * pow2r;

    component dBits = Num2Bits(nBits);         // d < 2^nBits
    dBits.in <== d;
    dBits.out[0] === 1;                        // d is odd
}
