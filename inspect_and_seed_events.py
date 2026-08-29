import sys
import io
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.database import SessionLocal
from app.models.user import User
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.services.auth_service import hash_password

def run_seed():
    db = SessionLocal()
    try:
        print("[INFO] Checking existing attendances in database...")
        all_attendances = db.query(EventAttendance).all()
        print(f"Found {len(all_attendances)} total attendance request(s).")
        
        approved_events_info = []
        for att in all_attendances:
            if att.status == "pending":
                att.status = "approved"
            event = db.query(Event).filter(Event.id == att.event_id).first()
            user = db.query(User).filter(User.id == att.user_id).first()
            creator = db.query(User).filter(User.id == event.creator_id).first() if event and event.creator_id else None
            
            event_title = event.title if event else f"Event #{att.event_id}"
            user_name = user.display_name if user else f"User #{att.user_id}"
            creator_email = creator.email if creator else "System Scraped (No login)"
            
            approved_events_info.append({
                "attendance_id": att.id,
                "event_id": att.event_id,
                "event_title": event_title,
                "applicant_name": user_name,
                "status": att.status,
                "creator_email": creator_email
            })
        
        db.commit()

        # -------------------------------------------------------------
        # Create 3 Dummy Organizers
        # -------------------------------------------------------------
        organizer_credentials = []
        dummy_users_data = [
            {"email": "organizer_selin@example.com", "name": "Selin Yılmaz", "gender": "female", "phone": "+905550000001"},
            {"email": "organizer_can@example.com", "name": "Can Demir", "gender": "male", "phone": "+905550000002"},
            {"email": "organizer_elaceren@example.com", "name": "Ela Ceren", "gender": "female", "phone": "+905550000003"},
        ]
        
        organizers = []
        for udata in dummy_users_data:
            user = db.query(User).filter(User.email == udata["email"]).first()
            if not user:
                user = User(
                    email=udata["email"],
                    hashed_password=hash_password("Password123!"),
                    display_name=udata["name"],
                    gender=udata["gender"],
                    is_active=True,
                    referral_code=f"REF{uuid.uuid4().hex[:6].upper()}",
                    phone_number=udata["phone"],
                    phone_verified=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            organizers.append(user)
            organizer_credentials.append({
                "name": udata["name"],
                "email": udata["email"],
                "password": "Password123!"
            })

        # -------------------------------------------------------------
        # Create 4 Group Events (Grup Etkinlikleri)
        # -------------------------------------------------------------
        now = datetime.now(timezone.utc)
        group_events_data = [
            {
                "title": "Kadıköy Masa Oyunları & Catan Gecesi",
                "description": "Kadıköy Moda'da sıcak kahve eşliğinde Catan, Dixit ve Tabu oynuyoruz! Oyun kurallarını bilmiyorsan sorun değil, orada anlatıyoruz. Herkes davetlidir!",
                "category": "social",
                "location_name": "Moda Kahvesi, Kadıköy, İstanbul",
                "latitude": 40.9850,
                "longitude": 29.0260,
                "starts_at": now + timedelta(days=2, hours=4),
                "creator_id": organizers[0].id,
                "is_group_event": True,
                "max_attendees": 10,
                "is_paid": False,
                "image_url": "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?auto=format&fit=crop&w=800&q=80"
            },
            {
                "title": "Karaköy Kahve & Yazılım Sohbeti",
                "description": "Karaköy'de kahve eşliğinde yazılım, mobil tasarım, yapay zekâ ve yeni teknoloji trendleri üzerine sohbet ediyoruz. Bilgisayarını kap gel!",
                "category": "tech",
                "location_name": "Espresso Lab Karaköy, İstanbul",
                "latitude": 41.0240,
                "longitude": 28.9750,
                "starts_at": now + timedelta(days=3, hours=2),
                "creator_id": organizers[1].id,
                "is_group_event": True,
                "max_attendees": 8,
                "is_paid": False,
                "image_url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=800&q=80"
            },
            {
                "title": "Belgrad Ormanı Hafta Sonu Doğa Yürüyüşü & Piknik",
                "description": "Temiz havada 7 KM tempolu yürüyüş sonrası orman içinde keyifli bir piknik yapıyoruz. Yürüyüş ayakkabılarını ve termosunu unutma!",
                "category": "outdoor",
                "location_name": "Belgrad Ormanı Neşet Suyu Yürüyüş Yolu, İstanbul",
                "latitude": 41.1820,
                "longitude": 28.9880,
                "starts_at": now + timedelta(days=5, hours=1),
                "creator_id": organizers[2].id,
                "is_group_event": True,
                "max_attendees": 15,
                "is_paid": False,
                "image_url": "https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=800&q=80"
            },
            {
                "title": "Yenikapı Sahil Paten & Bisiklet Turu",
                "description": "Yenikapı sahil yolunda akşam serinliğinde paten sürüşü ve bisiklet turu yapıyoruz. Yeni başlayanlar ve profesyoneller katılabilir!",
                "category": "sports",
                "location_name": "Yenikapı Sahil Parkı, İstanbul",
                "latitude": 41.0020,
                "longitude": 28.9560,
                "starts_at": now + timedelta(days=4, hours=3),
                "creator_id": organizers[0].id,
                "is_group_event": True,
                "max_attendees": 12,
                "is_paid": False,
                "image_url": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=800&q=80"
            }
        ]

        created_events = []
        for edata in group_events_data:
            existing = db.query(Event).filter(Event.title == edata["title"]).first()
            if not existing:
                event = Event(**edata)
                db.add(event)
                db.commit()
                db.refresh(event)
                created_events.append(event)
            else:
                created_events.append(existing)

        print("\n[SUCCESS] SEEDING COMPLETE!")
        print("--------------------------------------------------")
        print(f"Attendance Records Processed: {len(approved_events_info)}")
        for ainfo in approved_events_info[-5:]:
            print(f"  * Event #{ainfo['event_id']}: '{ainfo['event_title']}' -> Applicant '{ainfo['applicant_name']}' (Status: {ainfo['status']})")
            print(f"    Organizer Email: {ainfo['creator_email']}")
            
        print("\n[DUMMY ORGANIZER ACCOUNTS FOR LOGGING IN AND TESTING APPROVALS]:")
        for cred in organizer_credentials:
            print(f"  - Name: {cred['name']} | Email: {cred['email']} | Password: {cred['password']}")
            
        print("\n[NEW DUMMY GROUP EVENTS CREATED]:")
        for ev in created_events:
            print(f"  - [ID: {ev.id}] {ev.title} (Category: {ev.category}, Creator ID: {ev.creator_id})")
        print("--------------------------------------------------")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Error during seeding: {exc}")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
