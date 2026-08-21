"""One-off dev helper: populates the database with bot users and events so
the app has something to look at during manual testing -- a mix of regular
users, a group event with real approved members, and a batch of individual
user-created events (also joined by other bots) to exercise the
"Kullanıcı Etkinlikleri" filter, swipe candidates, and matching.

Usage: uv run python scripts/seed_demo_data.py
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.event_attendance import EventAttendance
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.user import UserCreate
from app.services.auth_service import EmailAlreadyRegisteredError, register_user
from app.services.event_service import create_event, join_event

RUN_TAG = datetime.utcnow().strftime("%m%d%H%M")

BOT_NAMES = [
    "Elif Yılmaz", "Mert Kaya", "Zeynep Demir", "Can Şahin", "Ayşe Çelik",
    "Burak Arslan", "Deniz Aydın", "Selin Koç", "Emre Doğan", "Buse Yıldız",
    "Kerem Öztürk", "Naz Aksoy", "Onur Kurt", "İpek Güneş", "Baran Polat",
    "Ece Yalçın", "Doruk Türk", "Melis Aydemir", "Arda Bozkurt", "Sude Erdoğan",
]
UNIVERSITIES = ["Boğaziçi Üniversitesi", "İTÜ", "ODTÜ", "Koç Üniversitesi", "Bilkent Üniversitesi", None]
BIOS = [
    "Hafta sonları doğa yürüyüşü ve kahve keyfi seviyorum.",
    "Canlı müzik ve yeni insanlarla tanışmaya bayılırım.",
    "Kitap kurdu, sessiz kafe köşelerinin fanıyım.",
    "Spor salonu ve akşam yürüyüşleri rutinimin parçası.",
    None,
]

ISTANBUL_SPOTS = [
    ("Bebek Sahili", 41.0766, 29.0430),
    ("Moda Sahili", 40.9847, 29.0287),
    ("Maçka Parkı", 41.0447, 28.9938),
    ("Kadıköy Meydan", 40.9902, 29.0275),
    ("Beşiktaş Meydan", 41.0430, 29.0075),
    ("Karaköy", 41.0256, 28.9744),
]

USER_EVENT_TEMPLATES = [
    ("Sabah Koşusu Kankası", "sports", "Bebek Sahili boyunca hafif tempolu bir sabah koşusu yapacağız, herkes davetli."),
    ("Kahve & Sohbet Buluşması", "coffee", "Yeni insanlarla tanışıp güzel bir kahve sohbeti yapmak isteyenler için."),
    ("Akşam Yürüyüşü Etkinliği", "hobby", "Moda sahilinde günbatımı yürüyüşü, kamera getirebilirsiniz."),
    ("Board Game Gecesi", "boardgames", "Kutu oyunları severler bir araya geliyor, yeni oyunlar öğreneceğiz."),
    ("Akustik Müzik Dinletisi", "concert", "Küçük bir kafede akustik müzik dinletisi, sakin bir akşam için ideal."),
    ("Fotoğrafçılık Yürüyüşü", "hobby", "Şehrin en fotojenik köşelerinde birlikte fotoğraf çekeceğiz."),
    ("Yoga & Nefes Egzersizi", "yoga", "Parkta açık havada yoga seansı, mat getirmeyi unutmayın."),
    ("Bisiklet Turu", "cycling", "Sahil boyunca keyifli bir bisiklet turu düzenliyoruz."),
]

GROUP_EVENT = (
    "Hafta Sonu Piknik ve Tanışma Grubu",
    "hobby",
    "Yeni kankalar edinmek isteyenler için hafta sonu piknik buluşması, herkes yiyecek bir şeyler getiriyor.",
)


def make_bot(db, index: int, name: str) -> User | None:
    email = f"bot.{RUN_TAG}.{index}@findyourbuddy.demo"
    phone = f"+9055{RUN_TAG}{index:03d}"
    try:
        user = register_user(
            db,
            UserCreate(
                email=email,
                password="demo-pass-123",
                display_name=name,
                accepted_terms=True,
                phone_number=phone,
            ),
        )
    except EmailAlreadyRegisteredError:
        return db.query(User).filter(User.email == email).first()

    user.age = random.randint(21, 32)
    user.gender = random.choice(["Kadın", "Erkek"])
    user.university = random.choice(UNIVERSITIES)
    user.bio = random.choice(BIOS)
    user.hobbies = random.sample(["kahve", "muzik", "spor", "sinema", "kitap", "yolculuk"], k=2)
    user.latitude = 41.0082 + random.uniform(-0.05, 0.05)
    user.longitude = 28.9784 + random.uniform(-0.05, 0.05)
    db.commit()
    return user


def approve_join(db, event_id: int, user_id: int) -> None:
    attendance = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    if attendance is not None:
        attendance.status = "approved"
        db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        print(f"Creating {len(BOT_NAMES)} bot users...")
        bots = [b for i, name in enumerate(BOT_NAMES) if (b := make_bot(db, i, name)) is not None]
        print(f"  -> {len(bots)} bot users ready.")

        # --- Group event: one creator, several approved members ---
        title, category, description = GROUP_EVENT
        spot_name, lat, lng = random.choice(ISTANBUL_SPOTS)
        group_creator = bots[0]
        print(f"Creating group event '{title}' by {group_creator.display_name}...")
        group_event = create_event(
            db,
            EventCreate(
                title=title,
                description=description,
                category=category,
                location_name=spot_name,
                latitude=lat,
                longitude=lng,
                starts_at=datetime.utcnow() + timedelta(days=random.randint(2, 10)),
                is_group_event=True,
                max_attendees=10,
            ),
            creator_id=group_creator.id,
            is_premium=True,
        )
        joiners = bots[1:6]
        for joiner in joiners:
            join_event(db, group_event.id, joiner.id)
            approve_join(db, group_event.id, joiner.id)
        print(f"  -> approved: {[j.display_name for j in joiners]}")

        # --- Individual user-created events, each with a couple of joiners ---
        remaining = bots[6:]
        print(f"Creating {len(USER_EVENT_TEMPLATES)} individual user events...")
        for i, (ev_title, ev_category, ev_description) in enumerate(USER_EVENT_TEMPLATES):
            creator = remaining[i % len(remaining)]
            spot_name, lat, lng = random.choice(ISTANBUL_SPOTS)
            event = create_event(
                db,
                EventCreate(
                    title=ev_title,
                    description=ev_description,
                    category=ev_category,
                    location_name=spot_name,
                    latitude=lat,
                    longitude=lng,
                    starts_at=datetime.utcnow() + timedelta(days=random.randint(1, 14), hours=random.randint(0, 12)),
                    is_group_event=False,
                ),
                creator_id=creator.id,
                is_premium=False,
            )
            attendee_pool = [b for b in remaining if b.id != creator.id]
            attendees = random.sample(attendee_pool, k=min(3, len(attendee_pool)))
            for attendee in attendees:
                join_event(db, event.id, attendee.id)
            approved = "approved" if event.is_approved else f"REJECTED: {event.approval_rejection_reason}"
            print(f"  -> '{ev_title}' by {creator.display_name} [{event.category}] ({approved}), {len(attendees)} joined")

        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
