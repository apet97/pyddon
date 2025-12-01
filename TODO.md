# Production TODO

- [x] Tighten signature verification so `REQUIRE_SIGNATURE_VERIFICATION` is the only bypass switch (fixed in `clockify-python-addon/app/config.py` and `app/token_verification.py`).
- [x] Replace static RSA key in `clockify_core/security.py` with JWKS-based verification (configurable host, cached) to match the add-on implementation.
- [x] Implement optional Redis-backed distributed rate limiting for the add-on and shared services, keyed by workspace, controlled via config.
- [x] Run the full test matrix on Python 3.11 (`./scripts/test_all.sh` and `cd clockify-python-addon && PYTHONPATH=. pytest tests -v`); address any regressions.
- [x] Refresh docs to state signature verification must remain enabled outside local dev and to include the developer-workspace install steps (ngrok + manifest URL).
- [x] Add a concise deployment checklist covering TLS, DB migrations, health/ready/metrics probes, and log/metric shipping for production.
