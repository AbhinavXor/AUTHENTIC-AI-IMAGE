from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from artifacts.composer import (
    ComposedArtifactDraft,
    CompositionProgressCallback,
    compose_artifact_draft,
    compose_artifact_revision,
    is_design_only_revision,
)
from artifacts.document_profiles import resolve_document_profile
from artifacts.contracts import ArtifactAnswerRouter
from artifacts.large_source import plan_large_source
from artifacts.layout_brief import apply_layout_brief
from artifacts.models import ArtifactLayoutBrief
from artifacts.parser import parse_artifact_document, sanitize_filename
from artifacts.planner import plan_artifact
from artifacts.source_fidelity import (
    SourceFidelityProfile,
    canonical_revision_title,
    infer_professional_title,
    is_canonical_artifact_markdown,
    normalize_recovered_artifact_markdown,
    resolve_source_fidelity,
    sanitize_recovered_source_payload,
    source_fidelity_metrics,
)
from artifacts.quality import (
    ArtifactQualityReport,
    inspect_rendered_file,
    normalize_document_structure,
    normalize_markdown_source,
    validate_document_quality,
)
from artifacts.repository import (
    ArtifactConflictError,
    ArtifactRepository,
    ArtifactView,
)
from artifacts.storage import ArtifactStorage
from artifacts.source_vault import ArtifactSourceVault
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import (
    ArtifactDuplicateRequest,
    ArtifactRevisionRequest,
    ArtifactSourceSnapshot,
)


@dataclass(frozen=True, slots=True)
class ArtifactCreationResult:
    view: ArtifactView
    quality: ArtifactQualityReport
    source_content: str
    provider: str | None
    model: str | None
    request_id: str | None
    draft_character_count: int


