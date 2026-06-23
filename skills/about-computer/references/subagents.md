# Parallel Subagent Orchestration

Computer can spawn specialized subagents that work simultaneously, then synthesize their results.

## How it works

- Each subagent gets its own tools and context window.
- Subagents share a workspace filesystem — they can read and write files that other agents (and the parent) can access.
- The parent agent validates and synthesizes results before presenting them to the user.
- Subagents don't pollute the main conversation's context, preventing the quality degradation that comes from overloaded context windows.

Subagents can be powered by different LLM models depending on task complexity and cost requirements. Consult the model-catalog skill for available models and selection guidance.

## Types of parallel work

**Research parallelism** — Split a large research task across multiple agents. Each researches independently (e.g., one per company, one per region, one per topic) and saves findings to workspace files.

**Batch processing** — Process hundreds of entities in parallel with structured output collected into CSV. Two specialized modes handle this at scale:

- Batch web research across many entities (e.g., "research funding data for 100 companies").
- Batch browser automation across many URLs (e.g., "extract pricing from 50 competitor sites").

**Asset parallelism** — Generate multiple documents, slides, or reports concurrently. Each subagent produces one deliverable following the same quality standards.

**Sequential chaining** — Subagents can be chained: one collects data and saves to a file, the next reads that file and builds on it.

## Example use cases

- Research 20 companies in parallel — each subagent handles one company, all results collected into a single CSV.
- Generate 10 personalized outreach emails simultaneously.
- Process a large dataset by splitting it across agents and combining results.
- Run deep research on multiple aspects of a topic (financials, competitors, market trends) in parallel.
