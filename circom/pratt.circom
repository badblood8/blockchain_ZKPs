pragma circom 2.0.6;

// Template to convert an integer into its binary representation
template Num2Bits(n) {
    signal input in;
    signal output out[n];
    var lc1 = 0;

    for (var i = 0; i < n; i++) {
        out[i] <-- (in >> i) & 1;
        out[i] * (out[i] - 1) === 0;
        lc1 += out[i] * 2**i;
    }

    lc1 === in;
}

// Modular Exponentiation using the fixed template provided
template ModularExponentiation(nBits) {
    signal input base;
    signal input exp;
    signal input mod;
    signal output result;

    component expBits = Num2Bits(nBits);
    expBits.in <== exp;

    signal tmpResults[nBits + 1];
    signal currentBases[nBits + 1];
    signal applyMultiplier[nBits];

    tmpResults[0] <== 1;
    currentBases[0] <== base;

    for (var i = 0; i < nBits; i++) {
        applyMultiplier[i] <-- expBits.out[i] == 1 ? currentBases[i] : 1;
        tmpResults[i + 1] <-- (tmpResults[i] * applyMultiplier[i]) % mod;
        currentBases[i + 1] <-- (currentBases[i] * currentBases[i]) % mod;
    }

    result <== tmpResults[nBits];
}

// Template to verify a single step in the Pratt certificate
template VerifyPrattStep(nBits, maxFactors) {
    signal input prime;
    signal input base;
    signal input factors[maxFactors];
    signal input exps[maxFactors];
    signal output isPrime;

    component modExpMain = ModularExponentiation(nBits);
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

        modExpFactor[i] = ModularExponentiation(nBits);
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

component main {public [mainPrime, base, certPrimes, certFactors, precomputedExps]} = PrattCertificateVerifier(256, 6, 6);
