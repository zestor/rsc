# mypy: ignore-errors
# ruff: noqa
"""Finance citation helpers shared by AGI and ASI.

``cite`` wraps values so formatted output includes ``[value](claim:N)``.
``save_citations`` writes workspace-root ``citations.jsonl`` and emits
changed claims via ``__asi_citations__`` on stderr.
"""

import json
import math
import os
import sys

CLAIM_TYPE = "claim"
CITATIONS_FILENAME = "citations.jsonl"
CITATIONS_MARKER_KEY = "__asi_citations__"
CITATIONS_MARKER_VERSION = 1
WORKSPACE_ROOT = "/home/user/workspace"

_COUNTER = 0
_registry: dict[int, dict] = {}
_name_to_id: dict[str, int] = {}
_dirty_ids: set[int] = set()


def _resolve_csv_file(file, metadata_s3_key):
    match file:
        case {"filename": filename, "metadata_s3_key": csv_metadata_s3_key}:
            return filename, csv_metadata_s3_key or metadata_s3_key
        case {"filename": filename}:
            return filename, metadata_s3_key
        case _:
            return file, metadata_s3_key


def _compact_entry(entry):
    return {k: v for k, v in entry.items() if v is not None}


def _citations_path(path=None):
    requested_path = CITATIONS_FILENAME if path is None else os.fspath(path)
    if os.path.isabs(requested_path):
        return requested_path
    return os.path.join(WORKSPACE_ROOT, requested_path)


class CitedValue(float):
    """A float that remembers its citation ID.

    Participates in arithmetic normally. When formatted or printed,
    emits [value](claim:N) markers for downstream rendering.
    """

    def __new__(cls, value, citation_id):
        instance = super().__new__(cls, value)
        instance.citation_id = citation_id
        return instance

    def _display(self):
        return int(self) if self.is_integer() else float(self)

    def __format__(self, format_spec):
        formatted = format(float(self), format_spec) if format_spec else str(self._display())  # fmt: skip
        return f"[{formatted}]({CLAIM_TYPE}:{self.citation_id})"

    def __str__(self):
        return f"[{self._display()}]({CLAIM_TYPE}:{self.citation_id})"

    def __repr__(self):
        return f"[{self._display()!r}]({CLAIM_TYPE}:{self.citation_id})"

    def _wrap(self, result):
        if isinstance(result, (int, float)) and not isinstance(result, CitedValue):
            return CitedValue(result, self.citation_id)
        return result

    def __add__(self, other):
        return self._wrap(float.__add__(self, other))

    def __radd__(self, other):
        return self._wrap(float.__radd__(self, other))

    def __sub__(self, other):
        return self._wrap(float.__sub__(self, other))

    def __rsub__(self, other):
        return self._wrap(float.__rsub__(self, other))

    def __mul__(self, other):
        return self._wrap(float.__mul__(self, other))

    def __rmul__(self, other):
        return self._wrap(float.__rmul__(self, other))

    def __truediv__(self, other):
        return self._wrap(float.__truediv__(self, other))

    def __rtruediv__(self, other):
        return self._wrap(float.__rtruediv__(self, other))

    def __floordiv__(self, other):
        return self._wrap(float.__floordiv__(self, other))

    def __rfloordiv__(self, other):
        return self._wrap(float.__rfloordiv__(self, other))

    def __mod__(self, other):
        return self._wrap(float.__mod__(self, other))

    def __neg__(self):
        return CitedValue(-float(self), self.citation_id)

    def __abs__(self):
        return CitedValue(abs(float(self)), self.citation_id)

    def __round__(self, ndigits=None):
        return CitedValue(round(float(self), ndigits), self.citation_id)


class CitedStr(str):
    """A str that remembers its citation ID.

    Participates in string operations normally. When formatted or printed,
    emits [value](claim:N) markers for downstream rendering.
    """

    def __new__(cls, value, citation_id):
        instance = super().__new__(cls, value)
        instance.citation_id = citation_id
        return instance

    def __format__(self, format_spec):
        formatted = format(str.__str__(self), format_spec)
        return f"[{formatted}]({CLAIM_TYPE}:{self.citation_id})"

    def __str__(self):
        return f"[{str.__str__(self)}]({CLAIM_TYPE}:{self.citation_id})"

    def __repr__(self):
        return f"[{str.__str__(self)!r}]({CLAIM_TYPE}:{self.citation_id})"


