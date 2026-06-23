"""Deterministic renderer for the Talent Pool preview UI.

Same `TalentPoolBundle` JSON input → byte-identical output bundle.
Stdlib-only. No backend, no API client, no LLM string-insertion into HTML.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from schemas import (
    SCHEMA_VERSION,
    TIER_LABELS,
    TIER_ORDER,
    Candidate,
    CompanySnapshot,
    Methodology,
    MethodologySignal,
    Run,
    Signal,
    Source,
    TalentPoolBundle,
    TierThresholds,
    WorkflowSettings,
)

__all__ = (
    "load_bundle",
    "normalize_bundle",
    "render_bundle",
    "safe_profile_url",
    "assign_tier",
    "dedupe_headline_against_position",
)

SKILL_DIR = Path(__file__).parent
TEMPLATES_DIR = SKILL_DIR / "templates"
SHARED_DIR = SKILL_DIR.parent / "shared" / "ui"

HTML_TEMPLATE = TEMPLATES_DIR / "talent_pool_app.html"
CSS_TEMPLATE = TEMPLATES_DIR / "talent_pool_app.css"
JS_TEMPLATE = TEMPLATES_DIR / "talent_pool_app.js"
TOKENS_CSS = SHARED_DIR / "tokens.css"

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://(?:[^\s()]|\([^\s()]*\))+)\)")


def safe_profile_url(url: str) -> str:
    """Return the URL if scheme is http/https, else empty string."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return ""
    if not parts.netloc:
        return ""
    return url.strip()


def _safe_href(url: str) -> str:
    return safe_profile_url(url)


def _render_inline_markdown_links(text: str) -> str:
    """Escape text, preserving safe markdown links as clickable anchors."""

    if not text:
        return ""
    parts: list[str] = []
    last = 0
    for match in _MARKDOWN_LINK_RE.finditer(text):
        title, url = match.group(1), match.group(2)
        parts.append(escape(text[last : match.start()]))
        href = _safe_href(url)
        if href:
            parts.append(
                f'<a href="{escape(href, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{escape(title)}</a>'
            )
        else:
            parts.append(escape(title))
        last = match.end()
    parts.append(escape(text[last:]))
    return "".join(parts)


def assign_tier(score: float, thresholds: TierThresholds) -> str:
    if score >= thresholds.hot:
        return "hot"
    if score >= thresholds.warm:
        return "warm"
    if score >= thresholds.watch:
        return "watch"
    return "cold"


def dedupe_headline_against_position(
    headline: str, current_title: str, current_company: str
) -> str:
    """Drop headline if its tokens are a subset of "{title} {company}"."""
    if not headline:
        return ""
    position = f"{current_title} {current_company}".lower()
    if not position.strip():
        return headline
    headline_tokens = {t for t in headline.lower().split() if t.isalnum()}
    position_tokens = {t for t in position.split() if t.isalnum()}
    if headline_tokens and headline_tokens.issubset(position_tokens):
        return ""
    return headline


def _normalize_source(raw: dict) -> Source:
    url = _safe_href(str(raw.get("url", "")))
    title = str(raw.get("title", "") or url)
    return Source(title=title, url=url)


def _normalize_signal(raw: dict) -> Signal:
    sources = tuple(
        s
        for s in (
            _normalize_source(source)
            for source in raw.get("sources", raw.get("citations", ()))
        )
        if s.url
    )
    return Signal(
        name=str(raw.get("name", raw.get("label", ""))),
        weight=float(raw.get("weight", 0.0)),
        score=float(raw.get("score", 0.0)),
        rationale=str(raw.get("rationale", "")),
        weighted_contribution=float(raw.get("weighted_contribution", 0.0)),
        sources=sources,
    )


def _normalize_candidate(raw: dict, thresholds: TierThresholds) -> Candidate:
    signals = tuple(_normalize_signal(s) for s in raw.get("signals", ()))
    final_score = float(raw.get("final_score", 0.0))
    tier = str(raw.get("tier") or assign_tier(final_score, thresholds)).lower()
    if tier not in TIER_LABELS:
        tier = assign_tier(final_score, thresholds)
    headline = dedupe_headline_against_position(
        str(raw.get("headline", "")),
        str(raw.get("current_title", "")),
        str(raw.get("current_company", "")),
    )
    return Candidate(
        candidate_id=str(raw["candidate_id"]),
        full_name=str(raw.get("full_name", "")),
        headline=headline,
        current_title=str(raw.get("current_title", "")),
        current_company=str(raw.get("current_company", "")),
        location=str(raw.get("location", "")),
        profile_url=safe_profile_url(str(raw.get("profile_url", ""))),
        final_score=final_score,
        tier=tier,
        signals=signals,
        tags=tuple(str(t) for t in raw.get("tags", ())),
        found_run_id=str(raw.get("found_run_id", "")),
    )


