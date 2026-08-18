from app.models.user import User

ZODIAC_ELEMENTS = {
    "koç": "fire", "aslan": "fire", "yay": "fire",
    "boğa": "earth", "başak": "earth", "oğlak": "earth",
    "ikizler": "air", "terazi": "air", "kova": "air",
    "yengeç": "water", "akrep": "water", "balık": "water",
    "aries": "fire", "leo": "fire", "sagittarius": "fire",
    "taurus": "earth", "virgo": "earth", "capricorn": "earth",
    "gemini": "air", "libra": "air", "aquarius": "air",
    "cancer": "water", "scorpio": "water", "pisces": "water",
}


class RecommendationService:
    @staticmethod
    def calculate_jaccard_similarity(interests_a: list[str] | None, interests_b: list[str] | None) -> float:
        """Calculates Jaccard similarity coefficient between two lists of interests."""
        if not interests_a or not interests_b:
            return 0.0
            
        set_a = set(interests_a)
        set_b = set(interests_b)
        
        intersection = set_a.intersection(set_b)
        union = set_a.union(set_b)
        
        if not union:
            return 0.0
            
        return len(intersection) / len(union)

    @staticmethod
    def calculate_zodiac_compatibility(sign_a: str | None, sign_b: str | None) -> float:
        """Calculates Zodiac element synergy score between two signs using shared matching_service matrix."""
        if not sign_a or not sign_b:
            return 0.5
        from app.services.matching_service import _ZODIAC_ELEMENTS, _ELEMENT_SYNERGY
        elem1 = _ZODIAC_ELEMENTS.get(sign_a.strip())
        elem2 = _ZODIAC_ELEMENTS.get(sign_b.strip())
        if not elem1 or not elem2:
            return 0.5
        return _ELEMENT_SYNERGY.get((elem1, elem2), 0.5)

    @classmethod
    def score_candidate(cls, swiper: User, candidate: User) -> float:
        """Scores a candidate based on interests, hobbies, zodiac compatibility, and age proximity."""
        # 1. Interests & Hobbies overlap (Jaccard similarity) - Weight: 0.6
        interests_score = cls.calculate_jaccard_similarity(swiper.interests, candidate.interests)
        hobbies_score = cls.calculate_jaccard_similarity(swiper.hobbies, candidate.hobbies)
        overlap_score = (interests_score * 0.5) + (hobbies_score * 0.5) if (swiper.hobbies or candidate.hobbies) else interests_score
        
        # 2. Zodiac Sign Compatibility - Weight: 0.2
        zodiac_score = cls.calculate_zodiac_compatibility(swiper.zodiac_sign, candidate.zodiac_sign)

        # 3. Age proximity penalty/bonus - Weight: 0.2
        age_score = 0.5
        if swiper.age is not None and candidate.age is not None:
            age_diff = abs(swiper.age - candidate.age)
            if age_diff < 10:
                age_score = 1.0 - (age_diff / 10.0)
                
        # Weighted final score (0.6 * overlap + 0.2 * zodiac + 0.2 * age)
        return (0.6 * overlap_score) + (0.2 * zodiac_score) + (0.2 * age_score)
