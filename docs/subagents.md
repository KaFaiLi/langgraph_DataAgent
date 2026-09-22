# Conversational sub-agents

Conversational agents can delegate research to a child ReAct agent. The parent waits for
the result, then continues its own reasoning. Independent delegation calls from the same
model response run in parallel, subject to the configured concurrency limit.

## Enable delegation

Set this in your local `.env`:

```dotenv
SUBAGENTS_ENABLED=true
```

Then use the existing chat command, for example:

```powershell
uv run data-agent chat "Compare the two source reports. Delegate their independent investigations, then summarize the differences."
```

Delegation is model-selected, so enabling it does not force every request to start a
child. The parent should use ordinary tools for simple tasks and delegate work that
benefits from separate context. The default `research` child uses a restricted set of
read-only source tools under the configured `SOURCE_ROOT`.

The Python entrypoint is unchanged:

```python
from data_agent.agent import build_agent
from data_agent.config import Settings

bundle = await build_agent(Settings(subagents_enabled=True))
answer = await bundle.ask("Investigate these independent source reports and compare them.")
```

`bundle.all_tools` includes the local `run_subagent` tool when delegation is enabled.
That tool is part of the agent host; it is not exposed by the MCP server.

## Execution limits

| Setting | Default | Meaning |
| --- | --- | --- |
| `SUBAGENTS_ENABLED` | `false` | Enable conversational delegation. |
| `SUBAGENT_MAX_RUNS` | `4` | Maximum child attempts per root invocation. |
| `SUBAGENT_MAX_CONCURRENCY` | `2` | Maximum children running simultaneously in that invocation. |
| `SUBAGENT_MAX_MODEL_CALLS` | `6` | Maximum logical model calls per child. |
| `SUBAGENT_MAX_TOOL_CALLS` | `12` | Maximum tool calls per child. |
| `SUBAGENT_TIMEOUT_SECONDS` | `120` | Child deadline, including queue time. |
| `SUBAGENT_MAX_INPUT_CHARS` | `16000` | Maximum combined task and context length. |
| `SUBAGENT_MAX_RESULT_CHARS` | `8000` | Maximum child answer length returned to the parent. |

For ordinary unbound chat, failed attempts consume the child-attempt budget. Each new invocation gets fresh limits,
including concurrent requests through a reused bundle. Limits count logical calls;
provider-internal retries and token charges are separate. The parent retains its existing
`AGENT_MAX_ITERATIONS` configuration.

Children cannot delegate further. They receive a fresh conversation containing their
assigned task and selected context. The parent receives a bounded result with status,
output, call counts, and an explicit truncation flag. Child failure does not discard the
results of successful siblings. Cancellation of the parent cancels its local child tasks.
An already-dispatched remote request or synchronous operation may still finish remotely.

## Register a trusted child profile

Applications can supply explicit profiles when building a bundle:

```python
from data_agent.agent import build_agent
from data_agent.agent.subagents import SubagentSpec
from data_agent.config import Settings

profile = SubagentSpec(
    name="document_research",
    description="Investigate a document and report evidence and limitations.",
    system_prompt="Read the assigned source material and return a concise evidence summary.",
    tool_names=("search_text", "read_lines", "read_document_section"),
    skill_names=(),
)
bundle = await build_agent(
    Settings(subagents_enabled=True),
    subagent_specs=[profile],
)
```

Profiles are trusted application configuration. Tool names must be available to the root;
skills must exist in its discovered catalog. Additional application tools are root-only
unless explicitly included in a child profile. Profiles do not grant tools access beyond
their existing source and execution guards. A task's named paths guide research; they do
not establish a separate file-level authorization scope.

The default child has no skills. Enable a skill only after confirming its instructions can
be followed with the profile's permitted tools. Skill loading remains in the shared skill
module and does not register executable agents.

## Graphs, traces and persistence

`bundle.agent.ainvoke(...)`, `bundle.agent.astream(...)`, and the graph returned by
`data_agent.agent.graph.make_graph()` use the same invocation lifecycle. When delegation
is enabled, an outer lifecycle graph owns task cleanup; nested streaming updates include
an additional graph namespace. Use `subgraphs=True` when inspecting nested updates.

Shared execution traces identify root and child agents. Delegation arguments retain
metadata and text lengths instead of task/context bodies. Result previews remain disabled
by default; enabling previews can expose tool-result content and should be deliberate.
Children inherit trace ancestry and approved tracing fields; arbitrary parent metadata,
application configuration, and checkpoint identities are excluded from child execution.

Children have no persistent conversation or resumable checkpoint. Ordinary unbound chat
may repeat delegated work on replay. Review commands use `AgentReviewService`: its root
ReAct loop is checkpointed, accepted typed role results are reused through durable tool
identities, and interrupted children return explicit failures. Aggregate model/tool/child
and elapsed-time limits persist across restarts. Review profiles are specialist (low-cost),
independent challenger (low-cost), adjudicator (high-cost, no research tools), and lead /
lead verifier (high-cost, validated reports only). The parent coordinates them through
capabilities; it never invokes the legacy review graphs. See the
[runtime contract](architecture/general-agent-review-runtime.md) for status and persistence.

See the [design plan](plans/react-subagents.md) for module ownership and later extensions.
