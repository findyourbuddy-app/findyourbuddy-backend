"""One-off: recompute every user's trust score under the new derived model
(trust_service.compute_trust_score). Existing scores were an unbounded running
total seeded at 50; this rebuilds them from real signals, 0-100.

Usage:
    uv run python scripts/recompute_all_trust_scores.py            # dry run
    uv run python scripts/recompute_all_trust_scores.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.services.trust_service import compute_trust_score


def main(apply: bool) -> None:
    session = SessionLocal()
    try:
        users = session.query(User).order_by(User.id).all()
        changed = 0
        for user in users:
            new_score = compute_trust_score(session, user)
            if new_score != user.trust_score:
                changed += 1
                print(f"  #{user.id:<5} {user.trust_score:>4}  ->  {new_score:<4}  {user.email}")
                if apply:
                    user.trust_score = new_score
        if apply:
            session.commit()
            print(f"\nDone. Updated {changed}/{len(users)} users.")
        else:
            print(f"\nDry run: {changed}/{len(users)} would change. Re-run with --apply.")
    finally:
        session.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
