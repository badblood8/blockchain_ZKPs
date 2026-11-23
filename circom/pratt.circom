pragma circom 2.0.6;

include "../lib/modarith.circom";

// Template to verify a single step in the Pratt certificate
template VerifyPrattStep(nBits, maxFactors) {
    signal input prime;
    signal input base;
    signal input factors[maxFactors];
    signal input exps[maxFactors];
    signal output isPrime;

    component modExpMain = ModExp(nBits);
    modExpMain.base <== base;
    modExpMain.exp <== prime - 1;
    modExpMain.mod <== prime;

    signal mainCheck;
    mainCheck <== 1 - (modExpMain.result - 1) * (modExpMain.result - 1);

    component modExpFactor[maxFactors];
    signal factorDiff[maxFactors];
    signal factorChecks[maxFactors];
    signal nonZeroFactor[maxFactors];
    signal accumulatedChecks[maxFactors + 1];

    accumulatedChecks[0] <== mainCheck;

    for (var i = 0; i < maxFactors; i++) {
        // Define nonZeroFactor[i] as a binary signal using quadratic constraints
        nonZeroFactor[i] <-- 1 - (factors[i] * factors[i] == 0 ? 1 : 0);

        modExpFactor[i] = ModExp(nBits);
        modExpFactor[i].base <== base;
        modExpFactor[i].exp <== exps[i];
        modExpFactor[i].mod <== prime;

        factorDiff[i] <== modExpFactor[i].result - 1;
        factorChecks[i] <-- nonZeroFactor[i] * (1 - factorDiff[i] * factorDiff[i]) + (1 - nonZeroFactor[i]);

        accumulatedChecks[i + 1] <== accumulatedChecks[i] * factorChecks[i];
    }

    // Set isPrime based on the last accumulated check
    isPrime <== accumulatedChecks[maxFactors];
}




// Pratt Certificate Verifier with recursive primes and factors
template PrattCertificateVerifier(nBits, maxPrimes, maxFactors) {
    signal input mainPrime;
    signal input base;
    signal input certPrimes[maxPrimes];
    signal input certFactors[maxPrimes][maxFactors];
    signal input precomputedExps[maxPrimes][maxFactors];
    signal output isPrime;

    signal recursiveCheck[maxPrimes];
    component verifyStep[maxPrimes];

    for (var i = 0; i < maxPrimes; i++) {
        verifyStep[i] = VerifyPrattStep(nBits, maxFactors);
        verifyStep[i].prime <== certPrimes[i];
        verifyStep[i].base <== base;
        verifyStep[i].factors <== certFactors[i];
        verifyStep[i].exps <== precomputedExps[i];
        
        if (i == 0) {
            recursiveCheck[i] <== verifyStep[i].isPrime;
        } else {
            recursiveCheck[i] <== recursiveCheck[i - 1] * verifyStep[i].isPrime;
        }
    }

    isPrime <== recursiveCheck[maxPrimes - 1];
}

// Top-level circuit: the proof exists only if the whole certificate checks (isPrime == 1).
template PrattVerifier(nBits, maxPrimes, maxFactors) {
    signal input mainPrime;
    signal input base;
    signal input certPrimes[maxPrimes];
    signal input certFactors[maxPrimes][maxFactors];
    signal input precomputedExps[maxPrimes][maxFactors];

    component cert = PrattCertificateVerifier(nBits, maxPrimes, maxFactors);
    cert.mainPrime <== mainPrime;
    cert.base <== base;
    cert.certPrimes <== certPrimes;
    cert.certFactors <== certFactors;
    cert.precomputedExps <== precomputedExps;
    cert.isPrime === 1;
}

component main {public [mainPrime, base, certPrimes, certFactors, precomputedExps]} = PrattVerifier(32, 6, 6);
