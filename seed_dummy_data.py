import sys
import os
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.user import User
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.notification import Notification
from app.models.message import Message
from app.models.match import Match

def seed():
    db = SessionLocal()
    try:
        print("🌱 Seeding dummy users, group event join requests, and notifications...")

        # 1. Create or get dummy users
        dummy_users_data = [
            {
                "email": "ahmet.yilmaz.dummy@example.com",
                "display_name": "Ahmet Yılmaz",
                "bio": "Kahve sever, doğa yürüyüşçüsü ve masa oyunları tutkunu ☕🏕️",
                "age": 26,
                "gender": "Erkek",
                "hobbies": ["Masa Oyunları", "Doğa Yürüyüşü", "Kahve Tadımı"],
                "photo_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=600&auto=format&fit=crop",
                "is_verified": True,
                "trust_score": 85,
            },
            {
                "email": "zeynep.kaya.dummy@example.com",
                "display_name": "Zeynep Kaya",
                "bio": "Konser hastası 🎸 Canlı müzik ve tiyatro kaçırmam!",
                "age": 24,
                "gender": "Kadın",
                "hobbies": ["Canlı Müzik", "Tiyatro", "Sinema"],
                "photo_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=600&auto=format&fit=crop",
                "is_verified": True,
                "trust_score": 90,
            },
            {
                "email": "burak.demir.dummy@example.com",
                "display_name": "Burak Demir",
                "bio": "Yazılımcı 💻 Kodlama sonrası halı saha maçı ve kamping!",
                "age": 28,
                "gender": "Erkek",
                "hobbies": ["Futbol", "Kamp", "Yazılım"],
                "photo_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&auto=format&fit=crop",
                "is_verified": True,
                "trust_score": 80,
            },
            {
                "email": "elif.sahin.dummy@example.com",
                "display_name": "Elif Şahin",
                "bio": "Fotoğrafçılık ve bisiklet sürüşü 🚴‍♀️ Yeni yerler keşfetmeyi severim.",
                "age": 25,
                "gender": "Kadın",
                "hobbies": ["Bisiklet", "Fotoğrafçılık", "Seyahat"],
                "photo_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=600&auto=format&fit=crop",
                "is_verified": True,
                "trust_score": 95,
            },
        ]

        seeded_dummies = []
        for idx, d in enumerate(dummy_users_data, 1):
            user = db.query(User).filter(User.email == d["email"]).first()
            if not user:
                import secrets
                user = User(
                    email=d["email"],
                    hashed_password="dummy_password_hash_123",
                    referral_code=f"DUMMY_{secrets.token_hex(3)}",
                    phone_number=f"+90555{secrets.token_hex(3)}",
                    display_name=d["display_name"],
                    bio=d["bio"],
                    age=d["age"],
                    gender=d["gender"],
                    hobbies=d["hobbies"],
                    photo_url=d["photo_url"],
                    is_verified=d["is_verified"],
                    trust_score=d["trust_score"],
                    is_active=True,
                )
                db.add(user)
                db.flush()
                print(f"  + Created dummy user: {user.display_name} (ID: {user.id})")
            else:
                print(f"  ✓ Dummy user existing: {user.display_name} (ID: {user.id})")
            seeded_dummies.append(user)

        # 2. Target engincts@gmail.com specifically
        dummy_emails = [d["email"] for d in dummy_users_data]
        target_user = db.query(User).filter(User.email == "engincts@gmail.com").first()
        if not target_user:
            target_user = db.query(User).filter(User.email.ilike("%engincts%")).first()
        
        if target_user:
            hosts = [target_user]
        else:
            hosts = db.query(User).filter(User.email.notin_(dummy_emails)).limit(3).all()

        for host in hosts:
            print(f"🎯 Seeding data for host user: {host.display_name} ({host.email}, ID: {host.id})")

            # 3. Create sample group event if user doesn't have one
            user_group_event = db.query(Event).filter(
                Event.creator_id == host.id,
                Event.is_group_event == True
            ).first()

            if not user_group_event:
                user_group_event = Event(
                    creator_id=host.id,
                    title="Hafta Sonu Kahve & Masa Oyunları ☕🎲",
                    description="Kadıköy Moda'da harika bir cafe ortamında masa oyunları oynayıp sohbet edeceğiz. Katılmak isteyen herkesi bekleriz!",
                    category="Masa Oyunları",
                    location_name="Kadıköy, İstanbul",
                    latitude=40.9901,
                    longitude=29.0291,
                    is_group_event=True,
                    max_attendees=6,
                    starts_at=datetime.now(timezone.utc) + timedelta(days=2),
                )
                db.add(user_group_event)
                db.flush()
                print(f"  + Created sample group event: '{user_group_event.title}' (ID: {user_group_event.id})")

            # 4. Create pending applications & approved attendances
            # Dummy 0 and 1 -> Pending application (onay bekleyen istek)
            # Dummy 2 and 3 -> Approved (grup sohbetine dahil olmuş)
            attendee_configs = [
                (seeded_dummies[0], "pending"),
                (seeded_dummies[1], "pending"),
                (seeded_dummies[2], "approved"),
                (seeded_dummies[3], "approved"),
            ]

            for dummy_user, status in attendee_configs:
                att = db.query(EventAttendance).filter(
                    EventAttendance.event_id == user_group_event.id,
                    EventAttendance.user_id == dummy_user.id
                ).first()

                if not att:
                    att = EventAttendance(
                        event_id=user_group_event.id,
                        user_id=dummy_user.id,
                        status=status,
                    )
                    db.add(att)
                    print(f"  + Created attendance: {dummy_user.display_name} -> {status}")
                else:
                    att.status = status
                    print(f"  ✓ Updated attendance: {dummy_user.display_name} -> {status}")

                # 5. Create notifications for the host user
                if status == "pending":
                    title = "Yeni Etkinlik Katılım İsteği! 📩"
                    body = f"{dummy_user.display_name}, '{user_group_event.title}' grup etkinliğine katılmak istiyor."
                    notif = db.query(Notification).filter(
                        Notification.user_id == host.id,
                        Notification.event_id == user_group_event.id,
                        Notification.body.contains(dummy_user.display_name)
                    ).first()

                    if not notif:
                        notif = Notification(
                            user_id=host.id,
                            title=title,
                            body=body,
                            event_id=user_group_event.id,
                            is_read=False,
                        )
                        db.add(notif)
                        print(f"  🔔 Sent notification to {host.display_name}: {dummy_user.display_name} wants to join")

            # 6. Seed dummy chat messages via Match for approved attendees
            for dummy_user in [seeded_dummies[2], seeded_dummies[3]]:
                u_a, u_b = (host.id, dummy_user.id) if host.id < dummy_user.id else (dummy_user.id, host.id)
                match = db.query(Match).filter(
                    Match.event_id == user_group_event.id,
                    Match.user_a_id == u_a,
                    Match.user_b_id == u_b
                ).first()

                if not match:
                    match = Match(
                        event_id=user_group_event.id,
                        user_a_id=u_a,
                        user_b_id=u_b,
                        score=1.0,
                        is_active=True
                    )
                    db.add(match)
                    db.flush()
                    print(f"  + Created Match between {host.display_name} and {dummy_user.display_name}")

                msg_text = f"Selam! Ben {dummy_user.display_name}, '{user_group_event.title}' etkinliğine katıldığım için çok heyecanlıyım! 🎉"
                existing_msg = db.query(Message).filter(
                    Message.match_id == match.id,
                    Message.sender_id == dummy_user.id
                ).first()

                if not existing_msg:
                    new_msg = Message(
                        match_id=match.id,
                        sender_id=dummy_user.id,
                        content=msg_text,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=10)
                    )
                    db.add(new_msg)
                    print(f"  💬 Seeded chat message from {dummy_user.display_name}: '{msg_text}'")

        db.commit()
        print("✅ Dummy seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding dummy data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
