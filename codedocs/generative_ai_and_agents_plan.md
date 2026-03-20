# Hands-on experience with Generative AI APIs and agent-style solutions: plan and documentation

This document is a **plan and documentation** only—no code is executed. It (1) defines **Generative AI APIs** and **agent-style solutions** in the context of this project, (2) documents where and how the repo uses them (evidence of hands-on experience), and (3) suggests a short plan to extend or demonstrate more if needed.

**Related docs:** [docs/API.md](docs/API.md) (provider, agents), [agentic_frameworks_langgraph_plan.md](agentic_frameworks_langgraph_plan.md) (LangGraph, orchestration), [lib/provider.py](lib/provider.py), [lib/agents.py](lib/agents.py).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **Generative AI APIs** | Using hosted or local APIs for **chat** (completions) and **embeddings**: request/response shape, streaming, multi-provider support, and error handling. |
| **Agent-style solutions** | Orchestrating multiple steps or tools (retrieval, location, calculator, web search) and optionally letting an LLM or router decide what to call; exposing “tools used” and citations. |
| **Documentation** | Single place that maps “hands-on experience” to concrete artifacts in this repo and outlines a small plan for more. |

---

## 2. Generative AI APIs: concepts and usage

### 2.1 Chat / completions API

- **Purpose:** Send a list of messages (system, user, assistant) and receive a text completion (the model’s reply). Used for RAG answers, chatbots, and any turn-based dialogue.
- **Typical shape:** Request: `{ "model": "...", "messages": [{ "role": "system"|"user"|"assistant", "content": "..." }], "stream": true|false }`. Response: either a single JSON object with `choices[0].message.content` or a stream of chunks (e.g. Server-Sent Events or JSON lines) with `delta.content`.
- **Streaming:** With `stream: true`, the client receives chunks as they are generated; the UI can display partial output for better perceived latency. Handling `delta.content` and connection/timeout errors is part of hands-on experience.
- **Multi-provider:** Different providers (OpenAI, OpenRouter, Ollama) share a similar message format but differ in base URL, auth, and sometimes response shape. A unified client or adapter (e.g. OpenAI-compatible client with configurable base URL) allows switching providers without changing app logic.

### 2.2 Embeddings API

- **Purpose:** Convert text into a fixed-size vector for similarity search (e.g. in a vector DB). Same model must be used for indexing and querying.
- **Typical shape:** Request: `{ "model": "...", "input": "text" | ["text1", "text2", ...] }`. Response: `{ "data": [{ "embedding": [ ... ] }] }`. Batch input reduces round-trips during ingestion.
- **Usage in RAG:** At ingest time, chunk text and call the embeddings API for each chunk (or batch); store vectors and payload in Qdrant. At query time, embed the user query and run similarity search. Both use the same model and client (e.g. OpenAI or OpenRouter).

### 2.3 Provider-specific details

- **OpenAI:** Official SDK; `client.chat.completions.create(...)` and `client.embeddings.create(...)`; API key in header; optional organization. Base URL is default OpenAI.
- **OpenRouter:** OpenAI-compatible API; same SDK with different base URL (`https://openrouter.ai/api/v1`) and API key; allows many models (OpenAI, Anthropic, Google, etc.) through one endpoint.
- **Ollama (local):** REST API at `OLLAMA_URL`; `POST /api/chat` for chat (messages + stream) and `POST /api/embed` for embeddings; no API key. Response format differs (e.g. JSON lines when streaming). The app uses `requests.post` for Ollama chat and a separate code path from the OpenAI client.

### 2.4 Error handling and configuration

- **Hands-on concerns:** Invalid or missing API key; rate limits (429); timeouts; content filters; malformed or empty responses. The app should catch exceptions, show a user-friendly message, and optionally log or increment error metrics. Configuration (base URL, model list, keys) from env keeps the same code usable across environments.

---

## 3. Agent-style solutions: concepts and usage

### 3.1 What “agent-style” means here

- **Agent:** A component that can use **tools** (e.g. search, calculator, API calls) and **reason** over one or more steps to produce an answer. The flow may be fixed (orchestrator calls tools in a defined order) or adaptive (LLM or router decides which tool to call next).
- **Orchestrator:** Coordinates multiple specialists or tools: route the user query to the right specialist(s), call them, aggregate results, and optionally pass combined context to an LLM for a final answer.
- **Tool-calling / function-calling:** The LLM returns a structured request to call a function (e.g. “retrieve(query)”) and the app executes it, then may send the result back to the LLM for another turn. This is “agent-style” in the sense that the model drives which tools are used.
- **Visibility:** Showing “Tools Used” and “Sources” (citations) in the UI is part of agent-style UX: the user sees which tools or agents were invoked and where the answer came from.

