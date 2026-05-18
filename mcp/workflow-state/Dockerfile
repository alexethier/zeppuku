FROM aethier-mcp-base

COPY mcp/lib /tmp/mcp-lib
RUN pip install --no-cache-dir /tmp/mcp-lib && rm -rf /tmp/mcp-lib

COPY mcp/workflow-state /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_workflow_state"]
