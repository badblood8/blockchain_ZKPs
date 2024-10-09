import json
import sympy

def compute_factors_and_exponents(prime, max_factors=5):
    """Compute prime factors and corresponding exponents for Pratt certificate."""
    factors = []
    exponents = []
    n = prime - 1
    for p in sympy.primefactors(n):
        factors.append(p)
        exponents.append(n // p)
    # Ensure each list is exactly `max_factors` length
    factors += [0] * (max_factors - len(factors))
    exponents += [0] * (max_factors - len(exponents))
    return factors[:max_factors], exponents[:max_factors]

def generate_pratt_certificate(prime, max_factors=5, max_primes=10):
    """Generate Pratt certificate data with no duplicate primes or extraneous factors."""
    cert_primes = []
    cert_factors = []
    cert_exponents = []
    visited_primes = set()  # To keep track of primes already processed
    stack = [prime]

    while stack and len(cert_primes) < max_primes:
        p = stack.pop()
        if p in visited_primes:
            continue  # Skip if already processed
        visited_primes.add(p)

        if not sympy.isprime(p):
            raise ValueError(f"{p} is not prime.")

        # Add the prime and its factors and exponents
        cert_primes.append(p)
        factors, exponents = compute_factors_and_exponents(p, max_factors)
        cert_factors.append(factors)
        cert_exponents.append(exponents)

        # Add the unique prime factors to the stack if they have not been processed
        for factor in factors:
            if factor > 1 and factor not in visited_primes:
                stack.append(factor)

    # Pad to ensure each list has exactly `max_primes` entries
    for _ in range(max_primes - len(cert_primes)):
        cert_primes.append(0)
        cert_factors.append([0] * max_factors)
        cert_exponents.append([0] * max_factors)

    return cert_primes, cert_factors, cert_exponents

def generate_json(prime, base, max_primes=5, max_factors=5):
    """Generate Pratt certificate JSON with specified base and main prime."""
    cert_primes, cert_factors, precomputed_exps = generate_pratt_certificate(
        prime, max_factors=max_factors, max_primes=max_primes
    )
    data = {
        "mainPrime": prime,
        "base": base,
        "certPrimes": cert_primes,
        "certFactors": cert_factors,
        "precomputedExps": precomputed_exps
    }
    return data

# Main execution to generate JSON
main_prime = 8675309
base = 2
pratt_certificate_data = generate_json(main_prime, base, max_primes=6, max_factors=6)

# Write to JSON file
with open("inputs/pratt.json", "w") as file:
    json.dump(pratt_certificate_data, file, indent=4)

print("Generated Pratt certificate JSON:")
print(json.dumps(pratt_certificate_data, indent=4))
