# Groth16 pipeline for the Circom circuits (one Makefile for all of them) and the test entry points.
#
#   make CIRCUIT=rabin_miller all        compile, witness, setup, proof, verify, metrics
#   make CIRCUIT=pratt PROVER=rapidsnark RAPIDSNARK_DIR=/path/to/rapidsnark proof
#   make doctor                          which tools are installed
#   make test                            tests that need only python3 + sympy
#   make test-circom / test-noir         tests that need circom+snarkjs / nargo+bb
#
# Circuits: multiply fermat lehmann rabin_miller pratt ecpp   (see circom/, inputs/)
# Each circuit builds in build/<circuit>/, so circuits never overwrite each other.
#
# Ceremony file: a hash-verified Hermez "powers of tau" file is looked up in $(PTAU_DIR)/ and reused (see
# docs/TOOLCHAIN.md for why the official hosts cannot be relied on).  Its size is computed from the circuit.
# ALLOW_LOCAL_PTAU=1 generates an INSECURE single-party ceremony instead (development only).

CIRCUIT          ?= rabin_miller
CIRCOM           ?= circom
CIRCOM_FLAGS     ?= --O2
SNARKJS          ?= snarkjs
PROVER           ?= snarkjs
RAPIDSNARK_DIR   ?=
PTAU_DIR         ?= ptau
ALLOW_LOCAL_PTAU ?= 0
PYTHON           ?= python3

ZK      := $(PYTHON) scripts/zk.py
BUILD   := build/$(CIRCUIT)
SRC     := circom/$(CIRCUIT).circom
INPUT   := inputs/$(CIRCUIT).json
R1CS    := $(BUILD)/$(CIRCUIT).r1cs
WASM    := $(BUILD)/$(CIRCUIT)_js/$(CIRCUIT).wasm
WTNS    := $(BUILD)/witness.wtns
ZKEY    := $(BUILD)/$(CIRCUIT)_final.zkey
VK      := $(BUILD)/verification_key.json
PROOF   := $(BUILD)/proof.json
PUBLIC  := $(BUILD)/public.json
METRICS := $(BUILD)/metrics.json

.PHONY: all compile witness setup proof verify metrics clean doctor test test-python test-circom test-noir list check-circuit

all: compile witness setup proof verify metrics

check-circuit:
	@test -f $(SRC) || { echo "unknown circuit '$(CIRCUIT)'. Available:"; ls circom | sed 's/\.circom//;s/^/  /'; exit 1; }
	@test -f $(INPUT) || { echo "missing $(INPUT)"; exit 1; }

list:
	@ls circom | sed 's/\.circom//'

compile: check-circuit
	@mkdir -p $(BUILD)
	@echo "Compiling $(SRC) with $(CIRCOM) $(CIRCOM_FLAGS)"
	$(CIRCOM) $(SRC) --r1cs --wasm --sym $(CIRCOM_FLAGS) -o $(BUILD)

witness: $(R1CS)
	@echo "Generating witness for $(CIRCUIT)"
	node $(BUILD)/$(CIRCUIT)_js/generate_witness.js $(WASM) $(INPUT) $(WTNS)

$(R1CS):
	@$(MAKE) --no-print-directory CIRCUIT=$(CIRCUIT) compile

# Phase 1 + 2 setup.  A verified Hermez ceremony file is reused; the zkey gets a fresh random contribution.
setup: $(R1CS)
	@$(SNARKJS) r1cs info $(R1CS) > $(BUILD)/r1cs_info.txt 2>&1
	@POWER=$$($(ZK) pot-level $(BUILD)/r1cs_info.txt); \
	echo "$(CIRCUIT) needs a powers-of-tau ceremony of power $$POWER"; \
	PTAU=$$($(ZK) ptau $$POWER --dir $(PTAU_DIR) 2>/dev/null || $(ZK) fetch-ptau $$POWER --dir $(PTAU_DIR) 2>/dev/null); \
	if [ -z "$$PTAU" ]; then \
	  if [ "$(ALLOW_LOCAL_PTAU)" = "1" ]; then \
	    echo "!!! generating an INSECURE single-party ceremony (development only) !!!"; \
	    mkdir -p $(PTAU_DIR); PTAU=$(PTAU_DIR)/local_$$POWER.ptau; \
	    $(SNARKJS) powersoftau new bn128 $$POWER $(BUILD)/pot_0000.ptau; \
	    $(SNARKJS) powersoftau contribute $(BUILD)/pot_0000.ptau $(BUILD)/pot_0001.ptau --name=local --entropy="$$(head -c 32 /dev/urandom | base64)"; \
	    $(SNARKJS) powersoftau prepare phase2 $(BUILD)/pot_0001.ptau $$PTAU; \
	  else \
	    echo "No hash-verified ceremony file of power >= $$POWER in $(PTAU_DIR)/."; \
	    echo "  Put powersOfTau28_hez_final_$$POWER.ptau there (see docs/TOOLCHAIN.md), or run with ALLOW_LOCAL_PTAU=1."; \
	    exit 1; \
	  fi; \
	fi; \
	echo "using ceremony file $$PTAU"; \
	$(ZK) timed $(METRICS) setup -- $(SNARKJS) groth16 setup $(R1CS) $$PTAU $(BUILD)/$(CIRCUIT)_0000.zkey && \
	$(SNARKJS) zkey contribute $(BUILD)/$(CIRCUIT)_0000.zkey $(ZKEY) --name="contribution" --entropy="$$(head -c 32 /dev/urandom | base64)" && \
	$(SNARKJS) zkey export verificationkey $(ZKEY) $(VK)
	@test -s $(ZKEY) || { echo "setup produced no zkey (snarkjs prints [ERROR] but exits 0)"; exit 1; }

