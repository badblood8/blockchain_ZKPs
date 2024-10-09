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

// Rabin-Miller Primality Test
template RabinMillerPrimalityTest(k, nBits, maxRounds) {
    signal input n;
    signal input a[k];
    signal input d;
    signal input r;
    signal output isPrime;

    signal exponentResults[k];
    signal rabinMillerResults[k];
    signal isPrimeCheck[k];

    component modExp[k];
    component powerModExp[k][maxRounds];

    signal isOne[k];
    signal isNMinusOne[k];
    signal powerResults[k][maxRounds];
    signal tmpIsNMinusOne[k][maxRounds];
    signal conditionSignals[maxRounds];

    // Precompute the condition signals
    for (var j = 0; j < maxRounds; j++) {
        conditionSignals[j] <-- j < r ? 1 : 0;
    }

    for (var i = 0; i < k; i++) {
        modExp[i] = ModularExponentiation(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== d;
        modExp[i].mod <== n;

        exponentResults[i] <== modExp[i].result;
        isOne[i] <== 1 - (exponentResults[i] - 1) * (exponentResults[i] - 1);

        var nMinusOneAcc = 0; // Using var accumulator

        powerResults[i][0] <== exponentResults[i];

        for (var j = 1; j < maxRounds; j++) {
            powerModExp[i][j - 1] = ModularExponentiation(nBits);
            powerModExp[i][j - 1].base <== powerResults[i][j - 1];
            powerModExp[i][j - 1].exp <== 2;
            powerModExp[i][j - 1].mod <== n;
            powerResults[i][j] <== powerModExp[i][j - 1].result;

            var auxNMinusOne = 1 - (powerResults[i][j] - (n - 1)) * (powerResults[i][j] - (n - 1));
            nMinusOneAcc += conditionSignals[j] * auxNMinusOne;
        }

        isNMinusOne[i] <-- nMinusOneAcc;
        rabinMillerResults[i] <== isOne[i] + isNMinusOne[i] - isOne[i] * isNMinusOne[i];

        isPrimeCheck[i] <== i == 0 ? rabinMillerResults[i] : isPrimeCheck[i - 1] * rabinMillerResults[i];
    }

    isPrime <== isPrimeCheck[k - 1];
}

// Instantiate RabinMillerPrimalityTest with 10 bases and 256-bit exponentiation, max 20 rounds
component main {public [n, a]} = RabinMillerPrimalityTest(5, 128, 10);
