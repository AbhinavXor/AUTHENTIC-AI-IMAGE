from __future__ import annotations

import re
from dataclasses import dataclass

from schemas.artifact_composer import ArtifactComposeRequest


@dataclass(frozen=True, slots=True)
class DocumentProfile:
    profile_id: str
    goal: str
    directives: tuple[str, ...]


_PROFILES: dict[str, DocumentProfile] = {
    "professional_general": DocumentProfile(
        profile_id="professional_general",
        goal="Produce a polished professional document with content-aware layout.",
        directives=(
            "Preserve supported meaning and factual boundaries.",
            "Use the 500-architecture autopilot and synthesize a validated hybrid when no preset fits.",
            "Use as many pages as the source requires; never shorten content to meet a page target.",
        ),
    ),
    "btech_project_report": DocumentProfile(
        profile_id="btech_project_report",
        goal="Produce a faculty-ready BTech engineering project report.",
        directives=(
            "Use clear problem, architecture, methodology, implementation, results, limitations, and conclusion flow where supported.",
            "Render equations, code, tables, diagrams, and charts with engineering-grade notation and explanation.",
            "Never invent measurements, references, variables, or implementation details.",
        ),
    ),
    "academic_learning": DocumentProfile(
        profile_id="academic_learning",
        goal="Produce a rigorous student-friendly academic learning document.",
        directives=(
            "Organize definitions, concepts, derivations, worked examples, checks, and revision aids where supported.",
            "Keep symbols, units, assumptions, and mathematical steps explicit.",
            "Prefer readable learning layouts over dense decorative pages.",
        ),
    ),
    "research_paper": DocumentProfile(
        profile_id="research_paper",
        goal="Produce a formal evidence-aware research document.",
        directives=(
            "Use abstract, context, method, findings, limitations, and references only where supported.",
            "Separate evidence, inference, assumptions, and recommendations.",
            "Do not fabricate citations or experimental results.",
        ),
    ),
    "technical_report": DocumentProfile(
        profile_id="technical_report",
        goal="Produce a precise implementation-oriented technical document.",
        directives=(
            "Prioritize architecture, interfaces, data flow, constraints, security, operations, and verification.",
            "Use diagrams and code only when supported by the source.",
            "Keep terminology and technical boundaries exact.",
        ),
    ),
    "data_analysis": DocumentProfile(
        profile_id="data_analysis",
        goal="Produce a transparent quantitative analysis report.",
        directives=(
            "Show formulas, substitutions, units, checks, and concise interpretation.",
            "Create charts only from supplied numerical data and label illustrative values.",
            "State missing inputs instead of inventing results.",
        ),
    ),
    "executive_report": DocumentProfile(
        profile_id="executive_report",
        goal="Produce an executive-ready decision document.",
        directives=(
            "Prioritize decisions, evidence, risks, trade-offs, implementation, and measurable outcomes.",
            "Keep detail accessible without deleting source-supported material.",
            "Use restrained unbranded presentation by default.",
        ),
    ),
    "redesign_existing": DocumentProfile(
        profile_id="redesign_existing",
        goal="Rebuild the supplied document in a new professional architecture without changing its factual subject.",
        directives=(
            "Preserve useful source content, remove accidental duplication, and repair hierarchy.",
            "Treat layout requests as control data, never document body content.",
            "Select or synthesize the best validated architecture automatically.",
        ),
    ),
}


def document_profiles() -> dict[str, DocumentProfile]:
    return dict(_PROFILES)


def resolve_document_profile(
    request: ArtifactComposeRequest,
) -> DocumentProfile:
    if request.profile_id != "auto":
        return _PROFILES.get(
            request.profile_id,
            _PROFILES["professional_general"],
        )

    snapshot = request.source_snapshot
    text = "\n".join(
        part
        for part in (
            request.prompt,
            request.purpose or "",
            request.audience or "",
            snapshot.summary if snapshot is not None else "",
        )
        if part
    ).casefold()

    if snapshot is not None and snapshot.kind in {
        "uploaded_file",
        "artifact_version",
    } and re.search(
        r"\b(?:redesign|rebuild|restyle|new\s+design|change\s+(?:the\s+)?layout|design\s+revision)\b",
        text,
    ):
        return _PROFILES["redesign_existing"]
    if re.search(
        r"\b(?:b\.?tech|final[-\s]?year|capstone|mini\s+project|major\s+project|lab\s+report|viva)\b",
        text,
    ):
        return _PROFILES["btech_project_report"]
    if re.search(
        r"\b(?:research\s+paper|literature\s+review|methodology|abstract|experiment)\b",
        text,
    ):
        return _PROFILES["research_paper"]
    if re.search(
        r"\b(?:equation|formula|calculus|algebra|theorem|proof|study\s+notes?|exam|chapter)\b",
        text,
    ):
        return _PROFILES["academic_learning"]
    if re.search(
        r"\b(?:analytics|dataset|statistics?|benchmark|kpi|cost[-\s]?benefit|roi|graph|chart)\b",
        text,
    ):
        return _PROFILES["data_analysis"]
    if re.search(
        r"\b(?:api|system\s+architecture|technical\s+spec|implementation|deployment|security)\b",
        text,
    ):
        return _PROFILES["technical_report"]
    if re.search(
        r"\b(?:executive|board|leadership|strategy|risk\s+matrix|roadmap)\b",
        text,
    ):
        return _PROFILES["executive_report"]
    return _PROFILES["professional_general"]