### 3.2 Patterns in this project

- **Custom orchestrator (lib/agents.py):** Keyword-based router selects specialists (retrieval_agent, location_agent, calculator_agent); each specialist is implemented as a function (retrieval_fn, location_fn, calculator_fn). Single pass: route → invoke selected specialists → aggregate context → caller runs LLM with that context. Returns tool_calls and A2UI directives (e.g. show_map, show_calculator) for the UI.
- **LangChain tool-calling agent (app_RAG_ollama_langchain.py):** One LLM (ChatOllama) and a list of tools (e.g. retrieve); `create_tool_calling_agent` + `AgentExecutor`. The model decides when to call a tool and with what arguments; the executor runs the tool and feeds the result back. Supports `invoke` and `stream`. This is a classic “ReAct-style” or tool-calling agent.
- **RAG as implicit “tool”:** In the main app (app.py), retrieval (vector or hybrid) and optional Tavily search are used before the LLM; the combined context is a form of “tool output” passed into the prompt. Tools Used and Sources make this visible.
- **MCP (lib/mcp_client.py):** Model Context Protocol–style tool registry so tools can be registered and invoked by the agent; supports future extension with more tools or servers.

---

## 4. Hands-on experience: where it appears in this repo

### 4.1 Generative AI APIs

| Area | Artifact | What is done |
|------|----------|---------------|
| **Multi-provider chat** | **lib/provider.py** | `get_llm_client(provider_override)` returns OpenAI-compatible client for `openai` or `openrouter` (base URL and API key from env). `get_available_llm_providers()` and `get_default_llm_models(provider)` drive sidebar. Ollama is explicitly not using this client; app uses Ollama URL and REST. |
| **Chat streaming (OpenAI/OpenRouter)** | **app.py** | `_stream_api(provider, model, messages, ...)` uses `client.chat.completions.create(..., stream=True)` and iterates over `chunk.choices[0].delta.content` to stream into the UI. Same pattern in app_phase1.py, app_wRAG.py. |
| **Chat streaming (Ollama)** | **app.py**, **app_wRAG.py**, **app_UploadPDF_Chat.py** | `_stream_ollama(...)` or `stream_ollama_response(...)` uses `requests.post(f"{base}/api/chat", json=payload, stream=True)` and parses JSON-lines response (`data["message"]["content"]`). Handles connection errors and Ollama-specific error payloads. |
| **Embeddings** | **lib/provider.py**, **scripts/ingest_docs.py**, **app** | `get_embedding_client()` returns OpenAI-compatible client (OpenAI or OpenRouter). Ingestion embeds chunks and upserts to Qdrant; app embeds the user query for retrieval. Same client and model for both when using same env. |
| **Embeddings (Ollama)** | **app_RAG_ollama_langchain.py** | Uses `OllamaEmbeddings` from LangChain for local embeddings when using Ollama stack. |
| **Semantic chunking with LLM** | **lib/chunking.py** | Optional `_split_long_section_with_llm()` calls `client.chat.completions.create(...)` to split long sections at semantic boundaries during ingestion. |
| **Config and errors** | **lib/provider.py**, **app** | Missing API key raises `RuntimeError` with a clear message. App catches and shows user-facing error. Model lists and defaults from env (e.g. `LLM_MODELS_OPENAI`, `OLLAMA_MODEL`). |

### 4.2 Agent-style solutions

