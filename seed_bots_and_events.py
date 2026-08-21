import random
import uuid
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.core.security import get_password_hash

BOT_USERS_DATA = [
    {
        "display_name": "Zeynep Yılmaz",
        "email": "zeynep.yilmaz@buddybot.com",
        "gender": "female",
        "age": 24,
        "occupation": "Yazılım Mühendisi",
        "university": "İTÜ",
        "zodiac_sign": "Boğa",
        "bio": "Kadıköy'de kahve & kodlama seansları yapmayı çok seviyorum. Hafta sonları doğa yürüyüşü ve akustik konser takibindeyim! ☕🎶",
        "interests": ["coffee", "running", "concert", "workshop"],
        "hobbies": ["Yazılım", "Kahve", "Pilates", "Fotoğrafçılık"],
        "photo_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=500&auto=format&fit=crop&q=80",
        "trust_score": 4,
        "is_verified": True,
        "latitude": 41.0082,
        "longitude": 28.9784,
    },
    {
        "display_name": "Caner Kaya",
        "email": "caner.kaya@buddybot.com",
        "gender": "male",
        "age": 27,
        "occupation": "Ürün Tasarımcısı (UI/UX)",
        "university": "Mimar Sinan",
        "zodiac_sign": "İkizler",
        "bio": "Masa oyunları ve açık hava koşuları vazgeçilmezim. Kadıköy veya Beşiktaş'ta grup etkinliklerine açığım! 🏃‍♂️🎲",
        "interests": ["boardgames", "running", "coffee", "art"],
        "hobbies": ["Tasarım", "Koşu", "Catan", "Kahve Demleme"],
        "photo_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&auto=format&fit=crop&q=80",
        "trust_score": 3,
        "is_verified": True,
        "latitude": 41.0422,
        "longitude": 29.0083,
    },
    {
        "display_name": "Elif Şahin",
        "email": "elif.sahin@buddybot.com",
        "gender": "female",
        "age": 23,
        "occupation": "Mimarlık Öğrencisi",
        "university": "Yıldız Teknik",
        "zodiac_sign": "Başak",
        "bio": "Sanat galerilerini gezmeyi ve tarihi yarımadada yürüyüş yapmayı severim. Yeni sergiler keşfedecek buddy arıyorum 🎨✨",
        "interests": ["art", "theatre", "coffee", "hiking"],
        "hobbies": ["Çizim", "Müzeler", "Kitap", "Yoga"],
        "photo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=500&auto=format&fit=crop&q=80",
        "trust_score": 5,
        "is_verified": True,
        "latitude": 41.0150,
        "longitude": 28.9800,
    },
    {
        "display_name": "Mert Demir",
        "email": "mert.demir@buddybot.com",
        "gender": "male",
        "age": 26,
        "occupation": "Finans Analisti",
        "university": "Boğaziçi Üniversitesi",
        "zodiac_sign": "Aslan",
        "bio": "Halı saha maçları, tenis ve akşam bisiklet sürüşleri! Takımına eksik adam arıyorsan yazabilirsin ⚽🎾",
        "interests": ["football", "cycling", "running", "festival"],
        "hobbies": ["Futbol", "Tenis", "Bisiklet", "Borsa"],
        "photo_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=500&auto=format&fit=crop&q=80",
        "trust_score": 2,
        "is_verified": True,
        "latitude": 41.0825,
        "longitude": 29.0431,
    },
    {
        "display_name": "Selin Aydın",
        "email": "selin.aydin@buddybot.com",
        "gender": "female",
        "age": 25,
        "occupation": "Dijital Pazarlama Uzmanı",
        "university": "Marmara Üniversitesi",
        "zodiac_sign": "Akrep",
        "bio": "Yoga seansları, vegan kafe keşifleri ve bağımsız film gösterimleri! Kadıköy çevresindeyim 🧘‍♀️🌱 Cinema buddies welcome!",
        "interests": ["yoga", "coffee", "theatre", "hobby"],
        "hobbies": ["Yoga", "Pilates", "Sinema", "Aromaterapi"],
        "photo_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=500&auto=format&fit=crop&q=80",
        "trust_score": 4,
        "is_verified": True,
        "latitude": 40.9901,
        "longitude": 29.0291,
    },
    {
        "display_name": "Burak Özkan",
        "email": "burak.ozkan@buddybot.com",
        "gender": "male",
        "age": 28,
        "occupation": "Fizyoterapist",
        "university": "Hacettepe",
        "zodiac_sign": "Yay",
        "bio": "Kaya tırmanışı, kamp ve bouldering tutkunuyum. Hafta sonu outdoor aktiviteleri düzenliyorum 🧗‍♂️🏕️",
        "interests": ["climbing", "hiking", "running", "festival"],
        "hobbies": ["Tırmanış", "Kamp", "Hiking", "Doğa"],
        "photo_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=500&auto=format&fit=crop&q=80",
        "trust_score": 5,
        "is_verified": True,
        "latitude": 41.0600,
        "longitude": 29.0100,
    },
    {
        "display_name": "Deniz Çelik",
        "email": "deniz.celik@buddybot.com",
        "gender": "female",
        "age": 22,
        "occupation": "Psikoloji Öğrencisi",
        "university": "Bilgi Üniversitesi",
        "zodiac_sign": "Balık",
        "bio": "Kahve falı & derin sohbetler ☕ Kitap kulübümüze yeni üyeler arıyoruz!",
        "interests": ["coffee", "hobby", "theatre", "art"],
        "hobbies": ["Kitap Kulübü", "Psikoloji", "Yazarlık", "Kahve"],
        "photo_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=500&auto=format&fit=crop&q=80",
        "trust_score": 3,
        "is_verified": False,
        "latitude": 41.0500,
        "longitude": 28.9400,
    },
    {
        "display_name": "Kaan Arslan",
        "email": "kaan.arslan@buddybot.com",
        "gender": "male",
        "age": 29,
        "occupation": "Avukat",
        "university": "İstanbul Üniversitesi",
        "zodiac_sign": "Oğlak",
        "bio": "İş çıkışı Moda sahilinde yürüyüş veya caz konserleri. Kaliteli sohbet önceliğimdir 🎷",
        "interests": ["concert", "coffee", "running", "art"],
        "hobbies": ["Caz Dinlemek", "Yürüyüş", "Şarap Tadımı", "Tarih"],
        "photo_url": "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=500&auto=format&fit=crop&q=80",
        "trust_score": 4,
        "is_verified": True,
        "latitude": 40.9850,
        "longitude": 29.0200,
    },
]

