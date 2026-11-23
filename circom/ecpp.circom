pragma circom 2.0.6;

include "../lib/modarith.circom";

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
    component modExpMain = ModExp(nBits);
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
        modExpFactor[i] = ModExp(nBits);
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
    signal stepCheck;
    stepCheck <== curveValidation.isValid * isOrderValid;
    isPrime <== stepCheck * accumulator[maxFactors];
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

// Top-level circuit: the proof exists only if every step checks (isPrime == 1).
template ECPPMain(nBits, maxPrimes, maxFactors) {
    signal input mainPrime;
    signal input base;
    signal input curveA[maxPrimes];
    signal input curveB[maxPrimes];
    signal input pointX[maxPrimes];
    signal input pointY[maxPrimes];
    signal input order[maxPrimes];
    signal input factors[maxPrimes][maxFactors];
    signal input exps[maxPrimes][maxFactors];

    component cert = ECPPVerifier(nBits, maxPrimes, maxFactors);
    cert.mainPrime <== mainPrime;
    cert.base <== base;
    cert.curveA <== curveA;
    cert.curveB <== curveB;
    cert.pointX <== pointX;
    cert.pointY <== pointY;
    cert.order <== order;
    cert.factors <== factors;
    cert.exps <== exps;
    cert.isPrime === 1;
}

component main {public [mainPrime, base, curveA, curveB, pointX, pointY, order, factors, exps]} = ECPPMain(32, 5, 5);
