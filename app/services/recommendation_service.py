from app.models.user import User

class RecommendationService:
    @staticmethod
    def calculate_jaccard_similarity(interests_a: list[str], interests_b: list[str]) -> float:
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

    @classmethod
    def score_candidate(cls, swiper: User, candidate: User) -> float:
        """Scores a candidate based on interests similarity and age proximity."""
        # 1. Interests overlap (Jaccard similarity) - Weight: 0.8
        interests_score = cls.calculate_jaccard_similarity(swiper.interests, candidate.interests)
        
        # 2. Age proximity penalty/bonus - Weight: 0.2
        age_score = 0.0
        if swiper.age is not None and candidate.age is not None:
            age_diff = abs(swiper.age - candidate.age)
            # Maximum penalty at 10 years difference
            if age_diff < 10:
                age_score = 1.0 - (age_diff / 10.0)
                
        # Weighted final score
        return (0.8 * interests_score) + (0.2 * age_score)