def _normalize_run(raw: dict) -> Run:
    return Run(
        run_id=str(raw["run_id"]),
        started_at=str(raw.get("started_at", "")),
        finished_at=str(raw.get("finished_at", "")),
        label=str(raw.get("label", "")),
        notes=str(raw.get("notes", "")),
    )


def _normalize_company(raw: dict) -> CompanySnapshot:
    sources = tuple(
        s
        for s in (
            _normalize_source(source)
            for source in raw.get("sources", raw.get("citations", ()))
        )
        if s.url
    )
    return CompanySnapshot(
        name=str(raw.get("name", "")),
        slug=str(raw.get("slug", "")),
        stability=str(raw.get("stability", "")),
        summary=str(raw.get("summary", "")),
        sources=sources,
    )


def _normalize_methodology_signal(raw: dict) -> MethodologySignal:
    return MethodologySignal(
        key=str(raw.get("key", "")),
        label=str(raw.get("label", raw.get("name", ""))),
        weight=float(raw.get("weight", 0.0)),
        direction=str(raw.get("direction", "")),
    )


def _normalize_methodology(raw: dict) -> Methodology:
    return Methodology(
        formula=str(raw.get("formula", "")),
        total_weight=float(raw.get("total_weight", 0.0)),
        tier_cutoffs={
            str(key): str(value) for key, value in raw.get("tier_cutoffs", {}).items()
        },
        signals=tuple(
            _normalize_methodology_signal(signal) for signal in raw.get("signals", ())
        ),
    )


def _normalize_workflow(raw: dict) -> WorkflowSettings:
    return WorkflowSettings(
        role_label=str(raw.get("role_label", "")),
        role_subtitle=str(raw.get("role_subtitle", "")),
        cadence_label=str(raw.get("cadence_label", "Manual only")),
        last_refreshed_at=str(raw.get("last_refreshed_at", "")),
    )


def _normalize_thresholds(raw: dict) -> TierThresholds:
    defaults = TierThresholds()
    return TierThresholds(
        hot=float(raw.get("hot", defaults.hot)),
        warm=float(raw.get("warm", defaults.warm)),
        watch=float(raw.get("watch", defaults.watch)),
    )


def normalize_bundle(raw: dict) -> TalentPoolBundle:
    thresholds = _normalize_thresholds(raw.get("tier_thresholds", {}))
    workflow = _normalize_workflow(raw.get("workflow", {}))
    runs = tuple(_normalize_run(r) for r in raw.get("runs", ()))
    companies = tuple(_normalize_company(c) for c in raw.get("companies", ()))
    methodology = _normalize_methodology(raw.get("methodology", {}))
    candidates = tuple(
        _normalize_candidate(c, thresholds) for c in raw.get("candidates", ())
    )
    sorted_candidates = tuple(
        sorted(
            candidates,
            key=lambda c: (TIER_ORDER.index(c.tier), -c.final_score, c.full_name),
        )
    )
    return TalentPoolBundle(
        schema_version=str(raw.get("schema_version", SCHEMA_VERSION)),
        workflow=workflow,
        tier_thresholds=thresholds,
        runs=runs,
        candidates=sorted_candidates,
        companies=companies,
        methodology=methodology,
    )


def load_bundle(path: Path) -> TalentPoolBundle:
    return normalize_bundle(json.loads(path.read_text(encoding="utf-8")))


