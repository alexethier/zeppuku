# host-poc

Proof-of-concept MCP that exercises the aethier-mcp host bridge with
two tiny tools: `ls(path)` runs `ls -la <path>` on the host, and `env()`
dumps the bridge process's environment variables. Useful for sanity-checking
the bridge is wired up and for diagnosing PATH/credential issues with
other host-bridged MCPs (call `env()` to see exactly what the bridge sees).

```bash
./bin/bridge.sh start
./bin/manager start host-poc
```
