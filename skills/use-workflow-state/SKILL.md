---
name: use-workflow-state
description: Use when the user asks to track feature development state for a task (jira) by creating, reading, or transitioning workflow state.
---

# Use workflow-state

Use the `workflow-state` MCP to track feature development state for Jira tasks.

It stores exactly one current state per `workflow_id` in a CSV snapshot.

When you need state-specific execution behavior, read `state-agent-guidance.md` in this same directory. Do not assume it is preloaded; consult it explicitly only after this skill is loaded and the current state is known.

## When to use this

Use this skill when the user asks to:

- Create a workflow state record
- Check current state for a workflow
- Move a workflow to a new state

## Tool behavior

- `create_workflow(workflow_id, initial_state)`:
  - Creates a new workflow entry with a canonical state.
  - Returns no value.
  - Raises if `workflow_id` already exists or state is invalid.

- `get_workflow(workflow_id)`:
  - Returns the current state string.
  - Raises if `workflow_id` does not exist.

- `transition_workflow(workflow_id, to_state)`:
  - Updates current state for an existing workflow.
  - Returns no value.
  - Raises if `workflow_id` does not exist, state is invalid, or transition is not allowed.

## Canonical states

- `backlog`
- `implementation_plan:drafted`
- `implementation_plan:accepted`
- `implementation_plan:denied`
- `implemented`
- `implementation:accepted`
- `implementation:denied`
- `in_depth_review:accepted`
- `in_depth_review:denied`
- `smoke_test_plan:drafted`
- `smoke_test_plan:accepted`
- `smoke_test_plan:denied`
- `instrumentation_added`
- `test_plan_with_instrumentation_added`
- `tested:instrumentation`
- `tested:instrumentation:repeated:accepted`
- `tested:instrumentation:repeated:denied`
- `jenkins_build:success`
- `jenkins_build:failure`
- `cleanup:remove_instrumentation`
- `final_smoke_test:accepted`
- `final_smoke_test:denied`
- `final_jenkins_build:success:ready_for_human`
- `final_jenkins_build:denied`

## State meanings

- `backlog`: The workflow exists but work has not started yet.
- `implementation_plan:drafted`: An implementation plan is being drafted and is not yet reviewed.
- `implementation_plan:accepted`: The implementation plan is approved and execution can proceed.
- `implementation_plan:denied`: The implementation plan was rejected and must be revised.
- `implemented`: Code changes have been made and are ready for implementation review.
- `implementation:accepted`: The implementation itself is approved and test planning can begin.
- `in_depth_review:accepted`: In-depth review passed and smoke-test planning can begin.
- `in_depth_review:denied`: In-depth review failed and implementation changes are required before re-review.
- `implementation:denied`: The implementation review failed and code changes are required.
- `smoke_test_plan:drafted`: A smoke-test plan is being drafted and not yet approved.
- `smoke_test_plan:accepted`: The smoke-test plan is approved and instrumentation update can proceed.
- `smoke_test_plan:denied`: The smoke-test plan was rejected and needs updates.
- `instrumentation_added`: Required instrumentation has been added after smoke-test plan approval.
- `test_plan_with_instrumentation_added`: The test plan has been updated with instrumentation and is ready for execution.
- `tested:instrumentation`: Tests were executed with instrumentation according to the accepted plan.
- `tested:instrumentation:repeated:accepted`: Repeated instrumented testing passed and can proceed to Jenkins success validation.
- `tested:instrumentation:repeated:denied`: Repeated instrumented testing failed and can proceed to Jenkins failure validation.
- `jenkins_build:success`: Jenkins build validation passed and the workflow moves into cleanup/final smoke validation.
- `jenkins_build:failure`: Jenkins build validation failed and the workflow returns to re-testing.
- `cleanup:remove_instrumentation`: Post-build cleanup removes instrumentation before final smoke validation.
- `final_smoke_test:accepted`: Final smoke testing passed and final Jenkins success can be recorded.
- `final_smoke_test:denied`: Final smoke testing failed and final Jenkins denial is recorded.
- `final_jenkins_build:success:ready_for_human`: Final Jenkins validation passed and the workflow is ready for human handoff.
- `final_jenkins_build:denied`: Final Jenkins validation failed and the workflow ends in denied state.

## Transition rules

- `backlog -> implementation_plan:drafted`
- `implementation_plan:drafted -> implementation_plan:accepted|implementation_plan:denied`
- `implementation_plan:accepted -> implemented`
- `implementation_plan:denied -> implementation_plan:drafted`
- `implemented -> implementation:accepted|implementation:denied`
- `implementation:accepted -> in_depth_review:accepted|in_depth_review:denied`
- `in_depth_review:accepted -> smoke_test_plan:drafted`
- `in_depth_review:denied -> implemented`
- `implementation:denied -> implemented`
- `smoke_test_plan:drafted -> smoke_test_plan:accepted|smoke_test_plan:denied`
- `smoke_test_plan:denied -> smoke_test_plan:drafted`
- `smoke_test_plan:accepted -> instrumentation_added`
- `instrumentation_added -> test_plan_with_instrumentation_added`
- `test_plan_with_instrumentation_added -> tested:instrumentation`
- `tested:instrumentation -> tested:instrumentation:repeated:accepted|tested:instrumentation:repeated:denied`
- `tested:instrumentation:repeated:accepted -> jenkins_build:success`
- `tested:instrumentation:repeated:denied -> jenkins_build:failure`
- `jenkins_build:success -> cleanup:remove_instrumentation`
- `jenkins_build:failure -> tested:instrumentation`
- `cleanup:remove_instrumentation -> final_smoke_test:accepted|final_smoke_test:denied`
- `final_smoke_test:accepted -> final_jenkins_build:success:ready_for_human`
- `final_smoke_test:denied -> final_jenkins_build:denied`
- `final_jenkins_build:success:ready_for_human` is terminal (no outgoing transitions)
- `final_jenkins_build:denied` is terminal (no outgoing transitions)

## Practical conventions

- Keep `workflow_id` stable for the life of the task (for example, a Jira key).
- Keep state values canonical and explicit (for example, `backlog`, `implementation_plan:drafted`, `smoke_test_plan:accepted`).
- Prefer reading current state with `get_workflow` before transitioning when context is uncertain.

## Call patterns

### Create

Call:

- `create_workflow(workflow_id=<id>, initial_state=<state>)`

### Read

Call:

- `get_workflow(workflow_id=<id>)`

Use the returned string directly as the source of truth.

### Transition

Call:

- `transition_workflow(workflow_id=<id>, to_state=<state>)`

Then optionally call `get_workflow` to confirm.

## Notes

- This MCP enforces canonical states and strict transition edges.
- Denied states follow the explicit transition edges listed above.
- Transition history is intentionally not tracked in this phase.
