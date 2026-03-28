# How to use AI agent skills (memory, context, retrieval, orchestration) in this project

**Purpose:** Connect your experience building **agents**—**memory, context engineering, retrieval, orchestration**—to concrete modules and extension points in **expat-nl-mortgage-rag**.

**Related:** [langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md](langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md), [codedocs/agentic_frameworks_langgraph_plan.md](../codedocs/agentic_frameworks_langgraph_plan.md), [plan-ml-realtime-deployment.md](plan-ml-realtime-deployment.md).

---

## 1. Quick map: skill → codebase

| Skill | Where it shows up now | Extension idea |
|-------|----------------------|----------------|
| **Retrieval** | `lib/retrieval.py`, `scripts/ingest_docs.py`, Qdrant | Tune hybrid weights; add reranker; query rewriting node |
| **Context engineering** | Chunking in `lib/chunking.py`, citation assembly in `app.py` / response path | System prompts as versioned templates; compress long context |
| **Orchestration** | `lib/agents.py` (`route_query`, `run_orchestrator`); LangGraph in `lib/agents_graph.py` (if enabled) | Explicit graph: router → specialists → merge; retries and fallbacks |
| **Memory** | Streamlit `st.session_state` chat history | Long-term memory store (summary + vector id); optional LangGraph checkpointing |
| **Tools** | Calculator, location, KG hooks, MCP (`lib/mcp_client.py`) | New tools as thin adapters with schemas; guardrails on outputs |
| **UI directives** | `lib/a2ui.py` | Structured agent output for richer UI |

---

## 2. Retrieval (your strongest overlap)

You already have **hybrid search and RRF**—classic “agentic RAG” foundation.

**Ways to deepen the story:**

- **Pre-retrieval:** Query expansion, HyDE-style synthetic query, language detection for expat queries.
- **Post-retrieval:** Rerank, dedupe by `doc_id`, max marginal relevance–style diversity.
- **Grounding contract:** Enforce “must cite chunk ids” in the agent policy; log violations for eval.

---

## 3. Context engineering

- **Prompt layers:** System (role + safety), user message, retrieved chunks, optional tool results—document token budgets per layer.
- **Conversation window:** Sliding window vs summarize-old-turns; align with provider limits in `lib/provider.py`.
- **Negative instructions:** What the assistant must not do (not a substitute for professional mortgage advice).

---

## 4. Orchestration

- **Current pattern:** Keyword router + specialist calls in `lib/agents.py`.
- **LangGraph path:** State machine with explicit edges, easier to test per node and to add human-in-the-loop later.
- **Patterns to mention in interviews:** ReAct-style tool loops (if you add them), supervisor pattern, parallel retrieval + tool calls then merge.

---

## 5. Memory

| Type | Use case in this app |
|------|----------------------|
| **Short-term** | Last N turns in session; required for follow-up questions |
| **Long-term (optional)** | User preferences (language, region), saved scenarios—store with consent and redaction |
| **Working memory** | “Scratchpad” in graph state for multi-step reasoning (if you add planning) |

**Implementation note (future):** Persist summaries to a small DB or KV; never store secrets in memory blobs.

---

## 6. Observability for agents

- Trace: `trace_id`, node name, tool name, latency per node (Langfuse already optional in `lib/provider.py`).
- Compare **orchestrator paths** in metrics: how often calculator vs RAG vs location wins the route.

---

## 7. Elevator pitch (skills → this project)

> I built a retrieval-first agent for expat mortgage Q&A: hybrid vector + lexical retrieval, strict citation context, and an orchestrator that routes to RAG, location, and calculator tools. I’m extending that with LangGraph for explicit state and checkpoints, and I treat prompts and retrieval parameters as versioned artifacts with eval and drift monitoring.

---

## 8. Reading order in the repo

1. `lib/retrieval.py` and `lib/chunking.py`
2. `lib/agents.py` then `lib/agents_graph.py` (if present on your branch)
3. `app.py` Phase 4 / agent toggle sections
4. `codedocs/agentic_frameworks_langgraph_plan.md`
