# Primality Testing with Zero-Knowledge Proofs (ZKPs)

This repository provides implementations of various primality tests using Circom for zk-SNARKs (Zero-Knowledge Succinct Non-Interactive Arguments of Knowledge). Primality tests implemented here include **Fermat**, **Lehmann**, **Rabin-Miller**, and **Pratt Certificate** checks, with each method offering unique reliability, complexity, and cryptographic suitability.

## Table of Contents

1. [Overview of Primality Tests](#overview-of-primality-tests)
2. [Project Structure](#project-structure)
3. [Getting Started](#getting-started)
4. [Running the Tests](#running-the-tests)
5. [Contribution Guidelines](#contribution-guidelines)
6. [References](#references)

---

## Overview of Primality Tests

### 1. Fermat Primality Test
   - **Description**: Based on Fermat’s Little Theorem, it checks if \( a^{n-1} \equiv 1 \mod n \) for a base \( a \).
   - **Pros**: Simple and quick.
   - **Cons**: Weak against pseudoprimes; limited accuracy for cryptographic applications.

### 2. Lehmann Primality Test
   - **Description**: Verifies \( a^{(n-1)/2} \equiv \pm 1 \mod n \) for multiple bases \( a \), enhancing the reliability.
   - **Pros**: Stronger accuracy than Fermat with multiple bases.
   - **Cons**: Probabilistic; requires several bases for higher reliability.

### 3. Rabin-Miller Primality Test
   - **Description**: Uses a decomposition of \( n-1 = 2^s \times d \), examining sequences of powers to identify compositeness.
   - **Pros**: High accuracy with multiple bases; commonly used in cryptography.
   - **Cons**: Computationally intensive, especially for large primes.

### 4. Pratt Certificate (Deterministic Proof)
   - **Description**: A deterministic method where primality is proven through recursive verification of smaller prime factors in \( n-1 \).
   - **Pros**: Full proof of primality, free from pseudoprimes.
   - **Cons**: Recursive and computationally intensive.

---

## Project Structure

- **circom/**: Contains `.circom` circuit files implementing each primality test. Each file defines constraints necessary for verifying a number's primality.
- **inputs/**: JSON input files for each circuit, providing bases, primes, and factors as needed for each test.
- **scripts/**: Python scripts for running each primality test individually. Also contains a certificate generator for Pratt’s test, which outputs `pratt.json` to be used as input for the Pratt circuit.
- **makefiles/**: Makefiles for compiling, generating witnesses, setting up circuits, creating proofs, and verifying proofs for each test (e.g., `makefile_pratt` for the Pratt certificate test).

---

## Getting Started

### Requirements

- Install **Circom** following the [Circom Documentation](https://docs.circom.io/) to set up your environment.
- Ensure that Node.js and `snarkjs` are installed, as they are used for generating witnesses and proof verification.

---

## Running the Tests

Each test has an associated makefile, allowing for step-by-step execution. To run the circuits:

1. **Compile and run the test**: Replace `makefile_pratt` with the appropriate makefile for the specific test.
   
   ```bash
   make -f makefiles/makefile_pratt
   ```

2. **Clean build files** (optional):
   
   ```bash
   make -f makefiles/makefile_pratt clean
   ```

---

### Note

Larger inputs generate higher constraint counts and may require significant CPU power. Start with smaller inputs to verify compatibility with your system.

---

## Contribution Guidelines

These implementations are currently under development and lack optimization. Contributions for performance enhancements or additional features are highly encouraged!

---

## References

This project uses Circom for zk-SNARK proof generation. For more details on Circom, see the [Circom Documentation](https://docs.circom.io/).