"""One-off retrofit tooling for the time-range-slots feature.

Parses legacy free-text slot descriptions into (start_time, duration_minutes),
backfills the new columns, and verifies before constraints are enforced.
"""
