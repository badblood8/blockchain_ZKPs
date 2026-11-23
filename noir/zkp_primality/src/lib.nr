// Zero-knowledge primality building blocks (Noir + noir-bignum).
//
//   native      : <= 64-bit numbers with u128 arithmetic (trial division, Pocklington step)
//   pocklington : the same step for 120+ bit numbers over RuntimeBigNum
//
// Pocklington's criterion (the efficient cousin of a Pratt certificate): if n - 1 = F * e,
// F is prime and F > sqrt(n), and there is a base a with
//         a^(n-1) = 1 (mod n)    and    gcd(a^((n-1)/F) - 1, n) = 1,
// then n is prime.  (F prime and F > sqrt(n) force gcd(F, e) = 1 because e < sqrt(n) < F.)
// Chaining steps from a trivially certified small prime proves large primes
// deterministically: no error probability and no Fiat-Shamir grinding.
pub mod native;
pub mod pocklington;
