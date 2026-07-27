import {
  Sparkles,
} from 'lucide-react'
import type {
  ArtifactLength,
  ArtifactTone,
} from '../../types/artifact-composer'

interface ArtifactPromptComposerProps {
  disabled: boolean
  prompt: string
  tone: ArtifactTone
  length: ArtifactLength
  language: string
  includeExecutiveSummary: boolean
  includeTable: boolean
  includeRecommendations: boolean
  includeConclusion: boolean
  onPromptChange: (
    value: string,
  ) => void
  onToneChange: (
    value: ArtifactTone,
  ) => void
  onLengthChange: (
    value: ArtifactLength,
  ) => void
  onLanguageChange: (
    value: string,
  ) => void
  onIncludeExecutiveSummaryChange: (
    value: boolean,
  ) => void
  onIncludeTableChange: (
    value: boolean,
  ) => void
  onIncludeRecommendationsChange: (
    value: boolean,
  ) => void
  onIncludeConclusionChange: (
    value: boolean,
  ) => void
}

export function ArtifactPromptComposer({
  disabled,
  prompt,
  tone,
  length,
  language,
  includeExecutiveSummary,
  includeTable,
  includeRecommendations,
  includeConclusion,
  onPromptChange,
  onToneChange,
  onLengthChange,
  onLanguageChange,
  onIncludeExecutiveSummaryChange,
  onIncludeTableChange,
  onIncludeRecommendationsChange,
  onIncludeConclusionChange,
}: ArtifactPromptComposerProps) {
  return (
    <div className="artifact-ai-composer">
      <div className="artifact-ai-intro">
        <span>
          <Sparkles
            size={19}
            strokeWidth={1.8}
          />
        </span>

        <div>
          <h3>
            Describe the artifact
          </h3>

          <p>
            Authentic AI will compose
            structured professional content
            and generate the selected file.
          </p>
        </div>
      </div>

      <label className="artifact-ai-prompt-field">
        <span>Artifact instruction</span>

        <textarea
          disabled={disabled}
          maxLength={8_000}
          onChange={(event) =>
            onPromptChange(
              event.target.value,
            )
          }
          placeholder={
            'Example: Create a detailed '
            + 'executive report explaining '
            + 'the Authentic AI architecture, '
            + 'major components, governance '
            + 'boundaries, risks and roadmap.'
          }
          value={prompt}
        />

        <small>
          {prompt.length.toLocaleString()}
          {' / 8,000 characters'}
        </small>
      </label>

      <div className="artifact-ai-settings-grid">
        <label className="artifact-field">
          <span>Tone</span>

          <select
            disabled={disabled}
            onChange={(event) =>
              onToneChange(
                event.target
                  .value as ArtifactTone,
              )
            }
            value={tone}
          >
            <option value="professional">
              Professional
            </option>

            <option value="executive">
              Executive
            </option>

            <option value="technical">
              Technical
            </option>

            <option value="simple">
              Simple language
            </option>

            <option value="academic">
              Academic
            </option>
          </select>
        </label>

        <label className="artifact-field">
          <span>Document length</span>

          <select
            disabled={disabled}
            onChange={(event) =>
              onLengthChange(
                event.target
                  .value as ArtifactLength,
              )
            }
            value={length}
          >
            <option value="brief">
              Brief
            </option>

            <option value="standard">
              Standard
            </option>

            <option value="detailed">
              Detailed
            </option>
          </select>
        </label>

        <label className="artifact-field full">
          <span>Output language</span>

          <input
            disabled={disabled}
            maxLength={80}
            onChange={(event) =>
              onLanguageChange(
                event.target.value,
              )
            }
            placeholder="English"
            value={language}
          />
        </label>
      </div>

      <div className="artifact-ai-options">
        <p>Include sections</p>

        <div className="artifact-ai-option-grid">
          <label>
            <input
              checked={
                includeExecutiveSummary
              }
              disabled={disabled}
              onChange={(event) =>
                onIncludeExecutiveSummaryChange(
                  event.target.checked,
                )
              }
              type="checkbox"
            />

            <span>
              Executive Summary
            </span>
          </label>

          <label>
            <input
              checked={includeTable}
              disabled={disabled}
              onChange={(event) =>
                onIncludeTableChange(
                  event.target.checked,
                )
              }
              type="checkbox"
            />

            <span>
              Useful table
            </span>
          </label>

          <label>
            <input
              checked={
                includeRecommendations
              }
              disabled={disabled}
              onChange={(event) =>
                onIncludeRecommendationsChange(
                  event.target.checked,
                )
              }
              type="checkbox"
            />

            <span>
              Recommendations
            </span>
          </label>

          <label>
            <input
              checked={includeConclusion}
              disabled={disabled}
              onChange={(event) =>
                onIncludeConclusionChange(
                  event.target.checked,
                )
              }
              type="checkbox"
            />

            <span>
              Conclusion
            </span>
          </label>
        </div>
      </div>
    </div>
  )
}