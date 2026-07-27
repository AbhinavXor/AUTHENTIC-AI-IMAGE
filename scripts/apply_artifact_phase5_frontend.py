from __future__ import annotations

from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]


def update_file(
    relative_path: str,
    transform: Callable[[str], str],
) -> None:
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    content = path.read_text(
        encoding="utf-8",
    )

    updated = transform(content)

    if updated == content:
        print(
            f"UNCHANGED: {relative_path}"
        )
        return

    path.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        f"UPDATED: {relative_path}"
    )


def replace_once(
    content: str,
    old: str,
    new: str,
    *,
    description: str,
) -> str:
    if new in content:
        return content

    if old not in content:
        raise RuntimeError(
            f"{description} marker was not found."
        )

    return content.replace(
        old,
        new,
        1,
    )


def patch_artifact_studio(
    content: str,
) -> str:
    content = replace_once(
        content,
        """  LoaderCircle,
  ShieldCheck,
  Sparkles,
""",
        """  LoaderCircle,
  PenLine,
  ShieldCheck,
  Sparkles,
""",
        description="Artifact Studio icon import",
    )

    content = replace_once(
        content,
        """import {
  ArtifactResultCard,
} from '../components/Artifacts/ArtifactResultCard'
""",
        """import {
  ArtifactResultCard,
} from '../components/Artifacts/ArtifactResultCard'
import {
  ArtifactPromptComposer,
} from '../components/Artifacts/ArtifactPromptComposer'
""",
        description=(
            "Artifact Prompt Composer import"
        ),
    )

    content = replace_once(
        content,
        """import {
  ArtifactApiError,
  deleteArtifact,
  downloadArtifact,
  generateArtifact,
} from '../services/artifacts'
""",
        """import {
  ArtifactApiError,
  deleteArtifact,
  downloadArtifact,
  generateArtifact,
} from '../services/artifacts'
import {
  composeArtifact,
} from '../services/artifact-composer'
""",
        description=(
            "Artifact Composer service import"
        ),
    )

    content = replace_once(
        content,
        """import type {
  ArtifactFormat,
  ArtifactRecord,
} from '../types/artifacts'
""",
        """import type {
  ArtifactFormat,
  ArtifactRecord,
} from '../types/artifacts'
import type {
  ArtifactLength,
  ArtifactTone,
} from '../types/artifact-composer'
""",
        description=(
            "Artifact Composer type import"
        ),
    )

    content = replace_once(
        content,
        """const historyStorageKey =
  'authentic-ai.artifact-studio.history.v1'

""",
        """const historyStorageKey =
  'authentic-ai.artifact-studio.history.v1'

type ArtifactCreationMode =
  | 'ai'
  | 'manual'

""",
        description=(
            "Artifact creation mode type"
        ),
    )

    content = replace_once(
        content,
        """export function ArtifactStudio() {
  const [format, setFormat] =
    useState<ArtifactFormat>('pdf')
""",
        """export function ArtifactStudio() {
  const [
    creationMode,
    setCreationMode,
  ] = useState<ArtifactCreationMode>(
    'ai',
  )

  const [format, setFormat] =
    useState<ArtifactFormat>('pdf')
""",
        description=(
            "Artifact creation mode state"
        ),
    )

    content = replace_once(
        content,
        """  const [content, setContent] =
    useState(initialContent)

  const [artifact, setArtifact] =
""",
        """  const [content, setContent] =
    useState(initialContent)

  const [prompt, setPrompt] =
    useState(
      (
        'Create a professional report '
        + 'about the requested subject. '
        + 'Explain the main findings, '
        + 'risks, recommendations and '
        + 'next actions.'
      ),
    )

  const [tone, setTone] =
    useState<ArtifactTone>(
      'professional',
    )

  const [length, setLength] =
    useState<ArtifactLength>(
      'standard',
    )

  const [language, setLanguage] =
    useState('English')

  const [
    includeExecutiveSummary,
    setIncludeExecutiveSummary,
  ] = useState(true)

  const [
    includeTable,
    setIncludeTable,
  ] = useState(true)

  const [
    includeRecommendations,
    setIncludeRecommendations,
  ] = useState(true)

  const [
    includeConclusion,
    setIncludeConclusion,
  ] = useState(true)

  const [artifact, setArtifact] =
""",
        description=(
            "Artifact AI composer state"
        ),
    )

    content = replace_once(
        content,
        """  const canGenerate =
    !isGenerating &&
    content.trim().length > 0 &&
    characterCount <=
      maximumContentCharacters
""",
        """  const canGenerate =
    !isGenerating &&
    (
      creationMode === 'ai'
        ? (
            prompt.trim().length > 0 &&
            prompt.length <= 8_000 &&
            language.trim().length > 0
          )
        : (
            content.trim().length > 0 &&
            characterCount <=
              maximumContentCharacters
          )
    )
""",
        description=(
            "Artifact generation eligibility"
        ),
    )

    content = replace_once(
        content,
        """      const generated =
        await generateArtifact(
          {
            content,
            format,
            title:
              cleanOptionalValue(
                title,
              ),
            subtitle:
              cleanOptionalValue(
                subtitle,
              ),
            author:
              cleanOptionalValue(
                author,
              ),
            filename:
              cleanOptionalValue(
                filename,
              ),
          },
          controller.signal,
        )
""",
        """      const generated =
        creationMode === 'ai'
          ? await composeArtifact(
              {
                prompt,
                format,
                title:
                  cleanOptionalValue(
                    title,
                  ),
                subtitle:
                  cleanOptionalValue(
                    subtitle,
                  ),
                author:
                  cleanOptionalValue(
                    author,
                  ),
                filename:
                  cleanOptionalValue(
                    filename,
                  ),
                tone,
                length,
                language:
                  language.trim(),
                include_executive_summary:
                  includeExecutiveSummary,
                include_table:
                  includeTable,
                include_recommendations:
                  includeRecommendations,
                include_conclusion:
                  includeConclusion,
              },
              controller.signal,
            )
          : await generateArtifact(
              {
                content,
                format,
                title:
                  cleanOptionalValue(
                    title,
                  ),
                subtitle:
                  cleanOptionalValue(
                    subtitle,
                  ),
                author:
                  cleanOptionalValue(
                    author,
                  ),
                filename:
                  cleanOptionalValue(
                    filename,
                  ),
              },
              controller.signal,
            )
""",
        description=(
            "Prompt-to-Artifact generation call"
        ),
    )

    mode_section = """          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 1</span>
                <h2>
                  Choose creation mode
                </h2>
              </div>
            </div>

            <div className="artifact-creation-mode-grid">
              <button
                aria-pressed={
                  creationMode === 'ai'
                }
                className={
                  (
                    'artifact-creation-mode-card '
                    + (
                      creationMode === 'ai'
                        ? 'active'
                        : ''
                    )
                  )
                }
                disabled={isGenerating}
                onClick={() =>
                  setCreationMode('ai')
                }
                type="button"
              >
                <span className="artifact-creation-mode-icon">
                  <Sparkles
                    size={20}
                    strokeWidth={1.8}
                  />
                </span>

                <span className="artifact-creation-mode-copy">
                  <strong>
                    Create with AI
                  </strong>

                  <small>
                    Describe the document and
                    Authentic AI will compose
                    and generate it.
                  </small>
                </span>
              </button>

              <button
                aria-pressed={
                  creationMode === 'manual'
                }
                className={
                  (
                    'artifact-creation-mode-card '
                    + (
                      creationMode === 'manual'
                        ? 'active'
                        : ''
                    )
                  )
                }
                disabled={isGenerating}
                onClick={() =>
                  setCreationMode('manual')
                }
                type="button"
              >
                <span className="artifact-creation-mode-icon">
                  <PenLine
                    size={20}
                    strokeWidth={1.8}
                  />
                </span>

                <span className="artifact-creation-mode-copy">
                  <strong>
                    Use prepared content
                  </strong>

                  <small>
                    Paste structured Markdown
                    content and generate the
                    selected file directly.
                  </small>
                </span>
              </button>
            </div>
          </section>

"""

    first_section_marker = (
        """          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 1</span>
                <h2>
                  Select the output
                </h2>
"""
    )

    updated_first_section = (
        mode_section
        + """          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 2</span>
                <h2>
                  Select the output
                </h2>
"""
    )

    content = replace_once(
        content,
        first_section_marker,
        updated_first_section,
        description=(
            "Artifact creation mode section"
        ),
    )

    content = replace_once(
        content,
        """                <span>Step 2</span>
                <h2>
                  Document details
                </h2>
""",
        """                <span>Step 3</span>
                <h2>
                  Document details
                </h2>
""",
        description=(
            "Document details step number"
        ),
    )

    manual_content_section = """          <section className="artifact-panel-section">
            <div
              className={
                'artifact-section-heading '
                + 'artifact-content-heading'
              }
            >
              <div>
                <span>Step 3</span>
                <h2>
                  Add structured content
                </h2>
              </div>

              <small>
                {characterCount
                  .toLocaleString()}
                {' / '}
                {maximumContentCharacters
                  .toLocaleString()}
              </small>
            </div>

            <label className="artifact-content-field">
              <span className="sr-only">
                Artifact content
              </span>

              <textarea
                disabled={isGenerating}
                maxLength={
                  maximumContentCharacters
                }
                onChange={(event) =>
                  setContent(
                    event.target.value,
                  )
                }
                spellCheck
                value={content}
              />
            </label>

            <div className="artifact-content-meter">
              <span
                style={{
                  width:
                    `${contentPercentage}%`,
                }}
              />
            </div>

            <p className="artifact-markdown-note">
              Supports headings,
              paragraphs, lists,
              Markdown tables and
              code blocks.
            </p>
          </section>
"""

    mode_content_section = """          {creationMode === 'ai' ? (
            <section className="artifact-panel-section">
              <div className="artifact-section-heading">
                <div>
                  <span>Step 4</span>
                  <h2>
                    Compose with AI
                  </h2>
                </div>
              </div>

              <ArtifactPromptComposer
                disabled={isGenerating}
                includeConclusion={
                  includeConclusion
                }
                includeExecutiveSummary={
                  includeExecutiveSummary
                }
                includeRecommendations={
                  includeRecommendations
                }
                includeTable={
                  includeTable
                }
                language={language}
                length={length}
                onIncludeConclusionChange={
                  setIncludeConclusion
                }
                onIncludeExecutiveSummaryChange={
                  setIncludeExecutiveSummary
                }
                onIncludeRecommendationsChange={
                  setIncludeRecommendations
                }
                onIncludeTableChange={
                  setIncludeTable
                }
                onLanguageChange={
                  setLanguage
                }
                onLengthChange={
                  setLength
                }
                onPromptChange={
                  setPrompt
                }
                onToneChange={
                  setTone
                }
                prompt={prompt}
                tone={tone}
              />
            </section>
          ) : (
            <section className="artifact-panel-section">
              <div
                className={
                  'artifact-section-heading '
                  + 'artifact-content-heading'
                }
              >
                <div>
                  <span>Step 4</span>
                  <h2>
                    Add structured content
                  </h2>
                </div>

                <small>
                  {characterCount
                    .toLocaleString()}
                  {' / '}
                  {maximumContentCharacters
                    .toLocaleString()}
                </small>
              </div>

              <label className="artifact-content-field">
                <span className="sr-only">
                  Artifact content
                </span>

                <textarea
                  disabled={isGenerating}
                  maxLength={
                    maximumContentCharacters
                  }
                  onChange={(event) =>
                    setContent(
                      event.target.value,
                    )
                  }
                  spellCheck
                  value={content}
                />
              </label>

              <div className="artifact-content-meter">
                <span
                  style={{
                    width:
                      `${contentPercentage}%`,
                  }}
                />
              </div>

              <p className="artifact-markdown-note">
                Supports headings,
                paragraphs, lists,
                Markdown tables and
                code blocks.
              </p>
            </section>
          )}
"""

    content = replace_once(
        content,
        manual_content_section,
        mode_content_section,
        description=(
            "Artifact AI/manual content section"
        ),
    )

    content = replace_once(
        content,
        """            <span>
              {isGenerating
                ? (
                    'Generating '
                    + 'professional file…'
                  )
                : (
                    `Generate ${
                      format.toUpperCase()
                    }`
                  )}
            </span>
""",
        """            <span>
              {isGenerating
                ? (
                    creationMode === 'ai'
                      ? (
                          'Composing and '
                          + 'generating…'
                        )
                      : (
                          'Generating '
                          + 'professional file…'
                        )
                  )
                : (
                    creationMode === 'ai'
                      ? (
                          `Compose ${
                            format.toUpperCase()
                          } with AI`
                        )
                      : (
                          `Generate ${
                            format.toUpperCase()
                          }`
                        )
                  )}
            </span>
""",
        description=(
            "Artifact generate button label"
        ),
    )

    return content


