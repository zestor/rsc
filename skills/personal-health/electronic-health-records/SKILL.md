# EHR Data Tool

Fetch electronic health records (medications, conditions, allergies, lab results, procedures, immunizations) from connected healthcare providers.

Use this when the user asks about:
- Medications, prescriptions
- Medical conditions, diagnoses
- Allergies
- Lab results, blood work
- Procedures, surgeries
- Immunization records
- Appointments
- Patient summary

## Example Call

```python
await call_external_tool(
    tool_name="health_ehr_data",
    source_id="health",
    arguments={"categories": ["medical_records", "vitals_and_labs"]}
)
```

## Authentication

If the user has not connected the relevant source, prompt them to connect the specific provider:

```python
# Medical records from healthcare providers
await call_external_tool(tool_name="connect", source_id="medical_records", arguments={})

# Function Health lab results and clinician notes
await call_external_tool(tool_name="connect", source_id="function_health", arguments={})
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `categories` | `list[str]` | Yes | - | Health data categories to fetch from electronic health records. |

**Valid values:**

**`categories`** (HealthDataCategory): `activity`, `sleep`, `vitals_and_labs`, `nutrition`, `menstruation`, `medical_records`, `patient_summary`

### Examples

**Current medications:**

```python
# Current medications
await call_external_tool(tool_name="health_ehr_data", source_id="health", arguments={
    "categories": ["medical_records"]
})
```

**Recent lab results:**

```python
# Recent lab results
await call_external_tool(tool_name="health_ehr_data", source_id="health", arguments={
    "categories": ["vitals_and_labs"]
})
```

**Medical records:**

```python
# Medical records
await call_external_tool(tool_name="health_ehr_data", source_id="health", arguments={
    "categories": ["medical_records", "vitals_and_labs"]
})
```