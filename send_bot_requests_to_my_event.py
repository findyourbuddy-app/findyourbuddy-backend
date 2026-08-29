import sys
import os
import random
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.notification import Notification

def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "engincts@gmail.com").first()
        if not user:
            print("[ERROR] User engincts@gmail.com not found!")
            return

        print(f"[FOUND USER] {user.display_name} (ID: {user.id})")

        # Find latest events created by this user
        my_events = db.query(Event).filter(Event.creator_id == user.id).order_by(Event.id.desc()).all()
        if not my_events:
            # Fallback: check any user-created event
            my_events = db.query(Event).filter(Event.creator_id.isnot(None)).order_by(Event.id.desc()).limit(3).all()

        if not my_events:
            print("[ERROR] No events found!")
            return

        target_event = my_events[0]
        print(f"[TARGET EVENT] ID: {target_event.id}, Title: '{target_event.title}'")

        # Find bot users (excluding host user)
        bot_users = db.query(User).filter(
            User.email.like("%@buddybot.com"),
            User.id != user.id
        ).all()

        if not bot_users:
            # Fallback to any dummy users
            bot_users = db.query(User).filter(User.id != user.id).limit(6).all()

        # Select 3-4 bots to send join requests
        selected_bots = random.sample(bot_users, min(4, len(bot_users)))
        print(f"[SELECTED BOTS] {[b.display_name for b in selected_bots]}")

        created_requests = 0
        for bot in selected_bots:
            # Check existing attendance
            existing = db.query(EventAttendance).filter(
                EventAttendance.event_id == target_event.id,
                EventAttendance.user_id == bot.id
            ).first()

            if not existing:
                att = EventAttendance(
                    event_id=target_event.id,
                    user_id=bot.id,
                    status="pending"
                )
                db.add(att)
                db.flush()

                # Add Notification for event creator
                notif = Notification(
                    user_id=user.id,
                    title="Yeni Katılım İsteği! 🎉",
                    body=f"{bot.display_name}, '{target_event.title}' etkinliğine katılmak istiyor!",
                    notification_type="event_join_request",
                    event_id=target_event.id,
                    data={
                        "event_id": target_event.id,
                        "requester_id": bot.id,
                        "requester_name": bot.display_name,
                        "attendance_id": att.id,
                    }
                )
                db.add(notif)
                created_requests += 1
            else:
                existing.status = "pending"
                created_requests += 1

        db.commit()
        print(f"[SUCCESS] {created_requests} pending bot join requests & notifications created for '{target_event.title}'!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