EVENTS_DATA = [
    {
        "title": "Kadıköy Moda Sahil Akşam Koşusu 🏃‍♂️✨",
        "description": "Moda burnundan Fenerbahçe parkına tatlı bir akşam koşusu ve sonrasında dondurma sohbeti! Tempo 5:30 min/km civarı. Her seviyeden koşucu davetlidir.",
        "category": "running",
        "location_name": "Moda İskelesi, Kadıköy",
        "latitude": 40.9825,
        "longitude": 29.0245,
        "is_group_event": True,
        "max_attendees": 12,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Yazılım & Tasarım Kahve Sohbeti ☕💻",
        "description": "Kadıköy'ün nezih bir kafesinde toplanıp yan projelerimizden, UI/UX trendlerinden ve kodlamadan konuşuyoruz. İlk kahveler benden!",
        "category": "coffee",
        "location_name": "Walter's Coffee Roastery, Kadıköy",
        "latitude": 40.9880,
        "longitude": 29.0270,
        "is_group_event": True,
        "max_attendees": 8,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Karaköy Sanat Galerileri Tour & Kahve 🎨",
        "description": "Karaköy ve Tophane bölgesindeki güncel çağdaş sanat sergilerini gezip fikir alışverişi yapacağız. Sanatsever buddyleri bekliyoruz!",
        "category": "art",
        "location_name": "Karaköy Fransız Geçidi, İstanbul",
        "latitude": 41.0235,
        "longitude": 28.9772,
        "is_group_event": True,
        "max_attendees": 10,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Catan & Boardgame Gecesi 🎲♟️",
        "description": "Masa oyunları tutkunları buluşuyor! Catan, Splendor ve Carcassonne oynayacağız. Kural bilmeyenlere öğretiyoruz, eğlence garantili.",
        "category": "boardgames",
        "location_name": "Goblin Oyun Kulübü, Kadıköy",
        "latitude": 40.9912,
        "longitude": 29.0251,
        "is_group_event": True,
        "max_attendees": 6,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Zorlu PSM Akustik Konser Eşlikçisi Arıyorum 🎶 Ticket Duo",
        "description": "Bu Cuma akşamı akustik caz konserine gitmek için yanıma 1 buddy arıyorum! Biletim hazır, keyifli müzik seven birisi yazabilir.",
        "category": "concert",
        "location_name": "Zorlu PSM, Beşiktaş",
        "latitude": 41.0664,
        "longitude": 29.0175,
        "is_group_event": False,
        "max_attendees": 2,
        "is_paid": True,
        "ticket_price": 250.0,
        "image_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Beşiktaş 7v7 Gece Halı Saha Maçı ⚽",
        "description": "Kadromuza dosthane ve dinamik 2 oyuncu arıyoruz. Maç sonrası içecekler ve muhabbet bizden!",
        "category": "football",
        "location_name": "Beşiktaş Spor Tesisleri, Fulya",
        "latitude": 41.0540,
        "longitude": 29.0010,
        "is_group_event": True,
        "max_attendees": 14,
        "is_paid": True,
        "ticket_price": 80.0,
        "image_url": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Maçka Parkı Gün Gün Batan Yoga Seansı 🧘‍♀️",
        "description": "Gün matını al gel! Şehrin stresinden uzaklaşıp nefes egzersizi ve başlangıç seviye vinyasa yapıyoruz.",
        "category": "yoga",
        "location_name": "Maçka Demokrasi Parkı, Nişantaşı",
        "latitude": 41.0430,
        "longitude": 28.9950,
        "is_group_event": True,
        "max_attendees": 15,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1545205597-3d9d02c29597?w=800&auto=format&fit=crop&q=80",
    },
    {
        "title": "Yeniköy - Sarıyer Sahil Bisiklet Turu 🚴‍♂️",
        "description": "Boğaz havasında tatlı ve sohbetli bir bisiklet sürüşü. Tur bitiminde Sarıyer'de börek & çay molası var!",
        "category": "cycling",
        "location_name": "Yeniköy İskelesi, Sarıyer",
        "latitude": 41.1200,
        "longitude": 29.0700,
        "is_group_event": True,
        "max_attendees": 10,
        "is_paid": False,
        "image_url": "https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=800&auto=format&fit=crop&q=80",
    },
]