def init(prior_max_id=0, prior_registry=None):
    """Initialize or restore citation state.

    Called by AGI's executor to carry state across multiple code executions
    within a single turn. ASI does not need to call this — the module
    initializes with clean state on import.

    Args:
        prior_max_id: Highest citation ID from previous executions.
        prior_registry: Registry dict from previous executions to restore.
    """
    global _COUNTER, _registry, _name_to_id, _dirty_ids
    _COUNTER = prior_max_id
    _registry = dict(prior_registry or {})
    _name_to_id = {entry["name"]: cid for cid, entry in _registry.items()}
    _dirty_ids = set()


def cite(
    value,
    name,
    *,
    source=None,
    formula=None,
    derived_from=None,
    file=None,
    row_key=None,
    col=None,
    metadata_s3_key=None,
    url=None,
    source_url=None,
):
    """Cite a value with provenance metadata.

    The `name` argument is shown directly in the UI — use human-readable
    labels like "AAPL FY2024 Revenue", not snake_case identifiers.

    For source values (directly from a finance tool CSV):
        cite(value, "AAPL FY2024 Revenue", source="finance_company_financials", file=csv_file, row_key="2024-Q4", col="income_statement_total_revenues")
        cite(45_000.00, "AAPL Position Value", source="portfolio_holdings", file=csv_file, row_key="AAPL", col="Value")

    For derived values (computed from other cited values):
        cite(value, "AAPL FY2024 Net Margin", formula="net_income / revenue * 100", derived_from=["AAPL FY2024 Net Income", "AAPL FY2024 Revenue"])

    Returns a CitedValue (float) or CitedStr (str) that behaves identically
    to the original value in arithmetic and string operations. When printed
    or formatted, emits [value](claim:N) markers.
    """
    global _COUNTER

    if name in _name_to_id:
        cid = _name_to_id[name]
    else:
        _COUNTER += 1
        cid = _COUNTER

    try:
        coerced = float(value)
        if math.isfinite(coerced):
            cited = CitedValue(coerced, cid)
        else:
            coerced = str(value)
            cited = CitedStr(coerced, cid)
    except (ValueError, TypeError):
        coerced = str(value)
        cited = CitedStr(coerced, cid)

    parent_ids = None
    if derived_from:
        parent_ids = [_name_to_id[n] for n in derived_from if n in _name_to_id]

    resolved_file, resolved_metadata_s3_key = _resolve_csv_file(file, metadata_s3_key)
    entry = {
        "id": cid,
        "name": name,
        "value": coerced,
        "source": source,
        "formula": formula,
        "derived_from": parent_ids,
        "file": resolved_file,
        "row_key": str(row_key) if row_key is not None else None,
        "col": col,
        "metadata_s3_key": resolved_metadata_s3_key,
        "url": url,
        "source_url": source_url,
    }
    if _compact_entry(_registry.get(cid, {})) != _compact_entry(entry):
        _dirty_ids.add(cid)
    _registry[cid] = entry
    _name_to_id[name] = cid
    return cited


def get_registry():
    """Return the current citation registry as a dict of {id: entry}."""
    return dict(_registry)


def _emit_citations_marker(entries):
    if not entries:
        return
    marker = {
        CITATIONS_MARKER_KEY: {
            "version": CITATIONS_MARKER_VERSION,
            "claims": entries,
        }
    }
    print(json.dumps(marker, separators=(",", ":")), file=sys.stderr, flush=True)


def save_citations(path="citations.jsonl"):
    """Write the citation registry to JSONL and emit changed claims."""
    citations_path = _citations_path(path)
    lines = [json.dumps(_compact_entry(entry)) for entry in _registry.values()]
    with open(citations_path, "w", encoding="utf-8") as f:
        if lines:
            f.write("\n".join(lines) + "\n")
    changed_entries = [
        _compact_entry(_registry[cid]) for cid in sorted(_dirty_ids) if cid in _registry
    ]
    _emit_citations_marker(changed_entries)
    _dirty_ids.clear()


def load_citations(path="citations.jsonl"):
    """Load a previously saved citation registry, merging into current state."""
    global _COUNTER
    citations_path = _citations_path(path)
    try:
        with open(citations_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # lint-fixme: CheckUseOrjsonLoads: template is stdlib-only
                entry = json.loads(line)
                cid = entry["id"]
                _registry[cid] = entry
                _name_to_id[entry["name"]] = cid
                _COUNTER = max(_COUNTER, cid)
    except FileNotFoundError:
        pass
