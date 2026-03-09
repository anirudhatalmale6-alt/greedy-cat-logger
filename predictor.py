"""
Next Round Probability Predictor for Greedy Cat
Uses frequency analysis, recency, streaks, and patterns to estimate probabilities.
"""

from config import FOOD_ITEMS, FOOD_MULTIPLIER


class Predictor:
    """Estimates next round probabilities based on result history."""

    def __init__(self):
        # Base probability (equal distribution)
        self.base_prob = 1.0 / len(FOOD_ITEMS)

    def predict(self, results):
        """
        Analyze result history and return probability estimates.

        Args:
            results: list of result entries [{"result": "tomato", ...}, ...]

        Returns:
            dict of {food_name: {"probability": float, "reasons": [str]}}
            sorted by probability descending
        """
        if not results:
            # No history - return equal probabilities
            return {food: {"probability": self.base_prob * 100, "reasons": ["No data"]}
                    for food in FOOD_ITEMS}

        total = len(results)
        food_list = [e["result"] for e in results]

        # ---- Factor 1: Overall frequency (weight: 0.25) ----
        freq_scores = {}
        for food in FOOD_ITEMS:
            count = food_list.count(food)
            freq_scores[food] = count / max(total, 1)

        # ---- Factor 2: Recent frequency - last 20 rounds (weight: 0.25) ----
        recent = food_list[-20:]
        recent_scores = {}
        for food in FOOD_ITEMS:
            count = recent.count(food)
            recent_scores[food] = count / max(len(recent), 1)

        # ---- Factor 3: Recency - rounds since last seen (weight: 0.20) ----
        # Items not seen for a long time get higher score (due for appearance)
        recency_scores = {}
        for food in FOOD_ITEMS:
            ago = None
            for i, f in enumerate(reversed(food_list)):
                if f == food:
                    ago = i
                    break
            if ago is None:
                recency_scores[food] = 1.0  # Never seen - high score
            else:
                # Higher score for items not seen recently
                # Normalize: ago=0 -> 0.1, ago=50+ -> 1.0
                recency_scores[food] = min(0.1 + (ago / 50) * 0.9, 1.0)

        # ---- Factor 4: Anti-streak (weight: 0.15) ----
        # If an item has been appearing a lot recently, it's less likely to continue
        # If it hasn't appeared, it's "due"
        anti_streak_scores = {}
        last_10 = food_list[-10:]
        for food in FOOD_ITEMS:
            recent_count = last_10.count(food)
            # Inverse: high recent count = lower score
            anti_streak_scores[food] = 1.0 - (recent_count / max(len(last_10), 1))

        # ---- Factor 5: Pattern detection - pairs (weight: 0.15) ----
        # Look for what typically follows the current last result
        pattern_scores = {food: 0.0 for food in FOOD_ITEMS}
        if len(food_list) >= 2:
            last_food = food_list[-1]
            # Count transitions from last_food to each other food
            transitions = {}
            for i in range(len(food_list) - 1):
                if food_list[i] == last_food:
                    next_food = food_list[i + 1]
                    transitions[next_food] = transitions.get(next_food, 0) + 1

            total_transitions = sum(transitions.values())
            if total_transitions > 0:
                for food, count in transitions.items():
                    pattern_scores[food] = count / total_transitions

        # ---- Combine all factors ----
        weights = {
            "freq": 0.25,
            "recent": 0.25,
            "recency": 0.20,
            "anti_streak": 0.15,
            "pattern": 0.15,
        }

        combined = {}
        for food in FOOD_ITEMS:
            score = (
                weights["freq"] * freq_scores[food] +
                weights["recent"] * recent_scores[food] +
                weights["recency"] * recency_scores[food] +
                weights["anti_streak"] * anti_streak_scores[food] +
                weights["pattern"] * pattern_scores[food]
            )
            combined[food] = score

        # Normalize to percentages
        total_score = sum(combined.values())
        if total_score == 0:
            total_score = 1

        predictions = {}
        for food in FOOD_ITEMS:
            prob = (combined[food] / total_score) * 100
            reasons = self._get_reasons(food, freq_scores, recent_scores,
                                         recency_scores, anti_streak_scores,
                                         pattern_scores, food_list)
            predictions[food] = {
                "probability": round(prob, 1),
                "reasons": reasons,
            }

        # Sort by probability descending
        sorted_preds = dict(sorted(predictions.items(),
                                    key=lambda x: x[1]["probability"],
                                    reverse=True))
        return sorted_preds

    def _get_reasons(self, food, freq, recent, recency, anti_streak, pattern, food_list):
        """Generate human-readable reasons for the prediction."""
        reasons = []

        # Frequency
        total = len(food_list)
        count = food_list.count(food)
        if total > 0:
            pct = count / total * 100
            if pct > 15:
                reasons.append(f"High frequency ({pct:.0f}%)")
            elif pct < 5:
                reasons.append(f"Low frequency ({pct:.0f}%)")

        # Recency
        ago = None
        for i, f in enumerate(reversed(food_list)):
            if f == food:
                ago = i
                break
        if ago is not None:
            if ago == 0:
                reasons.append("Just appeared")
            elif ago > 30:
                reasons.append(f"Due (not seen in {ago} rounds)")
            elif ago > 15:
                reasons.append(f"Overdue ({ago} rounds ago)")
        else:
            reasons.append("Never appeared")

        # Pattern
        if pattern.get(food, 0) > 0.2:
            reasons.append("Common follow-up")

        # Streak
        last_5 = food_list[-5:]
        if food in last_5:
            streak_count = last_5.count(food)
            if streak_count >= 3:
                reasons.append(f"Hot streak (x{streak_count})")

        return reasons if reasons else ["Average likelihood"]

    def get_top_predictions(self, results, n=3):
        """Get top N predictions with details."""
        preds = self.predict(results)
        top = list(preds.items())[:n]
        return top
