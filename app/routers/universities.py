from typing import Any
import httpx
from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/universities", tags=["universities"])

# Curated list of Turkish Universities for fast server-side matching
TURKISH_UNIVERSITIES = [
    "İstanbul Üniversitesi",
    "İstanbul Teknik Üniversitesi (İTÜ)",
    "Boğaziçi Üniversitesi",
    "Orta Doğu Teknik Üniversitesi (ODTÜ)",
    "Hacettepe Üniversitesi",
    "Yıldız Teknik Üniversitesi (YTÜ)",
    "Ankara Üniversitesi",
    "Marmara Üniversitesi",
    "Bilkent Üniversitesi",
    "Koç Üniversitesi",
    "Sabancı Üniversitesi",
    "Ege Üniversitesi",
    "Dokuz Eylül Üniversitesi",
    "Bahçeşehir Üniversitesi (BAU)",
    "Galatasaray Üniversitesi",
    "Gazi Üniversitesi",
    "Anadolu Üniversitesi",
    "Mimar Sinan Güzel Sanatlar Üniversitesi",
    "Yeditepe Üniversitesi",
    "Özyeğin Üniversitesi",
    "TOBB Ekonomi ve Teknoloji Üniversitesi",
    "Akdeniz Üniversitesi",
    "Çukurova Üniversitesi",
    "Karadeniz Teknik Üniversitesi (KTÜ)",
    "Selçuk Üniversitesi",
    "Erciyes Üniversitesi",
    "Bursa Uludağ Üniversitesi",
    "Kocaeli Üniversitesi",
    "Sakarya Üniversitesi",
    "Pamukkale Üniversitesi",
    "Eskişehir Osmangazi Üniversitesi",
    "İzmir Yüksek Teknoloji Enstitüsü (İYTE)",
    "Gebze Teknik Üniversitesi (GTÜ)",
    "Yaşar Üniversitesi",
    "Kadir Has Üniversitesi",
    "İstanbul Bilgi Üniversitesi",
    "İstanbul Aydın Üniversitesi",
    "İstanbul Medipol Üniversitesi",
    "İstanbul Gelişim Üniversitesi",
    "Nişantaşı Üniversitesi",
    "Beykoz Üniversitesi",
    "Doğuş Üniversitesi",
    "Maltepe Üniversitesi",
    "Üsküdar Üniversitesi",
    "İstanbul Kültür Üniversitesi",
    "İstanbul Ticaret Üniversitesi",
    "MEF Üniversitesi",
    "Türk-Alman Üniversitesi",
    "Bezmialem Vakıf Üniversitesi",
    "İbn Haldun Üniversitesi",
    "İstinye Üniversitesi",
    "İstanbul Kent Üniversitesi",
    "İstanbul Sabahattin Zaim Üniversitesi",
    "TED Üniversitesi",
    "Atılım Üniversitesi",
    "Başkent Üniversitesi",
    "Çankaya Üniversitesi",
    "İzmir Ekonomi Üniversitesi",
    "Fenerbahçe Üniversitesi",
    "Antalya Bilim Üniversitesi",
    "Hasan Kalyoncu Üniversitesi",
    "KTO Karatay Üniversitesi",
]


def _normalize(text: str) -> str:
    return (
        text.lower()
        .replace("İ", "i")
        .replace("I", "ı")
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
        .strip()
    )


@router.get("/search", response_model=list[str])
async def search_universities_api(
    q: str = Query(..., min_length=2),
    _current_user: User = Depends(get_current_user),
) -> list[str]:
    query_clean = q.strip()
    norm_query = _normalize(query_clean)
    results: list[str] = []
    seen: set[str] = set()

    # 1. Local Turkish universities match
    for uni in TURKISH_UNIVERSITIES:
        norm_uni = _normalize(uni)
        if norm_query in norm_uni:
            results.append(uni)
            seen.add(norm_uni)

    # 2. Query Hipolabs public University Search API
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                "https://universities.hipolabs.com/search",
                params={"name": query_clean},
            )
            if resp.status_code == 200:
                items: list[dict[str, Any]] = resp.json()
                for item in items:
                    name = item.get("name")
                    country = item.get("country")
                    if name:
                        norm_name = _normalize(name)
                        if norm_name not in seen:
                            display_name = (
                                f"{name} ({country})"
                                if country and country != "Turkey"
                                else name
                            )
                            results.append(display_name)
                            seen.add(norm_name)
    except Exception:
        # Fallback gracefully to local matches if remote API call fails
        pass

    return results[:12]
