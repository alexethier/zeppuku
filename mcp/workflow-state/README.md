# workflow-state

Minimal MCP server for workflow state transitions backed by one CSV snapshot
file and `csvq`.

- Snapshot file: `/Users/aethier/playground/workflow_state/workflow_instances.csv`
- Lock file: `/Users/aethier/playground/workflow_state/workflow.lock`
- Columns: `workflow_id`, `state`

Tools:
- `create_workflow(workflow_id, initial_state)`
- `get_workflow(workflow_id)`
- `list_workflows()`
- `transition_workflow(workflow_id, to_state)`
- `delete_workflow(workflow_id)`

## States

Allowed states:

- `backlog`
- `implementation_plan:drafted`
- `implementation_plan:accepted`
- `implementation_plan:denied`
- `implemented`
- `implementation:accepted`
- `implementation:denied`
- `in_depth_review:accepted`
- `in_depth_review:denied`
- `smoke_test_runbook:drafted`
- `smoke_test_runbook:accepted`
- `smoke_test_runbook:denied`
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

## Run

```bash
./bin/bridge.sh start
./bin/manager start workflow-state
```

## Inspect

```bash
./bin/mcp workflow-state tools
./bin/mcp workflow-state call create_workflow workflow_id=FLOW-123 initial_state=backlog
./bin/mcp workflow-state call get_workflow workflow_id=FLOW-123
./bin/mcp workflow-state call list_workflows
./bin/mcp workflow-state call transition_workflow workflow_id=FLOW-123 to_state=implementation_plan:drafted
./bin/mcp workflow-state call delete_workflow workflow_id=FLOW-123
```
