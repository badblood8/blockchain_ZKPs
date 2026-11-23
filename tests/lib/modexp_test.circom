pragma circom 2.0.6;
include "../../lib/modarith.circom";

component main {public [base, exp, mod]} = ModExp(32);