def _bundle_to_json(bundle: TalentPoolBundle) -> str:
    payload = {
        "schema_version": bundle.schema_version,
        "workflow": asdict(bundle.workflow),
        "tier_thresholds": asdict(bundle.tier_thresholds),
        "runs": [asdict(r) for r in bundle.runs],
        "candidates": [
            {
                **asdict(c),
                "signals": [asdict(s) for s in c.signals],
                "tags": list(c.tags),
            }
            for c in bundle.candidates
        ],
        "companies": [asdict(c) for c in bundle.companies],
        "methodology": asdict(bundle.methodology),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _tier_counts(bundle: TalentPoolBundle) -> dict[str, int]:
    counts = {tier: 0 for tier in TIER_ORDER}
    for c in bundle.candidates:
        counts[c.tier] = counts.get(c.tier, 0) + 1
    return counts


def _render_tier_summary(bundle: TalentPoolBundle) -> str:
    counts = _tier_counts(bundle)
    cells = [
        f'<div class="tier-card tier-{escape(tier)}">'
        f'<div class="tier-label">{escape(TIER_LABELS[tier])}</div>'
        f'<div class="tier-count">{counts[tier]}</div>'
        f"</div>"
        for tier in TIER_ORDER
    ]
    return "".join(cells)


def _render_score_dial(score: float, tier: str, size: int = 80) -> str:
    radius = (size - 8) / 2
    circumference = 2 * 3.141592653589793 * radius
    pct = max(0.0, min(score, 100.0)) / 100.0
    dash = circumference * pct
    return (
        f'<span class="score-dial tier-{escape(tier)}" '
        f'style="--dial-size: {size}px" aria-label="Score {score:.1f}">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">'
        f'<circle cx="{size / 2:g}" cy="{size / 2:g}" r="{radius:g}" '
        'class="score-dial-track"></circle>'
        f'<circle cx="{size / 2:g}" cy="{size / 2:g}" r="{radius:g}" '
        f'class="score-dial-value" stroke-dasharray="{dash:.2f} {circumference:.2f}">'
        "</circle>"
        "</svg>"
        '<span class="score-dial-label">'
        f"<strong>{score:.1f}</strong><em>score</em>"
        "</span>"
        "</span>"
    )


def _render_candidate_row(c: Candidate, rank: int) -> str:
    sub_parts = [c.current_title, c.current_company, c.location]
    sub = " · ".join(p for p in sub_parts if p)
    if c.profile_url:
        link_block = (
            f'<a class="candidate-link" href="{escape(c.profile_url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">LinkedIn</a>'
        )
    else:
        link_block = (
            '<span class="candidate-link candidate-link-disabled" '
            'aria-disabled="true">LinkedIn unavailable</span>'
        )
    detail_button = (
        '<button type="button" class="candidate-link candidate-open" '
        f'data-candidate-id="{escape(c.candidate_id, quote=True)}">Details</button>'
    )
    headline_text = escape(c.headline) if c.headline else "&nbsp;"
    headline_class = (
        "candidate-headline"
        if c.headline
        else "candidate-headline candidate-headline-empty"
    )
    headline_block = f'<span class="{headline_class}">{headline_text}</span>'
    return (
        f'<li class="candidate-row tier-{escape(c.tier)}" data-id="{escape(c.candidate_id, quote=True)}">'
        '<button type="button" class="candidate-row-button candidate-open" '
        f'data-candidate-id="{escape(c.candidate_id, quote=True)}" '
        f'aria-label="Open {escape(c.full_name, quote=True)} details">'
        '<span class="candidate-rank">'
        f"{rank:02d}"
        "</span>"
        f"{_render_score_dial(c.final_score, c.tier)}"
        '<span class="candidate-main">'
        '<span class="candidate-title-line">'
        f'<span class="candidate-name">{escape(c.full_name)}</span>'
        f'<span class="tier-pill tier-{escape(c.tier)}">{escape(TIER_LABELS[c.tier])}</span>'
        "</span>"
        f'<span class="candidate-sub">{escape(sub)}</span>'
        f"{headline_block}"
        "</span>"
        '<span class="candidate-arrow" aria-hidden="true">↗</span>'
        "</button>"
        '<div class="candidate-links">'
        f"{link_block}"
        f"{detail_button}"
        "</div>"
        "</li>"
    )


def _render_sources(sources: tuple[Source, ...]) -> str:
    if not sources:
        return ""
    links = "".join(
        f'<a href="{escape(source.url, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer">{escape(source.title)}</a>'
        for source in sources
    )
    return f'<div class="source-list">{links}</div>'


def _render_signal_card(signal: Signal) -> str:
    bar_width = max(0.0, min(signal.score, 10.0)) * 10
    contribution = (
        f"{signal.weighted_contribution:.1f}"
        if signal.weighted_contribution
        else f"{signal.score * signal.weight:.1f}"
    )
    return (
        '<article class="signal-card">'
        '<div class="signal-card-header">'
        f"<h4>{escape(signal.name or 'Signal')}</h4>"
        '<div class="signal-metrics">'
        f"<span>{signal.score:.0f}/10</span>"
        f"<span>× {signal.weight:g}</span>"
        f"<span>{contribution} weighted</span>"
        "</div>"
        "</div>"
        '<div class="signal-bar" aria-hidden="true">'
        f'<span style="width: {bar_width:.0f}%"></span>'
        "</div>"
        f'<p class="signal-rationale">{_render_inline_markdown_links(signal.rationale)}</p>'
        f"{_render_sources(signal.sources)}"
        "</article>"
    )


def _render_candidate_details(bundle: TalentPoolBundle) -> str:
    if not bundle.candidates:
        return ""
    panels = []
    for candidate in bundle.candidates:
        signal_cards = "".join(_render_signal_card(s) for s in candidate.signals)
        profile_link = (
            f'<a class="drawer-link" href="{escape(candidate.profile_url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">LinkedIn ↗</a>'
            if candidate.profile_url
            else ""
        )
        panels.append(
            f'<article class="candidate-detail-card tier-{escape(candidate.tier)}" '
            f'data-candidate-panel="{escape(candidate.candidate_id, quote=True)}" hidden>'
            '<div class="drawer-profile">'
            f"{_render_score_dial(candidate.final_score, candidate.tier, 104)}"
            '<div class="drawer-profile-main">'
            '<div class="drawer-title-line">'
            f"<h3>{escape(candidate.full_name)}</h3>"
            f'<span class="tier-pill tier-{escape(candidate.tier)}">{escape(TIER_LABELS[candidate.tier])}</span>'
            "</div>"
            f"<p>{escape(candidate.current_title or '—')} · "
            f"{escape(candidate.current_company or '—')}</p>"
            f'<p class="drawer-meta">{escape(candidate.location or "—")}</p>'
            f"{profile_link}"
            "</div>"
            "</div>"
            '<div class="drawer-section-note">'
            "All ten signals, each scored 0–10. Weighted contribution feeds the final score."
            "</div>"
            f'<div class="signal-grid">{signal_cards}</div>'
            "</article>"
        )
    return (
        '<div class="drawer-backdrop" data-candidate-close hidden></div>'
        '<aside id="candidate-details" class="candidate-drawer" role="dialog" '
        'aria-label="Candidate details" aria-modal="true" aria-hidden="true" hidden>'
        '<div class="drawer-topbar">'
        "<div><h2>Candidate details</h2>"
        "<p>Signal breakdown, citations, and scoring inputs.</p></div>"
        '<button type="button" class="drawer-close" data-candidate-close '
        'aria-label="Close candidate details">×</button>'
        "</div>"
        '<div class="drawer-panels">'
        f"{''.join(panels)}"
        "</div>"
        "</aside>"
    )


def _render_companies_section(bundle: TalentPoolBundle) -> str:
    if not bundle.companies:
        return ""
    cards = "".join(
        '<article class="company-card">'
        '<div class="company-card-header">'
        f"<h3>{escape(company.name)}</h3>"
        f"<span>{escape(company.stability or 'No stability label')}</span>"
        "</div>"
        f"<p>{_render_inline_markdown_links(company.summary)}</p>"
        f"{_render_sources(company.sources)}"
        "</article>"
        for company in bundle.companies
    )
    return (
        '<section id="companies" class="companies-section">'
        "<h2>Companies in scope</h2>"
        '<div class="companies-grid">'
        f"{cards}"
        "</div>"
        "</section>"
    )


def _render_methodology_section(bundle: TalentPoolBundle) -> str:
    methodology = bundle.methodology
    if not methodology.formula and not methodology.signals:
        return ""
    cutoff_order = ("hot", "warm", "watch", "cold")
    cutoff_items = sorted(
        methodology.tier_cutoffs.items(),
        key=lambda item: (
            cutoff_order.index(item[0].lower())
            if item[0].lower() in cutoff_order
            else len(cutoff_order),
            item[0].lower(),
        ),
    )
    cutoffs = "".join(
        f"<dt>{escape(tier)}</dt><dd>{escape(value)}</dd>"
        for tier, value in cutoff_items
    )
    signals = "".join(
        "<tr>"
        f"<td>{escape(signal.label)}</td>"
        f"<td>{signal.weight:g}</td>"
        f"<td>{escape(signal.direction)}</td>"
        "</tr>"
        for signal in methodology.signals
    )
    return (
        '<section id="methodology" class="methodology-section">'
        "<h2>Methodology</h2>"
        '<div class="methodology-grid">'
        '<article class="methodology-card methodology-card-formula">'
        "<h3>Formula</h3>"
        f"<p><code>{escape(methodology.formula or '—')}</code></p>"
        f"<dl><dt>Total weight</dt><dd>{methodology.total_weight:g}</dd>"
        f"{cutoffs}</dl>"
        "</article>"
        '<article class="methodology-card methodology-card-signals">'
        "<h3>Signal weights</h3>"
        '<div class="methodology-table-wrap">'
        '<table class="methodology-table">'
        "<thead><tr><th>Signal</th><th>Weight</th><th>Direction</th></tr></thead>"
        f"<tbody>{signals}</tbody>"
        "</table>"
        "</div>"
        "</article>"
        "</div>"
        "</section>"
    )


def _render_workflow_section(bundle: TalentPoolBundle) -> str:
    w = bundle.workflow
    t = bundle.tier_thresholds
    rows = "".join(
        f"<tr><td>{escape(r.run_id)}</td><td>{escape(r.label or r.started_at)}</td>"
        f"<td>{escape(r.notes)}</td></tr>"
        for r in bundle.runs
    )
    runs_table = (
        '<div class="runs-table-wrap">'
        f'<table class="runs-table"><thead><tr><th>Run</th><th>Started</th><th>Notes</th></tr>'
        f"</thead><tbody>{rows}</tbody></table>"
        "</div>"
        if rows
        else '<p class="muted">No runs recorded.</p>'
    )
    return (
        '<section id="workflow-data" class="workflow-section">'
        "<h2>Workflow data</h2>"
        '<div class="workflow-grid">'
        '<div class="workflow-card">'
        "<h3>Settings</h3>"
        f"<dl><dt>Role</dt><dd>{escape(w.role_label or '—')}</dd>"
        f"<dt>Cadence</dt><dd>{escape(w.cadence_label)}</dd>"
        f"<dt>Last refreshed</dt><dd>{escape(w.last_refreshed_at or '—')}</dd></dl>"
        "</div>"
        '<div class="workflow-card">'
        "<h3>Tier thresholds</h3>"
        f"<dl><dt>Hot ≥</dt><dd>{t.hot:.1f}</dd>"
        f"<dt>Warm ≥</dt><dd>{t.warm:.1f}</dd>"
        f"<dt>Watch ≥</dt><dd>{t.watch:.1f}</dd></dl>"
        "</div>"
        '<div class="workflow-card runs-card">'
        "<h3>Runs</h3>"
        f"{runs_table}"
        "</div>"
        "</div>"
        "</section>"
    )


def render_bundle(bundle: TalentPoolBundle, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_template = HTML_TEMPLATE.read_text(encoding="utf-8")
    css = CSS_TEMPLATE.read_text(encoding="utf-8")
    js = JS_TEMPLATE.read_text(encoding="utf-8")

    role_label = bundle.workflow.role_label or "Talent Pool"
    role_subtitle = bundle.workflow.role_subtitle or "Preview"
    candidate_rows = "".join(
        _render_candidate_row(c, rank)
        for rank, c in enumerate(bundle.candidates, start=1)
    )
    tier_summary = _render_tier_summary(bundle)
    extended_sections = "".join(
        (
            _render_candidate_details(bundle),
            _render_companies_section(bundle),
            _render_methodology_section(bundle),
            _render_workflow_section(bundle),
        )
    )
    bundle_json = _bundle_to_json(bundle)
    # Escape `</script` so user-provided candidate fields cannot break out of
    # the application/json script tag in the rendered preview.
    safe_bundle_json = bundle_json.replace("</", "<\\/")

    html = (
        html_template.replace("{{ROLE_LABEL}}", escape(role_label))
        .replace("{{ROLE_SUBTITLE}}", escape(role_subtitle))
        .replace("{{TIER_SUMMARY}}", tier_summary)
        .replace("{{CANDIDATE_ROWS}}", candidate_rows)
        .replace("{{WORKFLOW_SECTION}}", extended_sections)
        .replace("{{BUNDLE_JSON}}", safe_bundle_json)
    )

    paths: list[Path] = []
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    paths.append(output_dir / "index.html")
    (output_dir / "app.css").write_text(css, encoding="utf-8")
    paths.append(output_dir / "app.css")
    (output_dir / "app.js").write_text(js, encoding="utf-8")
    paths.append(output_dir / "app.js")
    shutil.copyfile(TOKENS_CSS, output_dir / "tokens.css")
    paths.append(output_dir / "tokens.css")
    (output_dir / "talent_pool_bundle.json").write_text(bundle_json, encoding="utf-8")
    paths.append(output_dir / "talent_pool_bundle.json")
    return paths


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    bundle = load_bundle(args.input)
    paths = render_bundle(bundle, args.output)
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
