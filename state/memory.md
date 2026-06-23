# Memory State
Last updated: 2026-06-23T11:03:42.715467+00:00

## Compressed History


## Distilled Rules
- When asked to explain a tool or service, focus on its core function, target users, and primary use cases in a single concise paragraph.
- For technical tool explanations, mention the input it takes, the transformation it performs, and the output it provides to downstream applications.
- When a task specifies an exact output format (heading style, list type, count range), match that format precisely on the first attempt rather than improvising structure.
- For planning tasks that require breaking down complex or multi-topic requests, ensure each sub-task is independently researchable and covers a distinct facet of the original request.
- When a user question bundles multiple interconnected sub-topics (e.g., lineage, flood, hybrids, messiah), structure the answer to address each component explicitly while showing the narrative thread that connects them.
- When synthesizing research-grade answers on topics that blend ancient texts, theology, and speculative theories, clearly distinguish between canonical/scriptural sources, apocryphal traditions (e.g., Book of Enoch), and modern interpretive frameworks.
- When a question references specific named figures or lineages (e.g., Seth), verify and cite the textual tradition the reference originates from before building an argument on it.
- Base every claim on the provided search results or attachments and include explicit citations.
- Organize the answer into logical sections (e.g., background, analysis, implications) to improve readability and scholarly tone.
- When sources disagree, acknowledge the discrepancy and present the differing viewpoints without asserting unverified conclusions.
- Separate reasoning from the final JSON by placing the marker "---\nJSON OUTPUT:" on its own line before the JSON object.
- Ensure the JSON object conforms exactly to the required schema and contains no additional text or markdown after it.
- Keep any explanatory prose brief and before the marker, reserving the JSON for the structured answer.
- Provide the answer content directly; do not output meta‑planning or synthesis outlines unless the prompt explicitly requests them.
- Structure the response with brief plain‑prose reasoning, followed by a line containing exactly "---\nJSON OUTPUT:" and then a single, parsable JSON object with no additional text after the JSON.
- Ensure the JSON object conforms to the expected schema (e.g., required field names) and is valid JSON that can be parsed by json.loads.

## Ongoing Context


## History Summary


## Recent Failures
- Malformed evaluator response: ```json
{
  "passed": true,
  "score": 1.0,
  "per_criterion": {
    "complete": true,
    "correct": true
  },
  "critique": "",
  "root_causes": "",
  "suggested_fix": ""
}
```
- Malformed evaluator response: ```json
{
  "passed": true,
  "score": 1.0,
  "per_criterion": {
    "complete": true,
    "correct": true
  },
  "critique": "",
  "root_causes": "",
  "suggested_fix": ""
}
```
- Malformed evaluator response: ```json
{
  "passed": true,
  "score": 1.0,
  "per_criterion": {
    "complete": true,
    "correct": true
  },
  "critique": "",
  "root_causes": "",
  "suggested_fix": ""
}
```
- The submitted output is a research‑grade synthesis plan rather than the requested explanation. It outlines how to gather sources and structure an answer but does not actually explain non‑human intelligence modification of humanity, hybrids, the flood, or a messianic figure linked to Seth and fathered by non‑human intelligence. Consequently, the answer does not satisfy the task and lacks the substantive content needed for correctness.
- Malformed evaluator response: 
