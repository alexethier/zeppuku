# Build context: workspace root.
#   docker build -f mcp/slack-dev/Dockerfile -t aethier-mcp-slack-dev .
# Base image (aethier-mcp-base) is built automatically by bin/manager.
FROM aethier-mcp-base

COPY mcp/slack-dev /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_slack"]
