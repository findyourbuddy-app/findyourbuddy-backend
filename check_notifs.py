import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User
from app.models.notification import Notification

def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "engincts@gmail.com").first()
        if not user:
            print("[ERROR] User not found")
            return

        notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).all()
        print(f"Total notifications for {user.display_name}: {len(notifs)}")
        for n in notifs[:10]:
            print(f"ID: {n.id} | Title: {n.title} | event_id: {n.event_id} | notif_type: {n.notification_type} | data: {n.data}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
