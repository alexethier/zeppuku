from __future__ import annotations

import unittest

from aethier_mcp_workflow_state.validators import (
    validate_state,
    validate_transition,
    validate_workflow_id,
)


class ValidatorsTest(unittest.TestCase):
    def test_validate_workflow_id_accepts_jira_style_key(self) -> None:
        self.assertEqual(validate_workflow_id("FLOW-123"), "FLOW-123")

    def test_validate_workflow_id_rejects_spaces(self) -> None:
        with self.assertRaises(ValueError):
            validate_workflow_id("FLOW 123")

    def test_validate_state_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_state("   ")

    def test_validate_state_accepts_canonical_value(self) -> None:
        self.assertEqual(
            validate_state("implementation_plan:drafted"),
            "implementation_plan:drafted",
        )

    def test_validate_state_rejects_legacy_alias(self) -> None:
        with self.assertRaises(ValueError):
            validate_state("implemenation_plan_accepted")

    def test_validate_state_rejects_removed_ready_for_human_alias(self) -> None:
        with self.assertRaises(ValueError):
            validate_state("ready_for_human")

    def test_validate_state_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            validate_state("planning")

    def test_validate_transition_allows_denied_loop(self) -> None:
        validate_transition("implementation_plan:denied", "implementation_plan:drafted")

    def test_validate_transition_places_in_depth_after_implementation_accepted(self) -> None:
        validate_transition("implementation:accepted", "in_depth_review:accepted")
        validate_transition("implementation:accepted", "in_depth_review:denied")
        validate_transition("in_depth_review:accepted", "smoke_test_runbook:drafted")
        validate_transition("in_depth_review:denied", "implemented")

    def test_validate_transition_repeated_test_moves_to_jenkins(self) -> None:
        validate_transition(
            "tested:instrumentation",
            "tested:instrumentation:repeated:accepted",
        )
        validate_transition(
            "tested:instrumentation",
            "tested:instrumentation:repeated:denied",
        )
        validate_transition(
            "tested:instrumentation:repeated:accepted",
            "jenkins_build:success",
        )
        validate_transition(
            "tested:instrumentation:repeated:denied",
            "jenkins_build:failure",
        )

    def test_validate_transition_requires_instrumentation_before_tested(self) -> None:
        validate_transition("smoke_test_runbook:accepted", "instrumentation_added")
        validate_transition("instrumentation_added", "test_plan_with_instrumentation_added")
        validate_transition("test_plan_with_instrumentation_added", "tested:instrumentation")

    def test_validate_transition_requires_cleanup_and_final_smoke(self) -> None:
        validate_transition("jenkins_build:success", "cleanup:remove_instrumentation")
        validate_transition("cleanup:remove_instrumentation", "final_smoke_test:accepted")
        validate_transition("cleanup:remove_instrumentation", "final_smoke_test:denied")
        validate_transition(
            "final_smoke_test:accepted",
            "final_jenkins_build:success:ready_for_human",
        )
        validate_transition("final_smoke_test:denied", "final_jenkins_build:denied")

    def test_validate_transition_rejects_old_in_depth_denied_edge(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition("in_depth_review:denied", "tested:instrumentation:repeated")

    def test_validate_transition_rejects_invalid_edge(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition("backlog", "implemented")


if __name__ == "__main__":
    unittest.main()
