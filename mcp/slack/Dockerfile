# Build context: workspace root.
#   docker build -f mcp/slack/Dockerfile -t aethier-mcp-slack .
# Base image (aethier-mcp-base) is built automatically by bin/manager.
FROM aethier-mcp-base

COPY mcp/slack /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_slack"]
