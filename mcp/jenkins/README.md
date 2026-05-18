# jenkins

Read-only MCP for a Jenkins deployment. Talks directly
to the REST API via `httpx` (no host bridge, no Java). Six tools:
`who_am_i()` for auth sanity; `list_jobs(folder="")` to browse (returns
`{name, url, color, type}` per entry, `type` ∈ pipeline / freestyle /
folder / multibranch); `get_job_status(name)` for current state
(`color`, `running`, `in_queue`, `last_build`); `list_runs(name, limit=20)`
for recent build history (newest first, capped 100); `console(name,
build="lastBuild", tail=500)` for log tails (build accepts a number or
any `last*Build` permalink, `tail=-1` for full log capped at 50k lines);
and `await_run(name, build_number)` which checks one specific build once
per call and returns immediately with a `sleep_before_retry_s` hint —
the agent sleeps and re-calls until status is terminal. Timing is
internal (500 s early sleeps, 60 s late sleeps, 60 min hard deadline).
Find `build_number` via `list_runs()`. Names are validated as path-safe
(`%` allowed for branch names like `dev%2FFLOW-10705`). Required env:
`JENKINS_URL`, `JENKINS_USER`, `JENKINS_TOKEN`; export them before
`./bin/manager start jenkins` and `restart` after rotating tokens.

```bash
export JENKINS_URL="https://jenkins.example.com"
export JENKINS_USER="aethier"
export JENKINS_TOKEN="..."
./bin/manager start jenkins
```
