pragma circom 2.0.6;

// Template to convert an integer into its binary representation
template Num2Bits(n) {
    signal input in;
    signal output out[n];
    var lc1 = 0;

    for (var i = 0; i < n; i++) {
        out[i] <-- (in >> i) & 1;
        out[i] * (out[i] - 1) === 0; // Ensure binary
        lc1 += out[i] * 2**i;
    }

    lc1 === in;
}

// Template for Modular Exponentiation using Repeated Squaring
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

// Elliptic Curve Validation
template EllipticCurveValidation(nBits) {
    signal input x;
    signal input y;
    signal input a;
    signal input b;
    signal input prime;
    signal output isValid;

    // Compute y^2 and x^3 + ax + b
    signal y2, x3PlusAxPlusB;
    y2 <-- (y * y) % prime;
    x3PlusAxPlusB <-- ((x * x * x) + (a * x) + b) % prime;

    // Validate the elliptic curve equation
    isValid <== 1 - (y2 - x3PlusAxPlusB) * (y2 - x3PlusAxPlusB);
}

// ECPP Verification Step
template VerifyECPPStep(nBits, maxFactors) {
    signal input prime;
    signal input base;
    signal input factors[maxFactors];
    signal input exps[maxFactors];
    signal input curveA;
    signal input curveB;
    signal input pointX;
    signal input pointY;
    signal input order;
    signal output isPrime;

    // Step 1: Validate the elliptic curve
    component curveValidation = EllipticCurveValidation(nBits);
    curveValidation.x <== pointX;
    curveValidation.y <== pointY;
    curveValidation.a <== curveA;
    curveValidation.b <== curveB;
    curveValidation.prime <== prime;

    // Step 2: Validate the order of the point using modular exponentiation
    component modExpMain = ModularExponentiation(nBits);
    modExpMain.base <== pointX;
    modExpMain.exp <== order;
    modExpMain.mod <== prime;

    signal isOrderValid;
    isOrderValid <== 1 - (modExpMain.result * modExpMain.result);

    // Step 3: Verify factors using modular exponentiation
    signal factorChecks[maxFactors];
    signal accumulator[maxFactors + 1];
    accumulator[0] <== 1;

    component modExpFactor[maxFactors];
    signal factorDiff[maxFactors];
    signal nonZeroFactor[maxFactors];
    signal factorDiffSquare[maxFactors];
    signal tmpFactorCheck[maxFactors];

    for (var i = 0; i < maxFactors; i++) {
        modExpFactor[i] = ModularExponentiation(nBits);
        modExpFactor[i].base <== base;
        modExpFactor[i].exp <== exps[i];
        modExpFactor[i].mod <== prime;

        factorDiff[i] <== modExpFactor[i].result - 1;

        // Ensure factors[i] is non-zero
        nonZeroFactor[i] <-- 1 - (factors[i] * factors[i] == 0 ? 1 : 0);
        nonZeroFactor[i] * (nonZeroFactor[i] - 1) === 0;

        // Compute the square and tmpFactorCheck
        factorDiffSquare[i] <== factorDiff[i] * factorDiff[i];
        tmpFactorCheck[i] <== 1 - factorDiffSquare[i];

        // Combine checks
        factorChecks[i] <== tmpFactorCheck[i] * nonZeroFactor[i] + (1 - nonZeroFactor[i]);

        // Accumulate checks
        accumulator[i + 1] <== accumulator[i] * factorChecks[i];
    }

    // Combine all checks
    isPrime <-- curveValidation.isValid * isOrderValid * accumulator[maxFactors];
}

// ECPP Verifier Main Template
template ECPPVerifier(nBits, maxPrimes, maxFactors) {
    signal input mainPrime;
    signal input base;
    signal input curveA[maxPrimes];
    signal input curveB[maxPrimes];
    signal input pointX[maxPrimes];
    signal input pointY[maxPrimes];
    signal input order[maxPrimes];
    signal input factors[maxPrimes][maxFactors];
    signal input exps[maxPrimes][maxFactors];
    signal output isPrime;

    component verifyStep[maxPrimes];
    signal recursiveCheck[maxPrimes];

    for (var i = 0; i < maxPrimes; i++) {
        verifyStep[i] = VerifyECPPStep(nBits, maxFactors);
        verifyStep[i].prime <== mainPrime;
        verifyStep[i].base <== base;
        verifyStep[i].factors <== factors[i];
        verifyStep[i].exps <== exps[i];
        verifyStep[i].curveA <== curveA[i];
        verifyStep[i].curveB <== curveB[i];
        verifyStep[i].pointX <== pointX[i];
        verifyStep[i].pointY <== pointY[i];
        verifyStep[i].order <== order[i];

        if (i == 0) {
            recursiveCheck[i] <== verifyStep[i].isPrime;
        } else {
            recursiveCheck[i] <== recursiveCheck[i - 1] * verifyStep[i].isPrime;
        }
    }

    isPrime <== recursiveCheck[maxPrimes - 1];
}

// Instantiate Main Circuit
component main {public [mainPrime, base, curveA, curveB, pointX, pointY, order, factors, exps]} = ECPPVerifier(256, 5, 5);
