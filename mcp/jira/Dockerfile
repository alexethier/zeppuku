# Build context: workspace root.
#   docker build -f mcp/jira/Dockerfile -t aethier-mcp-jira .
# Base image (aethier-mcp-base) is built automatically by bin/manager.
FROM aethier-mcp-base

COPY mcp/jira /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_jira"]