class ArtifactLifecycleService:
    """Application service for artifact creation and version operations."""

    def __init__(
        self,
        *,
        artifact_storage: ArtifactStorage,
        artifact_repository: ArtifactRepository,
        model_router: ArtifactAnswerRouter,
        source_vault: ArtifactSourceVault | None = None,
    ) -> None:
        self.artifact_storage = artifact_storage
        self.artifact_repository = artifact_repository
        self.model_router = model_router
        self.source_vault = source_vault

    def _hydrate_source_reference(
        self,
        request: ArtifactComposeRequest,
    ) -> ArtifactComposeRequest:
        reference = request.source_ref
        if reference is None:
            return request
        if self.source_vault is None:
            raise ValueError(
                "Durable artifact source storage is unavailable."
            )
        record = self.source_vault.get(reference)
        return request.model_copy(
            update={"source_snapshot": record.snapshot}
        )

    @staticmethod
    def _operation_fingerprint(
        action: str,
        payload: dict[str, Any],
    ) -> str:
        encoded = json.dumps(
            {
                "action": action,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _creation_fingerprint(
        cls,
        request: ArtifactComposeRequest,
        *,
        source_content: str | None = None,
    ) -> str:
        payload = request.model_dump(
            mode="json",
            exclude={"idempotency_key"},
        )
        if source_content is not None:
            payload["source_content_sha256"] = hashlib.sha256(
                source_content.encode("utf-8")
            ).hexdigest()
        return cls._operation_fingerprint(
            "created",
            payload,
        )

    @staticmethod
    def _existing_result(
        view: ArtifactView,
    ) -> ArtifactCreationResult:
        quality = ArtifactQualityReport.from_dict(
            dict(view.version.validation)
        )
        return ArtifactCreationResult(
            view=view,
            quality=quality,
            source_content=view.version.source_content,
            provider=view.version.provider,
            model=view.version.model,
            request_id=view.version.request_id,
            draft_character_count=len(
                view.version.source_content
            ),
        )

    @staticmethod
    def _source_snapshot(
        request: ArtifactComposeRequest,
    ) -> dict[str, Any]:
        if request.source_snapshot is None:
            return {
                "kind": "explicit_prompt",
                "summary": request.prompt[:500],
                "content": request.prompt,
                "message_ids": [],
                "attachment_names": [],
                "confidence": 1.0,
            }

        return request.source_snapshot.model_dump()

    @staticmethod
    def _source_model(
        view: ArtifactView,
    ) -> ArtifactSourceSnapshot:
        return ArtifactSourceSnapshot.model_validate(
            view.record.source_snapshot
        )

    @staticmethod
    def _specification(
        request: ArtifactComposeRequest,
        *,
        title: str,
        layout_brief: ArtifactLayoutBrief | None = None,
    ) -> dict[str, Any]:
        return {
            "title": title,
            "subtitle": request.subtitle,
            "author": request.author,
            "format": request.format,
            "tone": request.tone,
            "length": request.length,
            "language": request.language,
            "document_type": request.document_type,
            "purpose": request.purpose,
            "audience": request.audience,
            "layout_family": request.layout_family,
            "branding_mode": request.branding_mode,
            "visual_density": request.visual_density,
            "presentation_tier": request.presentation_tier,
            "architecture_id": (
                layout_brief.architecture_id
                if layout_brief is not None
                else request.previous_architecture_id
            ),
            "architecture_visual_system": (
                layout_brief.visual_system
                if layout_brief is not None
                else request.architecture_visual_system
            ),
            "architecture_mode": (
                layout_brief.architecture_mode
                if layout_brief is not None
                else None
            ),
            "header_mode": request.header_mode,
            "footer_mode": request.footer_mode,
            "include_table_of_contents": request.include_table_of_contents,
            "include_section_openers": request.include_section_openers,
            "include_cover_date": request.include_cover_date,
            "include_cover_profile": request.include_cover_profile,
            "include_document_label": request.include_document_label,
            "include_cover_subtitle": request.include_cover_subtitle,
            "include_executive_summary": (
                request.include_executive_summary
            ),
            "include_table": request.include_table,
            "include_recommendations": (
                request.include_recommendations
            ),
            "include_conclusion": request.include_conclusion,
            "bundle_volume_count": request.bundle_volume_count,
            "profile_id": request.profile_id,
            "prompt_mode": request.prompt_mode,
            "source_reference_used": request.source_ref is not None,
        }

    def _render_source(
        self,
        *,
        source_content: str,
        request: ArtifactComposeRequest,
        fidelity: SourceFidelityProfile | None = None,
    ) -> tuple[object, ArtifactQualityReport, str]:
        # Final defense-in-depth cleanup. Composition instructions are control
        # data, never document body content. This also removes any provider
        # placeholder line before the structured quality gate runs.
        source_content = sanitize_recovered_source_payload(
            source_content
        )

        if (
            request.source_snapshot is not None
            and request.source_snapshot.kind == "artifact_version"
        ):
            if is_canonical_artifact_markdown(source_content):
                source_content = normalize_recovered_artifact_markdown(
                    source_content,
                    fallback_title=(
                        request.title
                        or infer_professional_title(source_content)
                    ),
                )

        normalized_source = normalize_markdown_source(
            source_content
        )
        if fidelity is not None and fidelity.preserve_all:
            metrics = source_fidelity_metrics(
                fidelity.source_body,
                normalized_source,
                fidelity.numbered_heading_titles,
            )
            if not metrics.passed:
                raise ValueError(
                    "Artifact content failed the source-fidelity preservation contract."
                )
        artifact = parse_artifact_document(
            normalized_source,
            title=request.title,
            subtitle=request.subtitle,
            author=request.author,
        )
        artifact = apply_layout_brief(request, artifact)
        artifact = normalize_document_structure(artifact)
        if request.format == "zip":
            artifact = replace(
                artifact,
                bundle_volume_count=(
                    request.bundle_volume_count
                    or 2
                ),
            )
        quality = validate_document_quality(
            artifact,
            source_snapshot=self._source_snapshot(request),
        )

        if quality.error_count:
            details = "; ".join(
                issue.message
                for issue in quality.issues
                if issue.severity == "error"
            )
            raise ValueError(
                "Artifact content failed structural quality validation"
                + (f": {details}" if details else ".")
            )

        stored = self.artifact_storage.create(
            artifact,
            format=request.format,
            filename=request.filename,
        )
        output_quality = inspect_rendered_file(
            stored.path,
            format=stored.format,
        )
        quality.merge(output_quality)

        if (
            fidelity is not None
            and fidelity.preserve_all
            and stored.format == "pdf"
            and quality.page_or_slide_count < fidelity.minimum_expected_pages
        ):
            quality.add(
                "source_fidelity_page_shortfall",
                (
                    "Rendered PDF is too short for the preserved source: "
                    f"expected at least {fidelity.minimum_expected_pages} pages, "
                    f"received {quality.page_or_slide_count}."
                ),
                severity="error",
            )

        if quality.error_count:
            self.artifact_storage.delete(
                stored.artifact_id,
                missing_ok=True,
            )
            details = "; ".join(
                issue.message
                for issue in quality.issues
                if issue.severity == "error"
            )
            raise ValueError(
                "Rendered artifact failed output quality validation"
                + (f": {details}" if details else ".")
            )

        return stored, quality, normalized_source

    async def compose_and_create(
        self,
        request: ArtifactComposeRequest,
        *,
        progress_callback: CompositionProgressCallback | None = None,
    ) -> ArtifactCreationResult:
        request = self._hydrate_source_reference(request)
        if request.profile_id == "auto":
            request = request.model_copy(
                update={
                    "profile_id": resolve_document_profile(
                        request
                    ).profile_id
                }
            )
        creation_fingerprint = self._creation_fingerprint(
            request
        )
        existing = self.artifact_repository.resolve_creation(
            idempotency_key=request.idempotency_key,
            fingerprint=creation_fingerprint,
        )
        if existing is not None:
            return self._existing_result(existing)

        user_supplied_filename = request.filename
        request, plan = plan_artifact(request)
        large_plan = plan_large_source(request)
        fidelity = resolve_source_fidelity(
            request,
            large_plan.source_text,
        )
        if fidelity.preserve_all:
            canonical_title = infer_professional_title(
                fidelity.source_body,
                request.title or plan.title,
            )
            update: dict[str, object] = {"title": canonical_title}
            if user_supplied_filename is None:
                update["filename"] = f"{sanitize_filename(canonical_title)}.{request.format}"
            request = request.model_copy(update=update)
            plan = replace(
                plan,
                title=canonical_title,
                filename=str(update.get("filename", plan.filename)),
            )
        if large_plan.bundle_volume_count is not None:
            requested_name = request.filename or plan.filename
            stem = sanitize_filename(
                requested_name.rsplit(".", 1)[0]
            ) or sanitize_filename(request.title or "document")
            bundle_filename = f"{stem}-PDF-Volumes.zip"
            request = request.model_copy(
                update={
                    "format": "zip",
                    "filename": bundle_filename,
                    "bundle_volume_count": (
                        large_plan.bundle_volume_count
                    ),
                }
            )
            plan = replace(
                plan,
                filename=bundle_filename,
            )

        draft = await compose_artifact_draft(
            request,
            model_router=self.model_router,
            plan=plan,
            progress_callback=progress_callback,
        )
        stored, quality, normalized_source = (
            await asyncio.to_thread(
                self._render_source,
                source_content=draft.content,
                request=request,
                fidelity=fidelity,
            )
        )
        artifact = parse_artifact_document(
            normalized_source,
            title=request.title,
            subtitle=request.subtitle,
            author=request.author,
        )
        resolved_artifact = apply_layout_brief(request, artifact)
        view = self.artifact_repository.register_new(
            stored,
            title=artifact.title,
            source_content=normalized_source,
            specification=self._specification(
                request,
                title=artifact.title,
                layout_brief=resolved_artifact.layout_brief,
            ),
            source_snapshot=self._source_snapshot(request),
            validation=quality.to_dict(),
            page_or_slide_count=quality.page_or_slide_count,
            provider=draft.provider,
            model=draft.model,
            request_id=draft.request_id,
            idempotency_key=request.idempotency_key,
            operation_fingerprint=creation_fingerprint,
        )
        return ArtifactCreationResult(
            view=view,
            quality=quality,
            source_content=normalized_source,
            provider=draft.provider,
            model=draft.model,
            request_id=draft.request_id,
            draft_character_count=len(normalized_source),
        )

    def create_from_markdown(
        self,
        request: ArtifactComposeRequest,
        *,
        source_content: str,
        provider: str | None = None,
        model: str | None = None,
        request_id: str | None = None,
    ) -> ArtifactCreationResult:
        creation_fingerprint = self._creation_fingerprint(
            request,
            source_content=source_content,
        )
        existing = self.artifact_repository.resolve_creation(
            idempotency_key=request.idempotency_key,
            fingerprint=creation_fingerprint,
        )
        if existing is not None:
            return self._existing_result(existing)

        request, _ = plan_artifact(request)
        stored, quality, normalized_source = self._render_source(
            source_content=source_content,
            request=request,
        )
        artifact = parse_artifact_document(
            normalized_source,
            title=request.title,
            subtitle=request.subtitle,
            author=request.author,
        )
        resolved_artifact = apply_layout_brief(request, artifact)
        view = self.artifact_repository.register_new(
            stored,
            title=artifact.title,
            source_content=normalized_source,
            specification=self._specification(
                request,
                title=artifact.title,
                layout_brief=resolved_artifact.layout_brief,
            ),
            source_snapshot=self._source_snapshot(request),
            validation=quality.to_dict(),
            page_or_slide_count=quality.page_or_slide_count,
            provider=provider,
            model=model,
            request_id=request_id,
            idempotency_key=request.idempotency_key,
            operation_fingerprint=creation_fingerprint,
        )
        return ArtifactCreationResult(
            view=view,
            quality=quality,
            source_content=normalized_source,
            provider=provider,
            model=model,
            request_id=request_id,
            draft_character_count=len(normalized_source),
        )

    async def revise(
        self,
        artifact_id: str,
        access_token: str,
        request: ArtifactRevisionRequest,
    ) -> ArtifactCreationResult:
        fingerprint = self._operation_fingerprint(
            "revised",
            request.model_dump(
                mode="json",
                exclude={"idempotency_key"},
            ),
        )
        existing = self.artifact_repository.resolve_operation(
            artifact_id,
            access_token,
            idempotency_key=request.idempotency_key,
            action="revised",
            fingerprint=fingerprint,
        )
        if existing is not None:
            return self._existing_result(existing)

        current_view = self.artifact_repository.get(
            artifact_id,
            access_token,
        )
        current_specification = dict(
            current_view.version.specification
        )
        source_snapshot_model = self._source_model(current_view)
        preserved_title = canonical_revision_title(
            current_view.version.source_content,
            source_snapshot_content=source_snapshot_model.content,
            fallback_title=str(
                current_specification.get(
                    "title",
                    current_view.record.title,
                )
            ),
        )
        design_only = is_design_only_revision(
            request.instruction
        )
        compose_request = ArtifactComposeRequest(
            prompt=request.instruction,
            format=current_view.version.format,
            title=(request.title or preserved_title),
            subtitle=current_specification.get("subtitle"),
            author=current_specification.get("author"),
            filename=current_view.record.display_name,
            tone=current_specification.get(
                "tone",
                "professional",
            ),
            length=current_specification.get(
                "length",
                "standard",
            ),
            language=current_specification.get(
                "language",
                "English",
            ),
            document_type=current_specification.get(
                "document_type",
                "professional_report",
            ),
            purpose=current_specification.get("purpose"),
            audience=current_specification.get("audience"),
            layout_family=current_specification.get("layout_family", "auto"),
            branding_mode=current_specification.get("branding_mode", "none"),
            visual_density=current_specification.get("visual_density", "auto"),
            presentation_tier=(
                "auto"
                if design_only
                else current_specification.get(
                    "presentation_tier",
                    "auto",
                )
            ),
            architecture_visual_system=(
                "auto"
                if design_only
                else current_specification.get(
                    "architecture_visual_system",
                    "auto",
                )
            ),
            header_mode=current_specification.get("header_mode", "auto"),
            footer_mode=current_specification.get("footer_mode", "none"),
            include_table_of_contents=bool(
                current_specification.get("include_table_of_contents", True)
            ),
            include_section_openers=bool(
                current_specification.get("include_section_openers", True)
            ),
            include_cover_date=bool(
                current_specification.get("include_cover_date", False)
            ),
            include_cover_profile=bool(
                current_specification.get("include_cover_profile", False)
            ),
            include_document_label=bool(
                current_specification.get("include_document_label", False)
            ),
            include_cover_subtitle=bool(
                current_specification.get("include_cover_subtitle", False)
            ),
            source_snapshot=source_snapshot_model,
            include_executive_summary=bool(
                current_specification.get(
                    "include_executive_summary",
                    True,
                )
            ),
            include_table=bool(
                current_specification.get(
                    "include_table",
                    True,
                )
            ),
            include_recommendations=bool(
                current_specification.get(
                    "include_recommendations",
                    True,
                )
            ),
            include_conclusion=bool(
                current_specification.get(
                    "include_conclusion",
                    True,
                )
            ),
        )
        current_architecture_id = current_specification.get(
            "architecture_id"
        )
        if not current_architecture_id:
            current_document = parse_artifact_document(
                current_view.version.source_content,
                title=compose_request.title,
                subtitle=compose_request.subtitle,
                author=compose_request.author,
            )
            current_architecture_id = apply_layout_brief(
                compose_request,
                current_document,
            ).layout_brief.architecture_id
        if design_only:
            compose_request = compose_request.model_copy(
                update={
                    "design_revision": True,
                    "previous_architecture_id": str(
                        current_architecture_id
                    ),
                }
            )
        draft: ComposedArtifactDraft = (
            await compose_artifact_revision(
                compose_request,
                current_content=(
                    current_view.version.source_content
                ),
                instruction=request.instruction,
                model_router=self.model_router,
            )
        )
        stored, quality, normalized_source = (
            await asyncio.to_thread(
                self._render_source,
                source_content=draft.content,
                request=compose_request,
            )
        )
        artifact = parse_artifact_document(
            normalized_source,
            title=compose_request.title,
            subtitle=compose_request.subtitle,
            author=compose_request.author,
        )
        resolved_artifact = apply_layout_brief(
            compose_request,
            artifact,
        )
        specification = self._specification(
            compose_request,
            title=artifact.title,
            layout_brief=resolved_artifact.layout_brief,
        )
        view = self.artifact_repository.add_version(
            artifact_id,
            access_token,
            stored,
            source_content=normalized_source,
            specification=specification,
            validation=quality.to_dict(),
            page_or_slide_count=quality.page_or_slide_count,
            provider=draft.provider,
            model=draft.model,
            request_id=draft.request_id,
            expected_version=request.expected_version,
            action="revised",
            idempotency_key=request.idempotency_key,
            operation_fingerprint=fingerprint,
        )
        return ArtifactCreationResult(
            view=view,
            quality=quality,
            source_content=normalized_source,
            provider=draft.provider,
            model=draft.model,
            request_id=draft.request_id,
            draft_character_count=len(normalized_source),
        )

    def export(
        self,
        artifact_id: str,
        access_token: str,
        *,
        format: str,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactCreationResult:
        fingerprint = self._operation_fingerprint(
            "exported",
            {
                "format": format,
                "expected_version": expected_version,
            },
        )
        existing = self.artifact_repository.resolve_operation(
            artifact_id,
            access_token,
            idempotency_key=idempotency_key,
            action="exported",
            fingerprint=fingerprint,
        )
        if existing is not None:
            return self._existing_result(existing)

        current_view = self.artifact_repository.get(
            artifact_id,
            access_token,
        )
        specification = dict(
            current_view.version.specification
        )
        compose_request = ArtifactComposeRequest(
            prompt="Export the existing artifact without changing its content.",
            format=format,
            title=(
                str(specification.get("title", "")).strip()
                or current_view.record.title
            ),
            subtitle=specification.get("subtitle"),
            author=specification.get("author"),
            filename=current_view.record.display_name,
            tone=specification.get("tone", "professional"),
            length=specification.get("length", "standard"),
            language=specification.get("language", "English"),
            document_type=specification.get(
                "document_type",
                "professional_report",
            ),
            purpose=specification.get("purpose"),
            audience=specification.get("audience"),
            layout_family=specification.get("layout_family", "auto"),
            branding_mode=specification.get("branding_mode", "none"),
            visual_density=specification.get("visual_density", "auto"),
            presentation_tier=specification.get(
                "presentation_tier",
                "auto",
            ),
            architecture_visual_system=specification.get(
                "architecture_visual_system",
                "auto",
            ),
            header_mode=specification.get("header_mode", "auto"),
            footer_mode=specification.get("footer_mode", "none"),
            include_table_of_contents=bool(
                specification.get("include_table_of_contents", True)
            ),
            include_section_openers=bool(
                specification.get("include_section_openers", True)
            ),
            include_cover_date=bool(
                specification.get("include_cover_date", False)
            ),
            include_cover_profile=bool(
                specification.get("include_cover_profile", False)
            ),
            include_document_label=bool(
                specification.get("include_document_label", False)
            ),
            include_cover_subtitle=bool(
                specification.get("include_cover_subtitle", False)
            ),
            source_snapshot=self._source_model(current_view),
            include_executive_summary=bool(
                specification.get(
                    "include_executive_summary",
                    True,
                )
            ),
            include_table=bool(
                specification.get("include_table", True)
            ),
            include_recommendations=bool(
                specification.get(
                    "include_recommendations",
                    True,
                )
            ),
            include_conclusion=bool(
                specification.get("include_conclusion", True)
            ),
        )
        stored, quality, normalized_source = self._render_source(
            source_content=current_view.version.source_content,
            request=compose_request,
        )
        view = self.artifact_repository.add_version(
            artifact_id,
            access_token,
            stored,
            source_content=normalized_source,
            specification=self._specification(
                compose_request,
                title=compose_request.title or current_view.record.title,
                layout_brief=apply_layout_brief(
                    compose_request,
                    parse_artifact_document(
                        normalized_source,
                        title=compose_request.title,
                        subtitle=compose_request.subtitle,
                        author=compose_request.author,
                    ),
                ).layout_brief,
            ),
            validation=quality.to_dict(),
            page_or_slide_count=quality.page_or_slide_count,
            provider=current_view.version.provider,
            model=current_view.version.model,
            request_id=current_view.version.request_id,
            expected_version=expected_version,
            action="exported",
            idempotency_key=idempotency_key,
            operation_fingerprint=fingerprint,
        )
        return ArtifactCreationResult(
            view=view,
            quality=quality,
            source_content=normalized_source,
            provider=current_view.version.provider,
            model=current_view.version.model,
            request_id=current_view.version.request_id,
            draft_character_count=len(normalized_source),
        )

    def duplicate(
        self,
        artifact_id: str,
        access_token: str,
        *,
        request: ArtifactDuplicateRequest,
    ) -> ArtifactCreationResult:
        current_view = self.artifact_repository.get(
            artifact_id,
            access_token,
        )
        if (
            request.expected_version is not None
            and request.expected_version != current_view.record.current_version
        ):
            raise ArtifactConflictError(
                "Artifact version changed before duplication."
            )

        specification = dict(
            current_view.version.specification
        )
        compose_request = ArtifactComposeRequest(
            prompt="Duplicate the existing artifact.",
            format=current_view.version.format,
            title=(
                str(specification.get("title", "")).strip()
                or current_view.record.title
            ),
            subtitle=specification.get("subtitle"),
            author=specification.get("author"),
            filename=(
                request.filename
                or f"Copy-of-{current_view.record.display_name}"
            ),
            tone=specification.get("tone", "professional"),
            length=specification.get("length", "standard"),
            language=specification.get("language", "English"),
            document_type=specification.get(
                "document_type",
                "professional_report",
            ),
            purpose=specification.get("purpose"),
            audience=specification.get("audience"),
            layout_family=specification.get("layout_family", "auto"),
            branding_mode=specification.get("branding_mode", "none"),
            visual_density=specification.get("visual_density", "auto"),
            presentation_tier=specification.get(
                "presentation_tier",
                "auto",
            ),
            architecture_visual_system=specification.get(
                "architecture_visual_system",
                "auto",
            ),
            header_mode=specification.get("header_mode", "auto"),
            footer_mode=specification.get("footer_mode", "none"),
            include_table_of_contents=bool(
                specification.get("include_table_of_contents", True)
            ),
            include_section_openers=bool(
                specification.get("include_section_openers", True)
            ),
            include_cover_date=bool(
                specification.get("include_cover_date", False)
            ),
            include_cover_profile=bool(
                specification.get("include_cover_profile", False)
            ),
            include_document_label=bool(
                specification.get("include_document_label", False)
            ),
            include_cover_subtitle=bool(
                specification.get("include_cover_subtitle", False)
            ),
            source_snapshot=self._source_model(current_view),
            include_executive_summary=bool(
                specification.get(
                    "include_executive_summary",
                    True,
                )
            ),
            include_table=bool(
                specification.get("include_table", True)
            ),
            include_recommendations=bool(
                specification.get(
                    "include_recommendations",
                    True,
                )
            ),
            include_conclusion=bool(
                specification.get("include_conclusion", True)
            ),
            idempotency_key=request.idempotency_key,
        )
        return self.create_from_markdown(
            compose_request,
            source_content=current_view.version.source_content,
            provider=current_view.version.provider,
            model=current_view.version.model,
            request_id=current_view.version.request_id,
        )
