from __future__ import annotations


class PlateauDetector:
    """Detects when an agent phase has stopped making progress."""

    def __init__(
        self,
        max_turns_without_new_route: int = 3,
        max_turns_without_new_interactive_element: int = 3,
        max_repeated_denials: int = 3,
        max_invalid_actions: int = 2,
        known_routes: set[str] | None = None,
    ) -> None:
        self._max_no_route = max_turns_without_new_route
        self._max_no_element = max_turns_without_new_interactive_element
        self._max_denials = max_repeated_denials
        self._max_invalid = max_invalid_actions
        self._known_routes: frozenset[str] | None = (
            frozenset(known_routes) if known_routes else None
        )

        self._seen_routes: set[str] = set(self._known_routes) if self._known_routes else set()
        self._turns_no_route: int = 0
        self._turns_no_element: int = 0
        self._denial_streak: int = 0
        self._invalid_streak: int = 0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_turn(
        self,
        new_routes: int,
        new_elements: int,
        route_paths: list[str] | None = None,
    ) -> None:
        """Record a completed turn with discovery counts.

        When *route_paths* and *known_routes* are both supplied, only paths
        not present in the baseline count as genuine new-route discoveries.
        """
        if route_paths is not None:
            novel_paths = [p for p in route_paths if p not in self._seen_routes]
            self._seen_routes.update(route_paths)
            effective_routes = len(novel_paths)
        else:
            effective_routes = new_routes

        if effective_routes > 0:
            self._turns_no_route = 0
        else:
            self._turns_no_route += 1

        if new_elements > 0:
            self._turns_no_element = 0
        else:
            self._turns_no_element += 1

        # A productive turn resets denial and invalid streaks.
        if effective_routes > 0 or new_elements > 0:
            self._denial_streak = 0
            self._invalid_streak = 0

    def record_denial(self) -> None:
        """Record a permission/access denied response."""
        self._denial_streak += 1

    def record_invalid(self) -> None:
        """Record an invalid action emitted by the model."""
        self._invalid_streak += 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_plateaued(self) -> bool:
        """Return True if any plateau condition is triggered."""
        return bool(self.plateau_reason())

    def plateau_reason(self) -> str:
        """Return a human-readable reason string, or empty string if not plateaued."""
        if self._turns_no_route >= self._max_no_route:
            return (
                f"No new routes discovered for {self._turns_no_route} consecutive turns "
                f"(limit={self._max_no_route})"
            )
        if self._turns_no_element >= self._max_no_element:
            return (
                f"No new interactive elements found for {self._turns_no_element} "
                f"consecutive turns (limit={self._max_no_element})"
            )
        if self._denial_streak >= self._max_denials:
            return (
                f"Received {self._denial_streak} consecutive denials "
                f"(limit={self._max_denials})"
            )
        if self._invalid_streak >= self._max_invalid:
            return (
                f"Emitted {self._invalid_streak} consecutive invalid actions "
                f"(limit={self._max_invalid})"
            )
        return ""
