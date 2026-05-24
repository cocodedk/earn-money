from __future__ import annotations

import pytest
from apps.agent.plateau import PlateauDetector


class TestNoPlateauInitially:
    def test_fresh_detector_not_plateaued(self):
        pd = PlateauDetector()
        assert pd.is_plateaued() is False
        assert pd.plateau_reason() == ""


class TestRoutePlateau:
    def test_plateau_after_n_turns_without_route(self):
        pd = PlateauDetector(max_turns_without_new_route=3)
        for _ in range(3):
            pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is True
        assert "route" in pd.plateau_reason()

    def test_no_plateau_before_limit(self):
        pd = PlateauDetector(max_turns_without_new_route=3)
        for _ in range(2):
            pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is False

    def test_route_discovery_resets_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=3,
            max_turns_without_new_interactive_element=100,
        )
        for _ in range(2):
            pd.record_turn(new_routes=0, new_elements=0)
        pd.record_turn(new_routes=1, new_elements=0)
        # counter reset; 2 more without route should not plateau
        for _ in range(2):
            pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is False

    def test_route_discovery_plateaus_after_reset_then_n_turns(self):
        pd = PlateauDetector(
            max_turns_without_new_route=2,
            max_turns_without_new_interactive_element=100,
        )
        pd.record_turn(new_routes=1, new_elements=0)
        pd.record_turn(new_routes=0, new_elements=0)
        pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is True


class TestInteractiveElementPlateau:
    def test_plateau_after_n_turns_without_elements(self):
        pd = PlateauDetector(
            max_turns_without_new_route=100,
            max_turns_without_new_interactive_element=3,
        )
        for _ in range(3):
            pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is True
        assert "interactive" in pd.plateau_reason()

    def test_element_discovery_resets_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=100,
            max_turns_without_new_interactive_element=3,
        )
        pd.record_turn(new_routes=0, new_elements=0)
        pd.record_turn(new_routes=0, new_elements=0)
        pd.record_turn(new_routes=0, new_elements=1)
        for _ in range(2):
            pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is False


class TestDenialPlateau:
    def test_plateau_after_n_denials(self):
        pd = PlateauDetector(max_repeated_denials=3)
        for _ in range(3):
            pd.record_denial()
        assert pd.is_plateaued() is True
        assert "denial" in pd.plateau_reason()

    def test_no_plateau_before_limit(self):
        pd = PlateauDetector(max_repeated_denials=3)
        pd.record_denial()
        pd.record_denial()
        assert pd.is_plateaued() is False

    def test_successful_turn_resets_denial_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=100,
            max_turns_without_new_interactive_element=100,
            max_repeated_denials=3,
        )
        pd.record_denial()
        pd.record_denial()
        pd.record_turn(new_routes=1, new_elements=0)
        pd.record_denial()
        pd.record_denial()
        assert pd.is_plateaued() is False


class TestInvalidActionPlateau:
    def test_plateau_after_n_invalid_actions(self):
        pd = PlateauDetector(max_invalid_actions=2)
        pd.record_invalid()
        pd.record_invalid()
        assert pd.is_plateaued() is True
        assert "invalid" in pd.plateau_reason()

    def test_no_plateau_before_limit(self):
        pd = PlateauDetector(max_invalid_actions=2)
        pd.record_invalid()
        assert pd.is_plateaued() is False

    def test_successful_turn_resets_invalid_counter(self):
        pd = PlateauDetector(
            max_turns_without_new_route=100,
            max_turns_without_new_interactive_element=100,
            max_invalid_actions=2,
        )
        pd.record_invalid()
        pd.record_turn(new_routes=0, new_elements=1)
        pd.record_invalid()
        assert pd.is_plateaued() is False


class TestCustomLimits:
    def test_single_turn_limit(self):
        pd = PlateauDetector(max_turns_without_new_route=1)
        pd.record_turn(new_routes=0, new_elements=0)
        assert pd.is_plateaued() is True

    def test_high_limits_never_plateau_early(self):
        pd = PlateauDetector(
            max_turns_without_new_route=100,
            max_turns_without_new_interactive_element=100,
            max_repeated_denials=100,
            max_invalid_actions=100,
        )
        for _ in range(50):
            pd.record_turn(new_routes=0, new_elements=0)
            pd.record_denial()
            pd.record_invalid()
        assert pd.is_plateaued() is False
