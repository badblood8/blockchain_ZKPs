// File: multiply.circom

pragma circom 2.0.0;

template Multiply() {
    signal input p;
    signal input q;
    signal output N;

    N <== p * q;
}

component main = Multiply();
