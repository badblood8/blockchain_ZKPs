pragma circom 2.0.6;

include "../lib/modarith.circom";

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
        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== d;
        modExp[i].mod <== n;

        exponentResults[i] <== modExp[i].result;
        isOne[i] <== 1 - (exponentResults[i] - 1) * (exponentResults[i] - 1);

        var nMinusOneAcc = 0; // Using var accumulator

        powerResults[i][0] <== exponentResults[i];

        for (var j = 1; j < maxRounds; j++) {
            powerModExp[i][j - 1] = ModExp(nBits);
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

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
template RabinMillerVerifier(k, nBits, maxRounds) {
    signal input n;
    signal input a[k];
    signal input d;
    signal input r;

    component test = RabinMillerPrimalityTest(k, nBits, maxRounds);
    test.n <== n;
    test.a <== a;
    test.d <== d;
    test.r <== r;
    test.isPrime === 1;
}

component main {public [n, a]} = RabinMillerVerifier(5, 32, 10);
