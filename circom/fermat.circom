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

    // Convert the exponent to binary bits using Num2Bits
    component expBits = Num2Bits(nBits);
    expBits.in <== exp;

    // Declare and initialize signals for intermediate steps outside of the loop
    signal tmpResults[nBits + 1];
    signal currentBases[nBits + 1];
    signal applyMultiplier[nBits];

    // Initialize initial conditions
    tmpResults[0] <== 1;           // Initial result is 1
    currentBases[0] <== base;       // Start base is the input base

    for (var i = 0; i < nBits; i++) {
        // Step 1: Set applyMultiplier based on expBits.out[i]
        applyMultiplier[i] <-- expBits.out[i] == 1 ? currentBases[i] : 1;

        // Step 2: Multiply tmpResults by applyMultiplier conditionally
        tmpResults[i + 1] <-- (tmpResults[i] * applyMultiplier[i]) % mod;

        // Step 3: Square the base for the next iteration
        currentBases[i + 1] <-- (currentBases[i] * currentBases[i]) % mod;
    }

    // Assign the final result
    result <== tmpResults[nBits];
}



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
        modExp[i] = ModularExponentiation(nBits);
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



// Instantiate FermatPrimalityTest with 3 random bases and 256-bit exponentiation
component main {public [n, a]} = FermatPrimalityTest(25, 256);
