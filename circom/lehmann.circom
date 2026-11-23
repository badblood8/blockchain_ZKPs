pragma circom 2.0.6;

include "../lib/modarith.circom";

// Lehmann Primality Test
template LehmannPrimalityTest(k, nBits) {
    signal input n;              // The number to be tested for primality
    signal input a[k];           // Array of random bases for testing
    signal output isPrime;       // Output: 1 if likely prime, 0 if composite
    signal exponentResults[k];   // Results of modular exponentiations
    signal lehmannResults[k];    // Intermediate Lehmann test results for each base
    signal isPrimeCheck[k];      // Accumulated prime check at each stage

    // Declare components for modular exponentiation
    component modExp[k];

    // Initialize isPrimeCheck[0] to 1 (assuming the number is prime)
    isPrimeCheck[0] <== 1;

    // Predeclare isOne and isNMinusOne signals outside the loop
    signal isOne[k];
    signal isNMinusOne[k];

    for (var i = 0; i < k; i++) {
        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== (n - 1) / 2; // Set the exponent to (n-1)/2 for Lehmann test
        modExp[i].mod <== n;

        // Store the result of each modular exponentiation
        exponentResults[i] <== modExp[i].result;

        // Check if exponentResults[i] == 1
        isOne[i] <== 1 - (exponentResults[i] - 1) * (exponentResults[i] - 1);

        // Check if exponentResults[i] == (n - 1)
        isNMinusOne[i] <== 1 - (exponentResults[i] - (n - 1)) * (exponentResults[i] - (n - 1));

        // Set lehmannResults[i] to 1 if either isOne or isNMinusOne is true (logical OR)
        lehmannResults[i] <== isOne[i] + isNMinusOne[i] - isOne[i] * isNMinusOne[i];

        // Calculate isPrimeCheck[i] based on isPrimeCheck[i-1] and lehmannResults[i]
        if (i > 0) {
            isPrimeCheck[i] <== isPrimeCheck[i - 1] * lehmannResults[i];
        }
    }

    // Set final output isPrime based on the last value of isPrimeCheck
    isPrime <== isPrimeCheck[k - 1];
}

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
template LehmannVerifier(k, nBits) {
    signal input n;
    signal input a[k];

    component test = LehmannPrimalityTest(k, nBits);
    test.n <== n;
    test.a <== a;
    test.isPrime === 1;
}

component main {public [n, a]} = LehmannVerifier(10, 32);
