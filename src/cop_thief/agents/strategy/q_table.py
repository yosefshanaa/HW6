"""Optional tabular Q-Learning (assignment §8, PRD_agent_strategy §2.3).

Dependency-free (plain dict) so it never pulls deep-learning libraries. This
provides the Bellman update core; a policy can be layered on top later.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field


@dataclass
class QTable:
    """A tabular action-value function with the Bellman (TD) update."""

    num_actions: int
    learning_rate: float = 0.1
    discount_factor: float = 0.9
    q: dict[tuple[Hashable, int], float] = field(default_factory=dict)

    def value(self, state: Hashable, action: int) -> float:
        """Current estimate of ``Q(state, action)``."""
        return self.q.get((state, action), 0.0)

    def best_value(self, state: Hashable) -> float:
        """Max action-value in ``state`` (0 if unseen)."""
        return max((self.value(state, a) for a in range(self.num_actions)), default=0.0)

    def best_action(self, state: Hashable) -> int:
        """Greedy action in ``state``."""
        return max(range(self.num_actions), key=lambda a: self.value(state, a))

    def update(
        self,
        state: Hashable,
        action: int,
        reward: float,
        next_state: Hashable,
        done: bool,
    ) -> float:
        """Apply the Bellman update and return the new ``Q(state, action)``."""
        best_next = 0.0 if done else self.best_value(next_state)
        td_target = reward + self.discount_factor * best_next
        td_error = td_target - self.value(state, action)
        new_value = self.value(state, action) + self.learning_rate * td_error
        self.q[(state, action)] = new_value
        return new_value
