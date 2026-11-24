pragma circom 2.0.6;

include "modarith.circom";

// Pratt primality certificates (Lucas' converse of Fermat's little theorem):
//
//   p > 2 is prime  <=>  there is g with  g^(p-1) = 1 (mod p)  and
//                        g^((p-1)/q) != 1 (mod p)  for EVERY prime q | p-1,
//   and each such q is itself proven prime (recursively; 2 is the base case).
//
// A certificate is a flat list of M entries.  Entry i is a prime p_i, a base g_i
// and the odd prime factors of p_i - 1 listed with multiplicity (padded with 1):
//
//        p_i - 1  =  2^s * q_0 * q_1 * ... * q_{F-1}          (exact integer equality)
//
// Soundness argument (all of it enforced by constraints below):
//   1. For each entry, the listed q's plus the power of two multiply to exactly
//      p_i - 1, so if every q is prime they are ALL the prime divisors of p_i - 1.
//   2. Every non-padding q must equal the prime of some entry (membership).
//      Since q divides p_i - 1 we have q < p_i, so induction on the VALUE of p
//      proves every entry prime: the smallest entry can only have q's equal to
//      itself-or-smaller entries, i.e. none, hence p - 1 is a pure power of two.
//      No ordering or cycle check is therefore needed.
//   3. The Lucas conditions on g_i then give p_i prime.
//
// Padding: unused entries are the valid entry (p=3, g=2, no odd factors), so no
// division by zero / mod 0 ever occurs.
//
// Limits: all numbers are nBits-bit (nBits <= 125, see modarith.circom).  M bounds
// the certificate size and F bounds the number of odd prime factors (with
// multiplicity) of any p_i - 1; a certificate that does not fit has no witness.
// Cost: about (F + 1) * (4 nBits^2 + 13 nBits) constraints per entry.

// One entry of the certificate.  `allP` is the full list of entry primes
// (for the membership check).  The template has no outputs: if it is
// instantiated, the entry MUST verify.
template PrattEntry(nBits, F, M) {
    assert(nBits >= 3 && nBits <= 125);
    assert(F >= 1 && M >= 1);
    var maxS = nBits - 1;

    signal input p;
    signal input g;
    signal input q[F];
    signal input allP[M];

    // ---------- 2-adic part: p - 1 = 2^s * (odd part), s in [1, maxS] one-hot
    var s0 = twoAdicValuation(p - 1);
    signal sel[maxS + 1];
    sel[0] <== 0;
    var selSum = 0;
    var pow2sLc = 0;
    for (var j = 1; j <= maxS; j++) {
        sel[j] <-- (j == s0) ? 1 : 0;
        sel[j] * (sel[j] - 1) === 0;
        selSum += sel[j];
        pow2sLc += sel[j] * (2 ** j);
    }
    selSum === 1;
    signal pow2s;
    pow2s <== pow2sLc;

    // ---------- exact factorization: 2^s * q_0 * ... * q_{F-1} == p - 1
    // Each partial product is range-checked to nBits bits so that no product of
    // two nBits-bit numbers can wrap around the field.
    signal prod[F + 1];
    component prodRange[F];
    prod[0] <== pow2s;
    for (var l = 0; l < F; l++) {
        prod[l + 1] <== prod[l] * q[l];
        prodRange[l] = AssertBits(nBits);
        prodRange[l].in <== prod[l + 1];
    }
    prod[F] === p - 1;

    // ---------- Lucas condition for q = 2:  h = g^((p-1)/2) != 1  and  h^2 = 1
    signal exp2;
    exp2 <-- (p - 1) \ 2;
    2 * exp2 === p - 1;

    component hExp = ModExp(nBits);            // also enforces 2 <= p < 2^nBits, g < p
    hExp.base <== g;
    hExp.exp <== exp2;
    hExp.mod <== p;

    component hIsOne = IsEqual();
    hIsOne.in[0] <== hExp.result;
    hIsOne.in[1] <== 1;
    hIsOne.out === 0;

    component hSq = ModMul(nBits);             // g^(p-1) == 1
    hSq.a <== hExp.result;
    hSq.b <== hExp.result;
    hSq.n <== p;
    hSq.r === 1;

    // ---------- Lucas condition and membership for every odd factor slot
    component isPad[F];                        // q == 1 : unused slot
    component isDup[F];                        // q == previous q : already checked
    component slotExp[F];
    component slotIsOne[F];
    component member[F][M];
    component noMember[F];
    signal exps[F];
    signal needsCheck[F];
    signal memberSum[F];

    for (var l = 0; l < F; l++) {
        isPad[l] = IsEqual();
        isPad[l].in[0] <== q[l];
        isPad[l].in[1] <== 1;

        // exps[l] = (p-1)/q[l], exactly
        exps[l] <-- (p - 1) \ q[l];
        exps[l] * q[l] === p - 1;

        slotExp[l] = ModExp(nBits);
        slotExp[l].base <== g;
        slotExp[l].exp <== exps[l];
        slotExp[l].mod <== p;

        slotIsOne[l] = IsEqual();
        slotIsOne[l].in[0] <== slotExp[l].result;
        slotIsOne[l].in[1] <== 1;

        // g^((p-1)/q) != 1 is required unless the slot is padding or repeats the
        // previous slot's q (a prover cannot skip a check: the flag is derived).
        if (l == 0) {
            needsCheck[l] <== 1 - isPad[l].out;
        } else {
            isDup[l] = IsEqual();
            isDup[l].in[0] <== q[l];
            isDup[l].in[1] <== q[l - 1];
            needsCheck[l] <== (1 - isPad[l].out) * (1 - isDup[l].out);
        }
        needsCheck[l] * slotIsOne[l].out === 0;

        // membership: a non-padding q must be the prime of some entry
        var eqSum = 0;
        for (var j = 0; j < M; j++) {
            member[l][j] = IsEqual();
            member[l][j].in[0] <== q[l];
            member[l][j].in[1] <== allP[j];
            eqSum += member[l][j].out;
        }
        memberSum[l] <== eqSum;
        noMember[l] = IsZero();
        noMember[l].in <== memberSum[l];
        (1 - isPad[l].out) * noMember[l].out === 0;
    }
}

// Whole certificate.  Only `mainPrime` needs to be public; the rest is witness.
template PrattVerifier(nBits, M, F) {
    signal input mainPrime;
    signal input certPrimes[M];
    signal input certBases[M];
    signal input certFactors[M][F];

    mainPrime === certPrimes[0];

    component entry[M];
    for (var i = 0; i < M; i++) {
        entry[i] = PrattEntry(nBits, F, M);
        entry[i].p <== certPrimes[i];
        entry[i].g <== certBases[i];
        entry[i].q <== certFactors[i];
        entry[i].allP <== certPrimes;
    }
}
