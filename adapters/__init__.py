"""Adapters package (BUILD-SPEC §4).

`base.py` holds the protocol + shared machinery (circuit breaker, idempotency
store, backoff). `contract.py` holds the one contract suite every adapter —
fake or real — must pass. Real adapters land in their own modules at VS-3;
their fakes live in sim/fakes/ and pass the same suite.
"""
