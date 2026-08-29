import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User
from app.models.event import Event
from app.models.event_attendance import EventAttendance

def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "engincts@gmail.com").first()
        if not user:
            print("[ERROR] User engincts@gmail.com not found!")
            return

        catan_event = db.query(Event).filter(Event.title.ilike("%catan%")).first()
        if not catan_event:
            print("[ERROR] Catan event not found!")
            return

        print(f"[FOUND] Event ID: {catan_event.id}, Title: {catan_event.title}")

        # Approve all pending attendances for Catan event
        attendances = db.query(EventAttendance).filter(
            EventAttendance.event_id == catan_event.id,
            EventAttendance.status == "pending"
        ).all()

        for att in attendances:
            att.status = "approved"
            print(f"[APPROVED] User ID {att.user_id} approved for Catan event!")

        db.commit()
        print("[SUCCESS] Catan event join requests approved!")

    finally:
        db.close()

if __name__ == "__main__":
    main()
