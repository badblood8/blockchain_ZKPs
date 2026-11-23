pragma circom 2.0.6;

include "../lib/pratt.circom";

// Pratt certificate verifier for 32-bit primes.
//   9 certificate entries, up to 4 odd prime factors (with multiplicity) per p-1.
// Sized for inputs/pratt.json (a certificate for 8675309); generate others with
//   python3 scripts/pratt_certificate_generator.py <prime> --entries 9 --factors 4
// Only mainPrime is public; the certificate itself is private witness.
component main {public [mainPrime]} = PrattVerifier(32, 9, 4);
