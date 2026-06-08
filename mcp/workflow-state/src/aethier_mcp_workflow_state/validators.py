"""Input validation helpers for workflow-state tools."""
from __future__ import annotations

import re

WORKFLOW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

ALLOWED_STATES: set[str] = {
    "backlog",
    "implementation_plan:drafted",
    "implementation_plan:ai_review:requested",
    "implementation_plan:ai_review:addressed",
    "implementation_plan:accepted",
    "implementation_plan:denied",
    "implemented",
    "tests:requested",
    "tests:passed",
    "tests:failed",
    "implementation:accepted",
    "in_depth_review:accepted",
    "in_depth_review:denied",
    "implementation:denied",
    "smoke_test_runbook:drafted",
    "smoke_test_runbook:accepted",
    "smoke_test_runbook:denied",
    "instrumentation_added",
    "test_plan_with_instrumentation_added",
    "tested:instrumentation",
    "tested:instrumentation:repeated:accepted",
    "tested:instrumentation:repeated:denied",
    "jenkins_build:success",
    "jenkins_build:failure",
    "cleanup:remove_instrumentation",
    "final_smoke_test:accepted",
    "final_smoke_test:denied",
    "final_jenkins_build:success:ready_for_human",
    "final_jenkins_build:denied",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "backlog": {"implementation_plan:drafted"},
    "implementation_plan:drafted": {
        "implementation_plan:ai_review:requested",
    },
    "implementation_plan:ai_review:requested": {
        "implementation_plan:ai_review:addressed",
    },
    "implementation_plan:ai_review:addressed": {
        "implementation_plan:accepted",
        "implementation_plan:denied",
        "implementation_plan:drafted",
    },
    "implementation_plan:accepted": {"implemented"},
    "implementation_plan:denied": {"implementation_plan:drafted"},
    "implemented": {"implementation:accepted", "implementation:denied"},
    "implementation:accepted": {"in_depth_review:accepted", "in_depth_review:denied"},
    "in_depth_review:accepted": {"tests:requested"},
    "tests:requested": {"tests:passed", "tests:failed"},
    "tests:passed": {"smoke_test_runbook:drafted"},
    "tests:failed": {"implemented"},
    "in_depth_review:denied": {"implemented"},
    "implementation:denied": {"implemented"},
    "smoke_test_runbook:drafted": {"smoke_test_runbook:accepted", "smoke_test_runbook:denied"},
    "smoke_test_runbook:accepted": {"instrumentation_added"},
    "smoke_test_runbook:denied": {"smoke_test_runbook:drafted"},
    "instrumentation_added": {"test_plan_with_instrumentation_added"},
    "test_plan_with_instrumentation_added": {"tested:instrumentation"},
    "tested:instrumentation": {
        "tested:instrumentation:repeated:accepted",
        "tested:instrumentation:repeated:denied",
    },
    "tested:instrumentation:repeated:accepted": {"jenkins_build:success"},
    "tested:instrumentation:repeated:denied": {"jenkins_build:failure"},
    "jenkins_build:success": {"cleanup:remove_instrumentation"},
    "jenkins_build:failure": {"tested:instrumentation"},
    "cleanup:remove_instrumentation": {"final_smoke_test:accepted", "final_smoke_test:denied"},
    "final_smoke_test:accepted": {"final_jenkins_build:success:ready_for_human"},
    "final_smoke_test:denied": {"final_jenkins_build:denied"},
    "final_jenkins_build:success:ready_for_human": set(),
    "final_jenkins_build:denied": set(),
}

def validate_workflow_id(workflow_id: str) -> str:
    workflow_id = workflow_id.strip()
    if not WORKFLOW_ID_RE.match(workflow_id):
        raise ValueError(
            f"invalid workflow_id {workflow_id!r}: "
            "must match [A-Za-z0-9][A-Za-z0-9._:-]{0,127}"
        )
    return workflow_id


def validate_state(state: str) -> str:
    state = state.strip().lower()
    if not state:
        raise ValueError("state must be non-empty")
    if "\n" in state or "\r" in state:
        raise ValueError("state must be single-line")
    if state not in ALLOWED_STATES:
        allowed = ", ".join(sorted(ALLOWED_STATES))
        raise ValueError(f"invalid state {state!r}; allowed states: {allowed}")
    return state


def validate_transition(current_state: str, to_state: str) -> None:
    current = validate_state(current_state)
    target = validate_state(to_state)
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        allowed_text = ", ".join(sorted(allowed)) if allowed else "(none)"
        raise ValueError(
            f"invalid transition {current!r} -> {target!r}; "
            f"allowed next states: {allowed_text}"
        )
