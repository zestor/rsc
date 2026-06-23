# Text / Agent Models

Use the `model` parameter in `run_subagent` to select which LLM powers a subagent.

## claude_sonnet_4_6 (Claude Sonnet 4.6)

- Quality: ★★★★ | Speed: ★★★★★ | Cost: $$
- 200K context window

**Default for subagent types:** `general_purpose`, `research`

**When to use:**

- General research and information gathering
- Data processing and analysis
- Document drafting and editing
- Multi-step workflows that don't require top-tier reasoning
- Budget-conscious tasks where quality still matters

---

## claude_opus_4_8 (Claude Opus 4.8)

- Quality: ★★★★★ | Speed: ★★★ | Cost: $$$
- 200K context window

**Default for subagent types:** `asset`, `website_building`

**When to use:**

- Complex website building with multiple pages and interactions
- High-quality document creation (presentations, reports, forms)
- Tasks requiring deep reasoning and planning
- Creative work where quality is paramount
- User explicitly requests "best quality"
- Getting it right the first time saves iteration cost

---

## gemini_3_1_pro (Gemini 3.1 Pro)

- Quality: ★★★ | Speed: ★★★★ | Cost: $$
- 1M context window (5x larger than Claude models)

**When to use:**

- Budget-constrained research tasks
- Simple web research that doesn't require deep reasoning
- Gathering facts and information at scale

---

## gpt_5_4 (GPT 5.4)

- Quality: ★★★★★ | Speed: ★★★ | Cost: $$
- Strong at math, logic, and structured problem-solving

**When to use:**

- Tasks requiring strong logical or mathematical reasoning
- Complex data analysis with numerical precision
- Problems benefiting from step-by-step reasoning
- User explicitly requests an OpenAI model

---

## gpt_5_5 (GPT 5.5)

- Quality: ★★★★★ | Speed: ★★★ | Cost: $$$
- OpenAI's newest frontier model; successor to gpt_5_4 with stronger reasoning

**When to use:**

- Hardest reasoning and planning tasks where quality matters most
- User explicitly requests the newest OpenAI model
- Prefer over gpt_5_4 when top-tier reasoning justifies higher cost

---

## Default Models by Subagent Type

| Subagent Type      | Default Model      | Rationale                                |
| ------------------ | ------------------ | ---------------------------------------- |
| `general_purpose`  | claude_sonnet_4_6  | General-purpose balanced performance     |
| `research`         | claude_sonnet_4_6  | Good quality research at reasonable cost |
| `asset`            | claude_opus_4_8    | High quality for document creation       |
| `website_building` | claude_opus_4_8    | Complex reasoning for web development    |

## Selection Summary

| Scenario                            | Model                               |
| ----------------------------------- | ----------------------------------- |
| Website building                    | claude_opus_4_8                     |
| PDF/DOCX/PPTX/XLSX creation         | claude_opus_4_8                     |
| Deep reasoning, planning            | claude_opus_4_8                     |
| User wants "best quality"           | claude_opus_4_8                     |
| General research                    | claude_sonnet_4_6                   |
| Data processing                     | claude_sonnet_4_6                   |
| Budget constraints                  | claude_sonnet_4_6 or gemini_3_1_pro |
| Large-scale research on a budget    | gemini_3_1_pro                      |
| Math / logic / structured reasoning | gpt_5_4                             |
| Newest OpenAI frontier reasoning    | gpt_5_5                             |
| User requests a specific model      | use that model                      |
| Default / no preference             | depends on subagent_type            |
