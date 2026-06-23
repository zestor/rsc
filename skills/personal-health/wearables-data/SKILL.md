# Wearables Data Tool

Fetch wearable health data (activity, sleep, vitals, nutrition, menstruation) from connected devices.

Use this when the user asks about:
- Sleep data, sleep quality, sleep duration
- Activity, steps, workouts, calories burned
- Heart rate, HRV, body metrics
- Nutrition tracking, calorie intake
- Menstruation cycle tracking

## Example Call

```python
await call_external_tool(
    tool_name="health_wearables_data",
    source_id="health",
    arguments={"categories": ["sleep", "activity"], "time_range_days": 7}
)
```

## Authentication

If the user has not connected a wearable device or wants to connect another, prompt them to connect:

```python
await call_external_tool(tool_name="connect", source_id="wearables", arguments={})
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `categories` | `list[str]` | Yes | - | Health data categories to fetch from wearable devices. |
| `time_range_days` | `int` | No | 7 | Number of days of historical data to fetch. Default 7 (one week), maximum 28 (four weeks). |

**Valid values:**

**`categories`** (HealthDataCategory): `activity`, `sleep`, `vitals_and_labs`, `nutrition`, `menstruation`, `medical_records`, `patient_summary`

### Examples

**Last week's sleep data:**

```python
# Last week's sleep data
await call_external_tool(tool_name="health_wearables_data", source_id="health", arguments={
    "categories": ["sleep"],
    "time_range_days": 7
})
```

**Monthly activity summary:**

```python
# Monthly activity summary
await call_external_tool(tool_name="health_wearables_data", source_id="health", arguments={
    "categories": ["activity"],
    "time_range_days": 28
})
```

**Complete wearable health snapshot:**

```python
# Complete wearable health snapshot
await call_external_tool(tool_name="health_wearables_data", source_id="health", arguments={
    "categories": ["activity", "sleep", "vitals_and_labs", "nutrition"],
    "time_range_days": 14
})
```

## Apple Health on iOS

On iOS Computer sessions, query Apple Health directly via the `apple_healthkit`
connector (see the parent `personal-health` skill for the full discover/describe/call
pattern). Sleep example:

```python
await call_external_tool(
    tool_name="query_apple_healthkit",
    source_id="apple_healthkit",
    arguments={"health_types": [{"type": "Sleep Analysis", "duration": "1_week"}]},
)
```