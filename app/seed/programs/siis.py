"""SIIS program seed: delegates to authoritative curriculum."""
from __future__ import annotations

from app.seed.curriculum_authoritative import SIIS_NAME, seed_siis as _seed_siis


def seed_siis(session) -> None:
    """Resync SIIS curriculum to the authoritative definition."""
    _seed_siis(session)


if __name__ == "__main__":
    from app.seed.base import run_seed
    run_seed(seed_siis)
