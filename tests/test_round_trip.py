"""Tests for round-trip verification."""

import pytest

from flowscript_ldp.round_trip import (
    verify_fallback_chain,
    verify_mode3_round_trip,
    verify_queries_on_decoded,
)


class TestMode3RoundTrip:
    def test_simple_ir_round_trips(self, simple_ir):
        result = verify_mode3_round_trip(simple_ir)
        assert result["passed"] is True
        assert all(result["checks"].values())

    def test_decision_ir_round_trips(self, decision_ir):
        result = verify_mode3_round_trip(decision_ir)
        assert result["passed"] is True

    def test_blocker_ir_round_trips(self, blocker_ir):
        result = verify_mode3_round_trip(blocker_ir)
        assert result["passed"] is True


class TestQueriesOnDecoded:
    def test_queries_work_on_decoded_simple(self, simple_ir):
        result = verify_queries_on_decoded(simple_ir)
        assert result["all_passed"] is True

    def test_queries_work_on_decoded_decision(self, decision_ir):
        result = verify_queries_on_decoded(decision_ir)
        assert result["all_passed"] is True
        assert result["queries"]["alternatives"]["passed"] is True

    def test_queries_work_on_decoded_blocker(self, blocker_ir):
        result = verify_queries_on_decoded(blocker_ir)
        assert result["queries"]["blocked"]["passed"] is True


class TestFallbackChain:
    def test_fallback_chain_simple(self, simple_ir):
        result = verify_fallback_chain(simple_ir)
        assert result["all_passed"] is True

    def test_fallback_chain_decision(self, decision_ir):
        result = verify_fallback_chain(decision_ir)
        assert result["all_passed"] is True
        assert result["fallbacks"]["mode3_to_mode1"]["task_type"] == "decision_analysis"

    def test_fallback_chain_blocker(self, blocker_ir):
        result = verify_fallback_chain(blocker_ir)
        assert result["all_passed"] is True
