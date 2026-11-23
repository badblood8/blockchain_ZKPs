pragma circom 2.0.6;

include "../lib/modarith.circom";

// Lehmann primality test: n passes iff n is odd and, for every base a[i] with
// 2 <= a[i] <= n-2,
//     a[i]^((n-1)/2) == 1  or  == n-1   (mod n).
// n even makes (n-1)/2 a non-integer field element, which the exponent range
// check inside ModExp rejects, so even n has no valid witness.
// isPrime is the product of the k per-base indicator bits (1 only if every base,
// including a[0], passes).
template LehmannPrimalityTest(k, nBits) {
    assert(k >= 1);
    signal input n;
    signal input a[k];
    signal output isPrime;

    component baseRange[k];
    component modExp[k];
    component isOne[k];
    component isNMinusOne[k];
    signal baseOk[k];
    signal acc[k + 1];
    acc[0] <== 1;

    for (var i = 0; i < k; i++) {
        baseRange[i] = AssertBaseInRange(nBits);
        baseRange[i].a <== a[i];
        baseRange[i].n <== n;

        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== (n - 1) / 2;
        modExp[i].mod <== n;

        isOne[i] = IsEqual();
        isOne[i].in[0] <== modExp[i].result;
        isOne[i].in[1] <== 1;

        isNMinusOne[i] = IsEqual();
        isNMinusOne[i].in[0] <== modExp[i].result;
        isNMinusOne[i].in[1] <== n - 1;

        // logical OR of two booleans
        baseOk[i] <== isOne[i].out + isNMinusOne[i].out - isOne[i].out * isNMinusOne[i].out;

        acc[i + 1] <== acc[i] * baseOk[i];
    }

    isPrime <== acc[k];
}

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
template LehmannVerifier(k, nBits) {
    signal input n;
    signal input a[k];

    component test = LehmannPrimalityTest(k, nBits);
    test.n <== n;
    test.a <== a;
    test.isPrime === 1;
}

component main {public [n, a]} = LehmannVerifier(10, 32);
