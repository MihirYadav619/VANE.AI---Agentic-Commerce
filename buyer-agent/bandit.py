"""
Phase 6 - Contextual Bandit (LinUCB) for product-selection refinement.

When the LLM's reasoning (Phase 3) identifies multiple candidates as
genuinely relevant matches (not just picking one arbitrarily), this bandit
learns — over many purchase attempts — which candidates tend to lead to
successful, bounded purchases (the reward signal), and uses that learned
preference to break ties more intelligently than a fixed rule would.

This does NOT override the LLM's hard/soft-constraint judgment (Phase 3
still rejects genuinely bad matches) — it only refines selection AMONG
candidates the LLM has already judged to be valid options.

IMPORTANT SAFETY MECHANISM (added after testing exposed a real issue):
At cold-start (theta=0, no learned data), LinUCB's selection formula
reduces to picking the candidate with the largest feature-vector
magnitude — a deterministic exploration artifact, NOT a reward-informed
decision. Testing showed this caused the bandit to "change" the LLM's
pick nearly every time, even with zero real purchase history, which
would be misleading in front of judges (it looks like learning when it's
really just cold-start math). has_sufficient_data() gates the bandit so
it only overrides the LLM's pick once a category has accumulated enough
genuine observations to have a real, reward-informed preference.
"""

import json
import numpy as np
from pathlib import Path

BANDIT_STATE_PATH = Path(__file__).parent.parent / "backend" / "data" / "bandit_state.json"

# Features used to describe each candidate in a numeric "context vector" —
# this is what makes it a CONTEXTUAL bandit (decisions depend on product
# attributes), not just a plain multi-armed bandit.
FEATURE_NAMES = ["price_normalized", "rating_normalized", "stock_normalized"]
N_FEATURES = len(FEATURE_NAMES)

# Exploration parameter: higher = more willing to try less-proven options.
# Tuned up from 1.0 after testing showed premature-commitment risk at
# lower values (see README Phase 6 notes).
ALPHA = 2.0

# Minimum number of real purchase-outcomes a category must accumulate
# before the bandit is allowed to override the LLM's pick. Below this,
# the bandit still silently observes (via update()) but never changes
# the final decision — see the safety-mechanism note above.
MIN_OBSERVATIONS_TO_OVERRIDE = 5


