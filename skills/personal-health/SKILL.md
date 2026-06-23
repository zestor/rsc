# Personal Health Tools

Health tools fetch data from connected wearable devices and healthcare providers via the
connector service: `list_external_tools(queries=["health_"])`.

## Available Health Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `health_wearables_data` | Fetch wearable data (activity, sleep, vitals, nutrition) from connected devices | Sleep analysis, workout stats, heart rate trends, step counts, calorie tracking |
| `health_ehr_data` | Fetch electronic health records (medications, conditions, labs, procedures) | Lab results, medication lists, medical conditions, allergies, immunization records |

## Execution Pattern

Health data tools are called via `call_external_tool` with `source_id="health"`.
You **must** call `describe_external_tools` before `call_external_tool` — the system enforces this.

```python
# 1. Discover health tools
await list_external_tools(queries=["health_"])

# 2. Get input schemas (required before calling)
await describe_external_tools(source_id="health", tool_names=["health_wearables_data"])

# 3. Call health data tools with source_id="health"
await call_external_tool(tool_name="<tool_name>", source_id="health", arguments={...})
```

## Apple Health on iOS

On iOS Computer sessions only, Apple Health is available as a clientside external
connector. Use `source_id="apple_healthkit"` with the standard external connector
tools:

```python
# 1. Discover the iOS-local Apple Health connector
await list_external_tools(queries=["apple_healthkit"])

# 2. Get the HealthKit query schema
await describe_external_tools(
    source_id="apple_healthkit",
    tool_names=["query_apple_healthkit"],
)

# 3. Query on-device HealthKit data
await call_external_tool(
    tool_name="query_apple_healthkit",
    source_id="apple_healthkit",
    arguments={"health_types": [{"type": "Step Count", "duration": "1_week", "interval": "1_day"}]},
)
```

## Authentication Required

Health tools require authenticated connections to data providers. Use the **specific** connect
source for the data type you need — do not use the generic `source_id="health"` for connect calls:

- **Wearables** (activity, sleep, vitals, nutrition): `call_external_tool(tool_name="connect", source_id="wearables", arguments={})`
- **Medical records** (medications, conditions, labs): `call_external_tool(tool_name="connect", source_id="medical_records", arguments={})`
- **Function Health** (lab results, clinician notes): `call_external_tool(tool_name="connect", source_id="function_health", arguments={})`
- **Apple Health** (iOS-local health permissions): `call_external_tool(tool_name="connect", source_id="apple_healthkit", arguments={})`

## Gotchas

❌ `call_external_tool(tool_name="connect", source_id="health", arguments={})`

❌ `call_external_tool(tool_name="query_apple_healthkit", source_id="apple_healthkit", ...)` on non-iOS sessions — `apple_healthkit` is only routable from `ios` sessions; use `health_wearables_data` with `source_id="health"` for wearables data elsewhere.

## Sub-Skills

- **wearables-data** — Wearable device data (activity, sleep, vitals, nutrition)
- **electronic-health-records** — Electronic health records (medications, conditions, labs)