| Area | Artifact | What is done |
|------|----------|---------------|
| **Orchestrator** | **lib/agents.py** | `route_query(query)` returns list of specialists from keywords. `run_orchestrator(query, retrieval_fn, location_fn, calculator_fn)` invokes each, aggregates context and tool_calls, returns A2UI directives. Used in app.py when “Use Phase 4 agents” is enabled. |
| **Specialists as tools** | **app.py** | retrieval_fn (vector or hybrid), location_fn (nearby_places), calculator_fn (pointer to tab). Each returns (context_str, tool_calls). Orchestrator aggregates and LLM gets combined context. |
| **Tool-calling agent** | **app_RAG_ollama_langchain.py** | LangChain `create_tool_calling_agent` + `AgentExecutor`; tool = retrieve (Qdrant). Agent can `invoke` or `stream`; UI streams agent output. Demonstrates LLM-driven tool selection. |
| **Tools Used and Sources** | **app.py** | Every chat turn shows “Tools Used” (vector_search, hybrid_retrieve, tavily_search, or agent names) and expandable “Sources” (retrieved chunks). A2UI directives (show_calculator, show_map) from orchestrator are rendered in the UI. |
| **MCP-style registry** | **lib/mcp_client.py** | Tool registry for agent-invokable tools; can be extended with more tools or MCP servers. |
| **Web search as tool** | **app.py** | Optional Tavily search augments context; results and tool call appear in Tools Used and in the answer. |

### 4.3 Summary table: experience demonstrated

| Experience | Evidence in repo |
|-------------|------------------|
| **Calling a Gen AI chat API** | OpenAI/OpenRouter via `client.chat.completions.create`; Ollama via `POST /api/chat`. |
| **Streaming responses** | All chat paths support streaming and update the UI incrementally. |
| **Using an embeddings API** | Same client for ingest and query; OpenAI/OpenRouter; optional Ollama embeddings in LangChain app. |
| **Multi-provider support** | Single code path for OpenAI and OpenRouter (base URL + key); separate path for Ollama; provider/model selection in UI. |
| **Orchestrator + specialists** | lib/agents.py + app.py integration; routing, invocation, aggregation. |
| **LLM-driven tool use** | LangChain AgentExecutor with tool-calling in app_RAG_ollama_langchain.py. |
| **Tools Used and citations** | Visible in UI; tool_calls and sources per turn. |
| **Config from env** | All API keys and URLs from .env; no hardcoded secrets. |

---

## 5. Plan to extend or deepen experience (no code run)

### 5.1 Optional extensions (document only)

- **More providers:** Add Azure OpenAI (another base URL + key) to `lib/provider.py` and sidebar; document in this file and in API.md. See azure_platform_plan for Azure OpenAI.
- **Function/tool calling from API:** Use the provider’s native tool/function-calling (e.g. OpenAI `tools` parameter) so the model returns structured tool calls and the app executes them; would unify with the existing “Tools Used” display. Document as an alternative to the current “pre-call retrieval then single LLM call” flow.
- **LangGraph:** Add a graph-based orchestration option (router → specialists → aggregate) as in [agentic_frameworks_langgraph_plan.md](agentic_frameworks_langgraph_plan.md); keeps the same external behavior (context, tool_calls, A2UI) while demonstrating graph-based agent design.
- **Structured output:** Use provider-specific structured output (e.g. JSON mode or response format) for A2UI directives or tool-call parsing so the app gets a consistent shape from the LLM without ad-hoc parsing.

### 5.2 Documentation updates (plan)

- **This file:** Keep as the single “Gen AI APIs and agents” experience doc; link from README or docs/EXECUTION_SUMMARY under “Hands-on experience.”
- **docs/API.md:** Ensure “Provider” and “Agents” sections reference this file for high-level usage and multi-provider/agent patterns.
- **README:** One line under features: “Multi-provider Gen AI (OpenAI, OpenRouter, Ollama), streaming chat and embeddings; orchestrator and optional LangChain tool-calling agent.”

### 5.3 Implementation order (if implementing extensions)

1. Document only: finalize this file and add README/API.md links.
2. Optional: add Azure OpenAI to provider and sidebar; document.
3. Optional: implement native tool/function-calling with one provider and display in Tools Used.
4. Optional: add LangGraph-based orchestrator path per agentic_frameworks_langgraph_plan.

---

## 6. References

- [lib/provider.py](lib/provider.py) – LLM and embedding client; multi-provider.
- [lib/agents.py](lib/agents.py) – Orchestrator and specialists.
- [app.py](app.py) – Main app; streaming chat, RAG, agents, Tools Used, Sources.
- [app_RAG_ollama_langchain.py](app_RAG_ollama_langchain.py) – LangChain tool-calling agent.
- [agentic_frameworks_langgraph_plan.md](agentic_frameworks_langgraph_plan.md) – LangGraph and workflow orchestration.
- [docs/API.md](docs/API.md) – API and tools reference.

---

*This document is a plan and documentation only; no code has been run or modified as part of this file.*
