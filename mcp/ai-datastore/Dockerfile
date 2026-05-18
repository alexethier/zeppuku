FROM aethier-mcp-base

COPY mcp/lib /tmp/lib
RUN pip install --no-cache-dir /tmp/lib && rm -rf /tmp/lib

COPY mcp/ai-datastore /tmp/mcp
RUN pip install --no-cache-dir /tmp/mcp && rm -rf /tmp/mcp

CMD ["python", "-m", "aethier_mcp_ai_datastore"]