proof: $(WTNS) $(ZKEY)
	@echo "Proving $(CIRCUIT) with $(PROVER)"
ifeq ($(PROVER),rapidsnark)
	$(ZK) timed $(METRICS) prove -- $(RAPIDSNARK_DIR)/bin/prover $(ZKEY) $(WTNS) $(PROOF) $(PUBLIC)
else
	$(ZK) timed $(METRICS) prove -- $(SNARKJS) groth16 prove $(ZKEY) $(WTNS) $(PROOF) $(PUBLIC)
endif
	@test -s $(PROOF) || { echo "no proof produced"; exit 1; }

$(WTNS):
	@$(MAKE) --no-print-directory CIRCUIT=$(CIRCUIT) witness
$(ZKEY):
	@$(MAKE) --no-print-directory CIRCUIT=$(CIRCUIT) setup

verify: $(PROOF)
	@echo "Verifying $(CIRCUIT)"
ifeq ($(PROVER),rapidsnark)
	$(ZK) timed $(METRICS) verify -- $(RAPIDSNARK_DIR)/bin/verifier $(VK) $(PUBLIC) $(PROOF)
else
	$(ZK) timed $(METRICS) verify -- $(SNARKJS) groth16 verify $(VK) $(PUBLIC) $(PROOF)
endif

metrics:
	@echo "== $(CIRCUIT): sizes (bytes)"
	@for f in $(PROOF) $(PUBLIC) $(VK) $(ZKEY) $(R1CS) $(WASM); do printf "  %-48s %s\n" $$f $$(wc -c < $$f | tr -d ' '); done
	@echo "== $(CIRCUIT): times and peak memory"
	@cat $(METRICS)

clean:
	@test -n "$(BUILD)" && test "$(BUILD)" != "build/" && rm -rf "$(BUILD)"
	@echo "removed $(BUILD) (ceremony files in $(PTAU_DIR)/ are kept)"

doctor:
	@$(ZK) doctor

# ---------------------------------------------------------------- tests
test: test-python

# no circom/nargo needed: reference verifiers, generators and exhaustive models
test-python:
	$(PYTHON) tests/test_scripts.py
	$(PYTHON) tests/test_pratt.py GeneratorTests
	$(PYTHON) tests/model_check_rm.py
	$(PYTHON) noir/prime_chain/model_check.py 800
	$(PYTHON) noir/ecpp_chain/test_reference.py

# needs circom + snarkjs + node (set CIRCOM / PATH): library, Fermat/Lehmann/Rabin-Miller, Pratt
test-circom:
	$(PYTHON) tests/test_lib.py
	$(PYTHON) tests/test_primality.py
	$(PYTHON) tests/test_pratt.py

# needs nargo 1.0.0 (NARGO=/path/to/nargo): Pocklington, semiprime and ECPP circuits
test-noir:
	cd noir && NARGO=$${NARGO:-nargo} $(PYTHON) test_steps.py
	cd noir && NARGO=$${NARGO:-nargo} $(PYTHON) test_chain.py
	cd noir && NARGO=$${NARGO:-nargo} $(PYTHON) test_semiprime.py
	cd noir && NARGO=$${NARGO:-nargo} $(PYTHON) test_ecpp.py
	cd experiments/noir_rabin_miller_32 && $${NARGO:-nargo} test
	cd experiments/noir_rabin_miller_256 && NARGO=$${NARGO:-nargo} $(PYTHON) test_noir.py
	cd experiments/noir_rabin_miller_256 && $(PYTHON) model_check.py
