"""PIT program seed: delegates to authoritative curriculum."""
from __future__ import annotations

from app.seed.curriculum_authoritative import PIT_NAME, seed_pit as _seed_pit


def seed_pit(session) -> None:
    """Resync PIT curriculum to the authoritative definition."""
    _seed_pit(session)


if __name__ == "__main__":
    from app.seed.base import run_seed
    run_seed(seed_pit)