def seed_database():
    db = SessionLocal()
    try:
        print("🌱 Seeding realistic bot users and user-created events...")
        password_hash = get_password_hash("Password123!")

        created_bots = []
        for bdata in BOT_USERS_DATA:
            existing = db.query(User).filter(User.email == bdata["email"]).first()
            if not existing:
                phone_num = f"+90555{random.randint(1000000, 9999999)}"
                referral = f"BOT{uuid.uuid4().hex[:6].upper()}"
                user = User(
                    email=bdata["email"],
                    hashed_password=password_hash,
                    display_name=bdata["display_name"],
                    gender=bdata["gender"],
                    age=bdata["age"],
                    occupation=bdata["occupation"],
                    university=bdata["university"],
                    zodiac_sign=bdata["zodiac_sign"],
                    bio=bdata["bio"],
                    interests=bdata["interests"],
                    hobbies=bdata["hobbies"],
                    photo_url=bdata["photo_url"],
                    trust_score=bdata["trust_score"],
                    is_verified=bdata["is_verified"],
                    latitude=bdata["latitude"],
                    longitude=bdata["longitude"],
                    phone_number=phone_num,
                    phone_verified=True,
                    referral_code=referral,
                )
                db.add(user)
                db.flush()
                # Add default photo in photos table
                photo = UserPhoto(user_id=user.id, photo_url=bdata["photo_url"], position=0)
                db.add(photo)
                created_bots.append(user)
            else:
                created_bots.append(existing)

        db.commit()
        print(f"✅ {len(created_bots)} bot users ready!")

        # Create Events created by these bot users
        created_events = []
        now = datetime.utcnow()
        for idx, edata in enumerate(EVENTS_DATA):
            # Pick a creator bot
            creator = created_bots[idx % len(created_bots)]
            # Event starts between tomorrow and 5 days later
            starts_at = now + timedelta(days=random.randint(1, 5), hours=random.randint(1, 8))

            existing_event = db.query(Event).filter(Event.title == edata["title"]).first()
            if not existing_event:
                event = Event(
                    title=edata["title"],
                    description=edata["description"],
                    category=edata["category"],
                    location_name=edata["location_name"],
                    latitude=edata["latitude"],
                    longitude=edata["longitude"],
                    starts_at=starts_at,
                    creator_id=creator.id,
                    is_group_event=edata["is_group_event"],
                    max_attendees=edata["max_attendees"],
                    is_paid=edata["is_paid"],
                    ticket_price=edata.get("ticket_price"),
                    image_url=edata["image_url"],
                    is_approved=True,
                )
                db.add(event)
                db.flush()
                created_events.append(event)
            else:
                created_events.append(existing_event)

        db.commit()
        print(f"✅ {len(created_events)} user-created events created!")

        # Add event attendances so events have active participants
        attendance_count = 0
        for ev in created_events:
            # Add the creator as approved attendee
            if ev.creator_id:
                att_existing = db.query(EventAttendance).filter(
                    EventAttendance.event_id == ev.id,
                    EventAttendance.user_id == ev.creator_id
                ).first()
                if not att_existing:
                    db.add(EventAttendance(event_id=ev.id, user_id=ev.creator_id, status="approved"))
                    attendance_count += 1

            # Add 2-4 random bot users as attendees for group events
            if ev.is_group_event:
                other_bots = [b for b in created_bots if b.id != ev.creator_id]
                sample_attendees = random.sample(other_bots, min(3, len(other_bots)))
                for bot in sample_attendees:
                    att_existing = db.query(EventAttendance).filter(
                        EventAttendance.event_id == ev.id,
                        EventAttendance.user_id == bot.id
                    ).first()
                    if not att_existing:
                        db.add(EventAttendance(event_id=ev.id, user_id=bot.id, status="approved"))
                        attendance_count += 1

        db.commit()
        print(f"🎉 {attendance_count} event attendances registered! Seed completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
