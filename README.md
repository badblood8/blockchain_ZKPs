
# Cryptographic Banking Application: Zero-Knowledge Proof for \( N = p*q \) with Large Prime Factors

In this project, we explore various primality testing methods as foundational components in cryptographic banking applications. Specifically, we implement Zero-Knowledge Proofs (ZKPs) to verify the primality of large numbers, with a final objective of constructing a ZKP to validate \( N = p*q \), where \( p \) and \( q \) are large primes.

Circom is used to implement these proofs, and this repository contains both the circuits and scripts to generate and verify certificates of primality. Contributions for optimization and further testing are welcome.

---

## Circom Installation

Refer to the official Circom documentation for installation: [Circom Documentation](https://docs.circom.io/)

---

## Primality Testing Methods

1. **Fermat Primality Test**  
   - **Algorithm**: Uses Fermat's Little Theorem, asserting that if \( a^{n-1} \equiv 1 \ (	ext{mod} \ n) \) for several random bases \( a \), \( n \) is likely prime.  
   - **Pros**: Simple and efficient for small numbers.  
   - **Cons**: Can produce pseudoprimes, which falsely pass as primes.

2. **Lehmann Primality Test**  
   - **Algorithm**: Combines Fermat's method with an additional condition: for a chosen base \( a \), \( a^{(n-1)/2} \) should be \( \pm1 \ (	ext{mod} \ n) \).  
   - **Pros**: More accurate than Fermat’s test.  
   - **Cons**: Still not fully reliable for all composites.

3. **Rabin-Miller Primality Test**  
   - **Algorithm**: A probabilistic test that decomposes \( n-1 \) into \( 2^s \cdot d \) and checks bases \( a \) for nontrivial square roots of 1 mod \( n \).  
   - **Pros**: Highly accurate and widely used in practice.  
   - **Cons**: Probabilistic, though accuracy improves with more rounds.

4. **Pratt Primality Certificate**  
   - **Algorithm**: A deterministic method based on recursively proving the primality of factors of \( n-1 \) and confirming nontrivial roots modulo \( n \).  
   - **Pros**: Offers a certificate of primality, verifiable in polynomial time.  
   - **Cons**: Computationally intense for very large numbers.

5. **ECPP (Elliptic Curve Primality Proving)**  
   - **Algorithm**: Uses elliptic curves and their properties to construct primality certificates, verifying that a given number \( n \) satisfies specific elliptic curve constraints and group order conditions.  
   - **Pros**: Offers deterministic certificates and is highly scalable for large inputs.  
   - **Cons**: Requires advanced mathematical constructs and more complex computations than Pratt certificates.

---

## Project Structure

- **scripts/**: Python scripts implementing each primality test and generating certificates (for Pratt and ECPP).  
- **circom/**: Circom circuits for each test, enabling ZKP generation.  
- **makefiles/**: Scripts to run each method, step-by-step or in batch.  
- **inputs/**: JSON input files, e.g., `pratt.json` and `ecpp.json`, containing values and certificates.

---

## Usage

To use a specific test, e.g., the Pratt certificate, run the following:

```bash
make -f makefiles/makefile_pratt
```

To use the ECPP certificate:

```bash
make -f makefiles/makefile_ecpp
```

To clean up generated files:

```bash
make -f makefiles/makefile_pratt clean
make -f makefiles/makefile_ecpp clean
```

Run each test with caution as large inputs require high processing power.

---

## Proof Size and Proving Time

To measure the proof size and proving time, the makefiles include commands for time tracking. After running the proof generation step, it will output the time taken (in milliseconds or seconds depending on the system) and the size of the generated proof.

Example commands for ECPP:

```bash
make -f makefiles/makefile_ecpp proof
make -f makefiles/makefile_ecpp metrics
```

This will display the proving time and proof size in the output.

---

## Contributions

This repository is an evolving project with a focus on cryptographic banking applications. Code is not fully optimized, and contributions are welcome to enhance performance and functionality.

---

## Citation

Circom and SnarkJS are core components. Please refer to [Circom Documentation](https://docs.circom.io/) for usage and API references.

---
