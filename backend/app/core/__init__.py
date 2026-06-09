"""Cross-cutting core for the backend (DESIGN §4).

Home of config (`config.py`, PR2), the DB session (`db.py`, PR4), the error
envelope handler (`errors.py`, PR5), idempotency, and shared dependencies.
Empty in M0 beyond this package marker — each lands in its own M0 PR.
"""