class LinUCBBandit:
    """
    Standard LinUCB (Linear Upper Confidence Bound) implementation.

    Each product category gets its OWN bandit "arm-set" — a bandit that
    has learned about Shirts shouldn't apply that learning to Watches.

    State (the learned A matrices, b vectors, and observation counts per
    category) is persisted to disk so learning accumulates across runs
    instead of resetting every time the script restarts.
    """

    def __init__(self):
        self.categories = {}  # category_name -> {"A": ..., "b": ..., "n_observations": ...}
        self._load_state()

    def _load_state(self):
        if BANDIT_STATE_PATH.exists():
            with open(BANDIT_STATE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for category, data in raw.items():
                self.categories[category] = {
                    "A": np.array(data["A"]),
                    "b": np.array(data["b"]),
                    "n_observations": data.get("n_observations", 0),
                }

    def _save_state(self):
        BANDIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            category: {
                "A": data["A"].tolist(),
                "b": data["b"].tolist(),
                "n_observations": data["n_observations"],
            }
            for category, data in self.categories.items()
        }
        with open(BANDIT_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    def _get_category_state(self, category):
        """
        Lazily initializes a fresh bandit for a category the first time
        it's seen. A = identity matrix (no prior knowledge), b = zero
        vector — standard LinUCB cold-start initialization.
        """
        if category not in self.categories:
            self.categories[category] = {
                "A": np.identity(N_FEATURES),
                "b": np.zeros(N_FEATURES),
                "n_observations": 0,
            }
        return self.categories[category]

    def _extract_features(self, product, all_candidates):
        """
        Converts a product's raw attributes into a normalized feature
        vector, relative to the OTHER candidates in this specific
        decision (so "price_normalized" means "cheap relative to these
        other options right now", not some fixed global scale).
        """
        prices = [c["price"] for c in all_candidates]
        ratings = [c["rating"] for c in all_candidates]
        stocks = [c["stock"] for c in all_candidates]

        def normalize(value, values):
            lo, hi = min(values), max(values)
            if hi == lo:
                return 0.5  # all candidates identical on this feature
            return (value - lo) / (hi - lo)

        return np.array([
            normalize(product["price"], prices),
            normalize(product["rating"], ratings),
            normalize(product["stock"], stocks),
        ])

    def has_sufficient_data(self, category):
        """
        Returns True only if this category has accumulated enough real
        purchase-outcomes for the bandit's preference to be genuinely
        reward-informed, rather than a cold-start exploration artifact
        (which, at n=0, is really just picking the candidate with the
        largest feature-vector magnitude — not learning).
        """
        if category not in self.categories:
            return False
        return self.categories[category]["n_observations"] >= MIN_OBSERVATIONS_TO_OVERRIDE

    def select(self, candidates, category):
        """
        Given a list of candidate products (all already judged as valid
        matches by the LLM) and their shared category, returns the single
        candidate the bandit currently believes is the best choice —
        balancing known-good options (exploitation) against
        under-tried ones (exploration).

        Callers should check has_sufficient_data() before trusting this
        as a genuinely learned preference — see the class docstring.
        """
        state = self._get_category_state(category)
        A_inv = np.linalg.inv(state["A"])
        theta = A_inv @ state["b"]  # current best estimate of feature-weights

        best_score = -np.inf
        best_candidate = candidates[0]

        for product in candidates:
            x = self._extract_features(product, candidates)
            expected_reward = theta @ x
            uncertainty_bonus = ALPHA * np.sqrt(x @ A_inv @ x)
            ucb_score = expected_reward + uncertainty_bonus  # the "upper confidence bound"

            if ucb_score > best_score:
                best_score = ucb_score
                best_candidate = product

        return best_candidate

    def update(self, chosen_product, all_candidates, category, reward):
        """
        Called AFTER we know the outcome of a selection (e.g. the purchase
        succeeded = reward 1.0, or failed/was rejected = reward 0.0).
        This is what makes the bandit actually learn over time, and also
        increments the observation-count used by has_sufficient_data().
        """
        state = self._get_category_state(category)
        x = self._extract_features(chosen_product, all_candidates)

        state["A"] += np.outer(x, x)
        state["b"] += reward * x
        state["n_observations"] += 1

        self._save_state()


if __name__ == "__main__":
    fake_candidates = [
        {"id": "A", "price": 550, "rating": 3.9, "stock": 15},
        {"id": "B", "price": 480, "rating": 4.1, "stock": 25},
        {"id": "C", "price": 510, "rating": 4.3, "stock": 18},
    ]

    print("=" * 60)
    print("Robustness check: repeating the experiment 20 times with fresh bandits")
    winner_tally = {"A": 0, "B": 0, "C": 0}
    for trial in range(20):
        trial_bandit = LinUCBBandit()
        trial_bandit.categories = {}  # fresh state, ignore any saved file for this check
        counts = {"A": 0, "B": 0, "C": 0}
        for _ in range(40):
            choice = trial_bandit.select(fake_candidates, category=f"trial_{trial}")
            counts[choice["id"]] += 1
            success_probability = {"A": 0.3, "B": 0.5, "C": 0.9}[choice["id"]]
            reward = 1.0 if np.random.random() < success_probability else 0.0
            trial_bandit.update(choice, fake_candidates, category=f"trial_{trial}", reward=reward)
        winner = max(counts, key=counts.get)
        winner_tally[winner] += 1
        print(f"Trial {trial + 1}: {counts} -> winner: {winner}")

    print(f"\nWinner tally across 20 trials: {winner_tally}")
    print(f"(Expected: C wins the vast majority, since it has the highest true success-rate)")

    print("\n" + "=" * 60)
    print("Safety-mechanism check: has_sufficient_data() before/after threshold")
    test_bandit = LinUCBBandit()
    test_bandit.categories = {}
    print(f"Before any updates: has_sufficient_data('TestCat') = {test_bandit.has_sufficient_data('TestCat')}")
    for i in range(MIN_OBSERVATIONS_TO_OVERRIDE):
        test_bandit.update(fake_candidates[0], fake_candidates, category="TestCat", reward=1.0)
        print(f"After {i + 1} update(s): has_sufficient_data('TestCat') = {test_bandit.has_sufficient_data('TestCat')}")