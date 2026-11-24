pragma circom 2.0.6;

include "../lib/modarith.circom";

// Rabin-Miller (strong probable prime) test, left-to-right, no explicit decomposition.
//
// n is accepted iff n is odd, and for every base a[i] with 2 <= a[i] <= n-2:
//     writing n-1 = d * 2^r with d odd, r >= 1,
//     a^d == 1 (mod n)           or
//     a^(d*2^j) == n-1 (mod n)   for some 0 <= j < r.
//
// Technique.  Let e = n - 1 and process its bits from the top.  After bit i the running value is
//     s_i = a^(e >> i)   (mod n).
// With r = the number of trailing zero bits of e,  s_r = a^d  and  s_(r-j) = a^(d*2^j), so
//     the base passes  <=>  s_r == 1   or   s_i == n-1 for some 1 <= i <= r.
// Nothing needs to be decomposed: z[i] = [the low i bits of e are all zero] = [i <= r] and
// atR[i] = z[i]*e[i] (the single position i = r) come straight from the bits of n.
// The prover only HINTS two things per base -- a boolean u ("s_r == 1") and a one-hot position idx -- and
// the circuit checks ONE equality per base:
//     (u ? s_r : s_idx)  ==  (u ? 1 : n-1).
// All s_i are < n < 2^32, so that field equality is an integer equality.
//
// What each constraint is for (see tests/model_check_rm.py, which checks every one exhaustively at 8 bits):
//   * n odd (bit 0)            NECESSARY: an even n has no valid decomposition, yet the chain would run.
//   * idx[i] <= z[i] (i <= r)  NECESSARY: s_i == n-1 for i > r is not evidence of primality.
//   * idx one-hot, u boolean   needed so that the selected value is exactly one s_i (or s_r).
//   * position i = 0 excluded  redundant (s_0 = a^(n-1) = -1 is impossible for odd n), omitted for size.
// A pass is probabilistic evidence of primality: at most 1/4 of bases are strong liars for a composite n,
// so k random bases leave error <= 4^-k (with fixed public bases an adversary can choose a pseudoprime).
template RabinMillerVerifier(k, nBits) {
    assert(k >= 1 && nBits >= 3 && nBits <= 125);

    signal input n;
    signal input a[k];

    // ---------- n: nBits wide and odd;  e = n - 1 has the same bits except bit 0
    component nBitsC = Num2Bits(nBits);
    nBitsC.in <== n;
    nBitsC.out[0] === 1;
    signal e[nBits];
    e[0] <== 0;
    for (var i = 1; i < nBits; i++) {
        e[i] <== nBitsC.out[i];
    }

    // z[i] = 1 iff the low i bits of e are all zero (i <= r);  atR[i] = 1 iff i == r
    signal z[nBits + 1];
    signal atR[nBits];
    z[0] <== 1;
    for (var i = 0; i < nBits; i++) {
        z[i + 1] <== z[i] * (1 - e[i]);
        atR[i] <== z[i] * e[i];
    }

    // ---------- per base
    component baseRange[k];
    component mulBy[k][nBits];     // x * m
    component square[k][nBits];    // x * x
    signal m[k][nBits];            // m[i][j] = a if e[j] else 1
    signal x[k][nBits];            // x[i][j] = s_j = a^(e >> j) mod n
    signal idx[k][nBits];          // idx[i][j] = 1 iff the hinted position is j  (j >= 1)
    signal sIdx[k];
    signal sR[k];
    signal u[k];
    signal cand[k];
    signal sIdxTerm[k][nBits];
    signal sRTerm[k][nBits];

    for (var i = 0; i < k; i++) {
        baseRange[i] = AssertBaseInRange(nBits);
        baseRange[i].a <== a[i];
        baseRange[i].n <== n;

        // x[i][j] = x[i][j+1]^2 * (e[j] ? a : 1), starting from s_nBits = 1
        for (var j = nBits - 1; j >= 0; j--) {
            m[i][j] <== 1 + e[j] * (a[i] - 1);
            if (j == nBits - 1) {
                x[i][j] <== m[i][j];                       // 1^2 * m
            } else {
                square[i][j] = ModMul(nBits);
                square[i][j].a <== x[i][j + 1];
                square[i][j].b <== x[i][j + 1];
                square[i][j].n <== n;
                if (j == 0) {
                    x[i][j] <== square[i][j].r;            // e[0] = 0, nothing to multiply
                } else {
                    mulBy[i][j] = ModMul(nBits);
                    mulBy[i][j].a <== square[i][j].r;
                    mulBy[i][j].b <== m[i][j];
                    mulBy[i][j].n <== n;
                    x[i][j] <== mulBy[i][j].r;
                }
            }
        }

        // hints: u = [s_r == 1];  idx = a position 1 <= j <= r with s_j == n-1 (any, if u)
        var rVal = 0;
        for (var j = 1; j < nBits; j++) {
            rVal += (atR[j] == 1) ? j : 0;
        }
        u[i] <-- (x[i][rVal] == 1) ? 1 : 0;
        var pick = 1;
        for (var j = nBits - 1; j >= 1; j--) {
            if (z[j] == 1 && x[i][j] == n - 1) {
                pick = j;
            }
        }
        idx[i][0] <== 0;
        for (var j = 1; j < nBits; j++) {
            idx[i][j] <-- (j == pick) ? 1 : 0;
        }

        u[i] * (u[i] - 1) === 0;

        // idx is boolean, one-hot, and only allowed where j <= r
        var idxSum = 0;
        for (var j = 1; j < nBits; j++) {
            idx[i][j] * (idx[i][j] - 1) === 0;
            idx[i][j] * (1 - z[j]) === 0;
            idxSum += idx[i][j];
        }
        idxSum === 1;

        // select s_idx and s_r
        var lcIdx = 0;
        var lcR = 0;
        for (var j = 1; j < nBits; j++) {
            sIdxTerm[i][j] <== idx[i][j] * x[i][j];
            sRTerm[i][j] <== atR[j] * x[i][j];
            lcIdx += sIdxTerm[i][j];
            lcR += sRTerm[i][j];
        }
        sIdx[i] <== lcIdx;
        sR[i] <== lcR;

        // the single check:  (u ? s_r : s_idx) == (u ? 1 : n-1)
        cand[i] <== sIdx[i] + u[i] * (sR[i] - sIdx[i]);
        cand[i] === (n - 1) + u[i] * (2 - n);
    }
}

// 10 bases, 32-bit n (the range supported by this build; the library caps at 125 bits).
// The proof exists only if every base passes.  Public inputs: n and the bases.
component main {public [n, a]} = RabinMillerVerifier(10, 32);
