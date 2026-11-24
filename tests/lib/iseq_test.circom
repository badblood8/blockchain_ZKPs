pragma circom 2.0.6;
include "../../lib/bits.circom";

template IsEqualHarness() {
    signal input x;
    signal input y;
    signal output eq;
    signal output zx;

    component e = IsEqual();
    e.in[0] <== x;
    e.in[1] <== y;
    eq <== e.out;

    component z = IsZero();
    z.in <== x;
    zx <== z.out;
}

component main {public [x, y]} = IsEqualHarness();
