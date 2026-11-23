pragma circom 2.0.6;
include "../../lib/modarith.circom";

// Test harness: ModMul has preconditions (a, b < n < 2^k) that ModExp normally
// enforces, so the harness enforces them here.
template ModMulHarness(k) {
    signal input a;
    signal input b;
    signal input n;
    signal output r;

    component nRange = AssertBits(k);       nRange.in <== n;
    component aRange = AssertBits(k);       aRange.in <== a;
    component bRange = AssertBits(k);       bRange.in <== b;
    component aLt = AssertLessThan(k);      aLt.a <== a;  aLt.b <== n;
    component bLt = AssertLessThan(k);      bLt.a <== b;  bLt.b <== n;

    component m = ModMul(k);
    m.a <== a;  m.b <== b;  m.n <== n;
    r <== m.r;
}

component main {public [a, b, n]} = ModMulHarness(32);
