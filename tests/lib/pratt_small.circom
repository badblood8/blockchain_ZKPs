pragma circom 2.0.6;
include "../../lib/pratt.circom";

// Same templates as circom/pratt.circom, 16-bit numbers, 7 entries, up to 5 odd
// prime factors per p-1: small enough to run hundreds of cases quickly.
component main {public [mainPrime]} = PrattVerifier(16, 7, 5);
