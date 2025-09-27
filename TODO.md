## Basic Implementations

- [x] Implement session manager (Local)
- [x] Implement conversation manager (Sliding Window)
- [x] Front-end test interface
- [ ] Add User and Session IDs to Agent State (Enable future Tool Use Extensibility)
- [ ] Add authentication mechanism
- [ ] Custom Example @tools to be Added
- [ ] Add [Memory Tool](https://strandsagents.com/latest/documentation/docs/examples/python/memory_agent/?h=memory#mem0-memory-agent-personalized-context-through-persistent-memory), e.g; `Remember My Name is XYZ`
- [ ] Examples MCP Integration
- [ ] Examples of Agent Structured Output
- [ ] Examples of Multi-Agent Orchestration Agents As Tools
- [ ] Examples of Multi-Agent Orchestration Swarm

## Intermediate Implementations
- [ ] Trace Token Usage and M
- [ ] Yield properly tool_use and reasoning deltas [See Events](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/async-iterators/#example-event-loop-lifecycle-tracking) 
- [ ] Explore flexible approaches to share context-windows across different agents
- [ ] Add [Temeletry Features](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/observability/)
- [ ] Fail-safe approach for future switch between Sliding Window and Summarizing Conversation Managers in the same session

## Advanced/Experimental Implementations
- [ ] Implement Update Agent Mechanism Still Experimental Feature see: [Issue #606](https://github.com/strands-agents/sdk-python/issues/606) and [Issue #865](https://github.com/strands-agents/sdk-python/pull/865)