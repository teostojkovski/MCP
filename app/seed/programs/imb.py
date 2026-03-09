"""IMB program seed: delegates to authoritative curriculum."""
from __future__ import annotations

from app.seed.curriculum_authoritative import IMB_NAME, seed_imb as _seed_imb


def seed_imb(session) -> None:
    """Resync IMB curriculum to the authoritative definition."""
    _seed_imb(session)


if __name__ == "__main__":
    from app.seed.base import run_seed
    run_seed(seed_imb)