def patch_app_styles(
    content: str,
) -> str:
    style_import = (
        "import "
        "'./styles/artifact-ai-composer.css'\n"
    )

    if style_import in content:
        return content

    marker = (
        "import "
        "'./styles/artifact-studio.css'\n"
    )

    if marker not in content:
        raise RuntimeError(
            (
                "Artifact Studio stylesheet "
                "import marker was not found."
            )
        )

    return content.replace(
        marker,
        marker + style_import,
        1,
    )


def verify_phase5_frontend_files() -> None:
    required_files = [
        (
            "frontend/src/types/"
            "artifact-composer.ts"
        ),
        (
            "frontend/src/services/"
            "artifact-composer.ts"
        ),
        (
            "frontend/src/components/"
            "Artifacts/"
            "ArtifactPromptComposer.tsx"
        ),
        (
            "frontend/src/styles/"
            "artifact-ai-composer.css"
        ),
    ]

    missing_files = [
        relative_path
        for relative_path in required_files
        if not (
            ROOT / relative_path
        ).is_file()
    ]

    if missing_files:
        formatted = "\n".join(
            f"- {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            (
                "Phase 5 frontend files "
                "are missing:\n"
                f"{formatted}"
            )
        )

    print(
        (
            "PASS: All Phase 5 frontend "
            "files exist"
        )
    )


def main() -> None:
    verify_phase5_frontend_files()

    update_file(
        (
            "frontend/src/pages/"
            "ArtifactStudio.tsx"
        ),
        patch_artifact_studio,
    )

    update_file(
        "frontend/src/App.tsx",
        patch_app_styles,
    )

    print()
    print(
        (
            "PASS: Phase 5 frontend "
            "integration applied"
        )
    )


if __name__ == "__main__":
    main()