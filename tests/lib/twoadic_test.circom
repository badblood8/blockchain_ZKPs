pragma circom 2.0.6;
include "../../lib/twoadic.circom";

// d and the selector are INPUTS here, so tests can try any decomposition,
// including alternative self-consistent ones a malicious prover might choose.
component main {public [n, d, sel]} = CheckTwoAdicDecomposition(32);
