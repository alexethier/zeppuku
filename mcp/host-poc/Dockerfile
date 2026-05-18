# Build context: workspace root.
#   docker build -f mcp/host-poc/Dockerfile -t aethier-mcp-host-poc .
# Base image (aethier-mcp-base) is built automatically by bin/manager.
FROM aethier-mcp-base

COPY mcp/host-poc /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_host_poc"]
