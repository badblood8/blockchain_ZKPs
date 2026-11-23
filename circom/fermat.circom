pragma circom 2.0.6;

include "../lib/modarith.circom";

// Fermat Primality Test
template FermatPrimalityTest(k, nBits) {
    signal input n;              // The number to be tested for primality
    signal input a[k];           // Array of random bases for testing
    signal output isPrime;       // Output: 1 if likely prime, 0 if composite
    signal exponentResults[k];   // Results of modular exponentiations
    signal fermatResults[k];     // Intermediate Fermat test results for each base
    signal isPrimeCheck[k];      // Accumulated prime check at each stage

    // Declare components for modular exponentiation
    component modExp[k];

    // Initialize isPrimeCheck[0] to 1 (assuming the number is prime)
    isPrimeCheck[0] <== 1;

    for (var i = 0; i < k; i++) {
        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== n - 1;
        modExp[i].mod <== n;

        // Store the result of each modular exponentiation
        exponentResults[i] <== modExp[i].result;

        // Set fermatResults[i] to 1 if exponentResults[i] == 1, otherwise 0
        fermatResults[i] <== 1 - (exponentResults[i] - 1) * (exponentResults[i] - 1);

        // Calculate isPrimeCheck[i] based on isPrimeCheck[i-1] and fermatResults[i]
        if (i > 0) {
            isPrimeCheck[i] <== isPrimeCheck[i - 1] * fermatResults[i];
        }
    }

    // Set final output isPrime based on the last value of isPrimeCheck
    isPrime <== isPrimeCheck[k - 1];
}

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
template FermatVerifier(k, nBits) {
    signal input n;
    signal input a[k];

    component test = FermatPrimalityTest(k, nBits);
    test.n <== n;
    test.a <== a;
    test.isPrime === 1;
}

component main {public [n, a]} = FermatVerifier(25, 32);
