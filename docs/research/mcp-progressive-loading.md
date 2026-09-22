# MCP servers, skills, and progressive tool loading

_Research note — 2026-09-21_

## Conclusions

1. **Do not treat `skills/` as the default home for MCP servers or tool implementations.** MCP defines a host/client/server protocol: servers expose tools, prompts, and resources; clients discover and invoke them. The protocol does not define a project `skills/` directory. OpenAI’s separate Skills documentation defines a skill as a directory centered on `SKILL.md` containing reusable instructions and supporting files. The clean boundary for this repository is therefore: keep MCP transport, server implementations, connection configuration, lifecycle, auth, and policy in the MCP/integration boundary; keep `skills/<name>/` for domain playbooks, instructions, references, and deterministic entrypoints.

   A skill may explain when to use an MCP server or tool family, and a capability bundle may package both pieces, but the wiring should remain explicit rather than making the skill folder an implicit executable/plugin registry. This is an architectural recommendation inferred from the cited interfaces, not an MCP requirement.

2. **MCP itself supports discovery optimization, not semantic “load the relevant tool” search.** `tools/list` supports pagination through cursors, and the specification permits caching. A server can advertise `listChanged` and notify clients to refresh the list. That reduces discovery cost and keeps client caches coherent, but pagination is not the same as model-directed deferred loading. The MCP specification also says the advertised set must not vary per connection or as a side effect of another request (apart from authorization-dependent results).

3. **True progressive/deferred loading is host/provider behavior.** OpenAI’s Responses API supports tool search: mark a remote MCP server with `defer_loading: true`, expose its label and description up front, and load individual function definitions only after the model searches for them. The OpenAI docs recommend namespaces or MCP servers for large tool surfaces. Client-executed tool search is the option when discovery depends on project or tenant state; hosted search is the simpler option when the inventory is known when the request is built. This is not a portable MCP feature and is limited to the documented OpenAI Responses/tool-search integrations.

4. **The documented LangChain path is client-side adaptation.** LangChain’s MCP documentation and adapter source show `MultiServerMCPClient` connecting to one or more servers, calling `get_tools()`, converting the results to LangChain tools, and passing them to an agent. That is a useful integration seam for repository-controlled filtering, routing, or a custom lazy loader, but the cited adapter API should not be assumed to provide OpenAI-style semantic deferred loading. LangGraph’s `ToolNode` is likewise an execution/lookup boundary for a supplied tool registry; any progressive selection policy belongs in the host/agent layer around that registry.

## Recommended boundaries

| Concern | Keep it in | Responsibility |
| --- | --- | --- |
| Task-specific instructions, workflow, examples, and domain terminology | `skills/<name>/` | Tell the model when a capability applies and how to use it safely. |
| Tool schemas, external data access, side effects, auth, approvals, and audit | MCP server / `data_agent.mcp_server` boundary | Implement and expose callable operations. Treat tool metadata and remote output as untrusted input. |
| Connection lifecycle, server selection, caching, filtering, tool-name collision handling, and deferred loading | Agent host / adapter layer | Decide what is available to the model for this run and enforce policy before invocation. |
| User-selected reusable message templates | MCP prompts, when appropriate | MCP prompts are user-controlled templates; they are not a replacement for repository skills or model-controlled tools. |

Practical consequence: a skill can name a stable MCP capability and provide guardrails, but it should not contain credentials, silently launch arbitrary servers, or bypass the host’s allowlist/approval policy. A local server may live in the same repository for deployment convenience, but it should remain a server/integration component with an explicit registration path.

## What “progressive loading” can mean here

- **Protocol-level:** page `tools/list`, cache stable definitions, and refresh after `notifications/tools/list_changed`.
- **Host-level:** expose only an allowlisted subset of the loaded MCP tools to the graph/model, or load a server/tool group after a classifier/router decision. This is application policy and should be tested for authorization and stale-schema behavior.
- **OpenAI-specific:** use Responses tool search with a deferred MCP server. The model initially sees the server’s high-level label/description; the selected tool definitions are injected later. The OpenAI tool-search guide says loaded tools are appended at the end of context to preserve the cache.

## Caveats

- MCP specification revisions and SDK APIs evolve. This note cites the current specification path consulted on 2026-09-21; pin the protocol/SDK versions used by the project and re-check behavior during implementation.
- MCP `listChanged` is an invalidation signal, not a promise that the client will automatically refresh or that a model will semantically search the new list; the client/host must implement that behavior.
- OpenAI `defer_loading` and `tool_search` are provider-specific. They should not be presented as capabilities guaranteed by an arbitrary MCP client, model, or LangGraph deployment.
- Tool annotations are hints and should be treated as untrusted unless the server is trusted. OpenAI also warns that remote MCP servers are third-party services and highlights prompt-injection and data-access risks. Keep secrets outside skill files and require approval for sensitive operations.
- The LangChain sources cited document the adapter’s current loading model, not a universal limitation on future LangChain/LangGraph releases. Re-validate the selected package version before relying on custom lazy loading.

## Primary sources

- [MCP specification: Tools](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx) — tool discovery, pagination, caching, list-change notifications, and model-controlled invocation.
- [MCP Python SDK: Connect to a real host](https://py.sdk.modelcontextprotocol.io/get-started/real-host/) — host/client/server roles and stdio server lifecycle.
- [MCP TypeScript SDK: Server](https://ts.sdk.modelcontextprotocol.io/server) — tools versus prompts, including prompt templates and change notifications.
- [LangChain MCP documentation](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/mcp.mdx) — `MultiServerMCPClient`, `get_tools()`, and conversion of MCP tools into LangChain tools.
- [LangChain MCP adapter source](https://github.com/langchain-ai/langchain-mcp-adapters/blob/main/langchain_mcp_adapters/client.py) — client-side loading of tools, prompts, resources, and server info.
- [LangGraph `ToolNode` source](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/tool_node.py) — supplied-tool registry and execution boundary.
- [OpenAI API: Skills](https://developers.openai.com/api/docs/guides/tools-skills) — skills as reusable instructions/supporting files with a `SKILL.md` manifest.
- [OpenAI API: Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) — hosted/client-executed search, deferred loading, namespaces, and MCP-server guidance.
- [OpenAI API: MCP servers](https://developers.openai.com/api/docs/guides/tools-connectors-mcp) — `defer_loading` for remote MCP servers and security caveats.
