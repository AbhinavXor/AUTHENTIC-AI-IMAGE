import type {
  ArtifactSourceResponse,
  ArtifactSourceSnapshot,
} from '../types/artifacts'
import type {
  ConversationMessage,
} from '../types/chat'
import type {
  ResolvedArtifactReference,
} from './artifactReferenceResolver'

export interface ResolvedArtifactSource {
  prompt: string
  snapshot:
    | ArtifactSourceSnapshot
    | undefined
  requiresClarification: boolean
  clarification?: string
}

const genericCreatePattern =
  /^\s*(?:(?:please\s+)?(?:create|make|generate|prepare|produce|export|bana\s*do|banado|banao|taiyar\s*karo)\s+)?(?:a\s+|an\s+)?(?:professional\s+)?(?:pdf|docx|pptx|document|presentation|file)(?:\s+(?:please|for\s+me))?\s*[.!?]*$/i

const priorReferencePattern =
  /\b(?:above|previous|earlier|last\s+answer|this\s+answer|this\s+response|that\s+response|same\s+content|conversation|chat|upar|pichla|pichli|pehle\s+wala|is\s+answer|iss\s+response)\b/i

const artifactReadyPattern =
  /\b(?:your\s+(?:pdf|docx|pptx)\s+is\s+ready|download\s+it\s+below|artifact\s+ready)\b/i

const visualizationPattern =
  /```authentic-chart\s*[\s\S]*?```/i

const visualizationGlobalPattern =
  /```authentic-chart\s*[\s\S]*?```/gi

const maximumSnapshotCharacters =
  750_000

const maximumConversationSourceCharacters =
  700_000

const compactPreviewPattern =
  /\[Large source preserved(?: securely)? for document generation:[^\]]+hidden in chat preview\]/i

const sourceRecoveryPattern =
  /\b(?:recover|restore|retrieve|hydrate|load)\b[\s\S]{0,80}\b(?:source|content|document)\b|\b(?:stored|saved|authoritative|original|complete)\s+(?:source|content)\b[\s\S]{0,80}\b(?:recover|restore|retrieve|use|load)\b|\b(?:source|content)\s+ko\s+(?:recover|restore|load)\b/i

const recoveryStopWords =
  new Set([
    'about', 'above', 'again', 'all', 'and',
    'authoritative', 'bana', 'complete', 'content',
    'create', 'document', 'file', 'from', 'include',
    'latest', 'original', 'pdf', 'please',
    'professional', 'professionally', 'recover',
    'restore', 'source', 'stored', 'the', 'this',
    'use', 'version', 'with', 'aur', 'bana',
    'banao', 'do', 'hai', 'ka', 'ke', 'ki', 'ko',
    'karo', 'mein', 'se',
  ])

const recoveryWordPattern =
  /[A-Za-zÀ-ÖØ-öø-ÿ0-9]{3,}/g

export interface RecoveredArtifactCandidate {
  reference: ResolvedArtifactReference
  source: ArtifactSourceResponse
}

function recoveryTerms(
  value: string,
): Set<string> {
  return new Set(
    (value.toLocaleLowerCase().match(
      recoveryWordPattern,
    ) ?? [])
      .filter(
        (word) =>
          !recoveryStopWords.has(word),
      ),
  )
}

function visibleRecoveryContext(
  prompt: string,
  messages: ConversationMessage[],
): string {
  const compactSources = messages
    .filter(
      (message) =>
        compactPreviewPattern.test(
          message.content,
        ),
    )
    .map(
      (message) =>
        message.content,
    )

  return [
    prompt,
    ...compactSources,
  ].join('\n')
}

export function isArtifactSourceRecoveryRequest(
  prompt: string,
): boolean {
  return sourceRecoveryPattern.test(
    prompt.trim(),
  )
}

export function selectRecoveredArtifactSource(
  prompt: string,
  messages: ConversationMessage[],
  candidates: RecoveredArtifactCandidate[],
): RecoveredArtifactCandidate | null {
  if (candidates.length === 0) {
    return null
  }

  const contextTerms =
    recoveryTerms(
      visibleRecoveryContext(
        prompt,
        messages,
      ),
    )

  const messageIds =
    new Set(
      messages.map(
        (message) => message.id,
      ),
    )

  const ranked = candidates
    .map((candidate, index) => {
      const candidateTerms =
        recoveryTerms([
          candidate.source.title,
          candidate.source.filename,
          candidate.source.summary,
          candidate.source.content,
        ].join('\n'))

      const overlap = [
        ...contextTerms,
      ].filter(
        (term) =>
          candidateTerms.has(term),
      )

      const lineageMatches =
        candidate.source.message_ids
          .filter(
            (messageId) =>
              messageIds.has(messageId),
          )
          .length

      const topicScore =
        overlap.length
      const lineageScore =
        lineageMatches * 100
      const recencyTieBreaker =
        Math.max(
          0,
          candidates.length - index,
        ) / 1_000

      return {
        candidate,
        topicScore,
        lineageScore,
        score:
          lineageScore
          + topicScore
          + recencyTieBreaker,
      }
    })
    .sort(
      (left, right) =>
        right.score - left.score,
    )

  const best = ranked[0]

  if (!best) {
    return null
  }

  if (best.lineageScore > 0) {
    return best.candidate
  }

  const requiredTopicMatches =
    contextTerms.size >= 6
      ? 3
      : 2

  return best.topicScore >=
    requiredTopicMatches
      ? best.candidate
      : null
}

function cleanMessageContent(
  content: string,
): string {
  return content
    .replace(
      /<!--AUTHENTIC_[A-Z0-9_]+:[\s\S]*?-->/g,
      '',
    )
    .trim()
}

function sourceMessageContent(
  message: ConversationMessage,
): string {
  return cleanMessageContent(
    message.artifactSourceContent
      ?? message.content,
  ).replace(
    /\[Large source preserved(?: securely)? for document generation:[^\]]+hidden in chat preview\]/gi,
    '',
  ).trim()
}

function isMeaningfulAssistantMessage(
  message: ConversationMessage,
): boolean {
  if (
    message.role !== 'assistant' ||
    message.isStreaming ||
    message.artifact
  ) {
    return false
  }

  const content =
    cleanMessageContent(message.content)

  return (
    content.length >= 80 &&
    !artifactReadyPattern.test(content)
  )
}

function findLatestAssistantSource(
  messages: ConversationMessage[],
): ConversationMessage[] {
  for (
    let index = messages.length - 1;
    index >= 0;
    index -= 1
  ) {
    const message = messages[index]

    if (
      message &&
      isMeaningfulAssistantMessage(message)
    ) {
      const selected: ConversationMessage[] = []
      const selectedIds = new Set<string>()

      const addMessage = (
        candidate: ConversationMessage | undefined,
      ) => {
        if (
          !candidate ||
          candidate.isStreaming ||
          selectedIds.has(candidate.id)
        ) {
          return
        }

        selected.push(candidate)
        selectedIds.add(candidate.id)
      }

      const earliestIndex = Math.max(0, index - 12)
      for (
        let visualIndex = earliestIndex;
        visualIndex < index;
        visualIndex += 1
      ) {
        const visualMessage = messages[visualIndex]
        if (
          visualMessage?.role !== 'assistant' ||
          !visualizationPattern.test(
            visualMessage.content,
          )
        ) {
          continue
        }

        const visualPrompt =
          messages[visualIndex - 1]
        if (visualPrompt?.role === 'user') {
          addMessage(visualPrompt)
        }
        addMessage(visualMessage)
      }

      const previous = messages[index - 1]
      if (previous?.role === 'user') {
        addMessage(previous)
      }
      addMessage(message)

      return selected
    }
  }

  return []
}

function recentConversationSource(
  messages: ConversationMessage[],
): ConversationMessage[] {
  const selected: ConversationMessage[] = []
  let characters = 0

  for (
    let index = messages.length - 1;
    index >= 0 && selected.length < 8;
    index -= 1
  ) {
    const message = messages[index]

    if (
      !message ||
      message.isStreaming ||
      message.artifact
    ) {
      continue
    }

    const content =
      sourceMessageContent(message)

    if (!content) {
      continue
    }

    const accepted = content.slice(
      0,
      Math.max(
        0,
        maximumConversationSourceCharacters - characters,
      ),
    )

    if (!accepted) {
      break
    }

    selected.unshift({
      ...message,
      content: accepted,
    })
    characters += accepted.length
  }

  return selected
}

function visualizationTitle(
  block: string,
): string {
  const payload = block
    .replace(
      /^```authentic-chart\s*/i,
      '',
    )
    .replace(/```\s*$/, '')
    .trim()

  try {
    const parsed = JSON.parse(payload) as {
      title?: unknown
    }

    if (
      typeof parsed.title === 'string' &&
      parsed.title.trim()
    ) {
      return parsed.title.trim()
    }
  } catch {
    // The backend validates the complete block.
  }

  return 'Generated visualization'
}

function snapshotContentFromMessages(
  messages: ConversationMessage[],
): string {
  const visualizations: string[] = []
  const seenVisualizations =
    new Set<string>()

  const narrative = messages
    .map((message) => {
      const cleaned =
        sourceMessageContent(
          message,
        )

      const withoutVisualizations =
        cleaned.replace(
          visualizationGlobalPattern,
          (block) => {
            const normalized =
              block.trim()

            if (
              !seenVisualizations.has(
                normalized,
              )
            ) {
              visualizations.push(
                normalized,
              )
              seenVisualizations.add(
                normalized,
              )
            }

            return (
              `[Visualization preserved: ${
                visualizationTitle(
                  normalized,
                )
              }]`
            )
          },
        )
        .trim()

      return `${
        message.role === 'assistant'
          ? 'Serenya'
          : 'User'
      }:\n${withoutVisualizations}`
    })
    .filter(
      (entry) =>
        !entry.endsWith(':\n'),
    )
    .join('\n\n')

  const retainedVisualizations:
    string[] = []
  let visualizationCharacters = 0

  for (
    let index = visualizations.length - 1;
    index >= 0;
    index -= 1
  ) {
    const block = visualizations[index]
    const cost =
      block.length + 2

    if (
      visualizationCharacters + cost >
      maximumSnapshotCharacters - 1_000
    ) {
      continue
    }

    retainedVisualizations.unshift(
      block,
    )
    visualizationCharacters += cost
  }

  const visualizationSection =
    retainedVisualizations.length > 0
      ? [
          'SOURCE VISUALIZATIONS',
          ...retainedVisualizations,
          'END SOURCE VISUALIZATIONS',
        ].join('\n\n')
      : ''

  const separatorCharacters =
    visualizationSection ? 2 : 0
  const narrativeBudget = Math.max(
    0,
    maximumSnapshotCharacters -
      visualizationSection.length -
      separatorCharacters,
  )

  const compactNarrative =
    narrative.length <= narrativeBudget
      ? narrative
      : narrative
          .slice(
            narrative.length -
              narrativeBudget,
          )
          .replace(
            /^[^\n]*(?:\n|$)/,
            '',
          )
          .trim()

  return [
    compactNarrative,
    visualizationSection,
  ]
    .filter(Boolean)
    .join('\n\n')
    .slice(0, maximumSnapshotCharacters)
}

function snapshotFromMessages(
  messages: ConversationMessage[],
  kind:
    | 'previous_response'
    | 'conversation',
): ArtifactSourceSnapshot {
  const content =
    snapshotContentFromMessages(
      messages,
    )

  const latest = messages[messages.length - 1]
  const summary =
    cleanMessageContent(
      latest?.content ?? 'Conversation content',
    )
      .replace(
        visualizationGlobalPattern,
        '',
      )
      .slice(0, 400)
      .replace(/\s+/g, ' ')

  return {
    kind,
    summary:
      summary || 'Recent conversation content',
    content,
    message_ids: messages.map(
      (message) => message.id,
    ),
    attachment_names: messages
      .map(
        (message) =>
          message.attachment?.name,
      )
      .filter(
        (name): name is string =>
          Boolean(name),
      ),
    confidence:
      kind === 'previous_response'
        ? 0.98
        : 0.9,
  }
}

const substantialExplicitSourceMinimumCharacters =
  1_200

const substantialExplicitSourceMinimumLines =
  14

export function hasSubstantialExplicitArtifactSource(
  prompt: string,
): boolean {
  const normalized = prompt
    .replace(
      /\[Large source preserved(?: securely)? for document generation:[^\]]+hidden in chat preview\]/gi,
      '',
    )
    .trim()

  if (!normalized) {
    return false
  }

  const lines = normalized
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  return (
    normalized.length >=
      substantialExplicitSourceMinimumCharacters
    || lines.length >=
      substantialExplicitSourceMinimumLines
  )
}

export function createExplicitArtifactSource(
  prompt: string,
): ResolvedArtifactSource {
  const isLargeExplicitSource =
    prompt.length >= 2_000

  return {
    prompt:
      isLargeExplicitSource
        ? [
            (
              'Create the requested artifact from '
              + 'the complete explicit source snapshot.'
            ),
            (
              'Treat that snapshot as authoritative, '
              + 'follow its trailing production '
              + 'instructions, preserve its supported '
              + 'content, and do not substitute an '
              + 'unrelated topic.'
            ),
          ].join(' ')
        : prompt,
    snapshot: {
      kind: 'explicit_prompt',
      summary: prompt.slice(0, 500),
      content:
        isLargeExplicitSource
          ? prompt.slice(
              0,
              4_000_000,
            )
          : undefined,
      message_ids: [],
      attachment_names: [],
      confidence: 0.96,
    },
    requiresClarification: false,
  }
}

function hasExplicitSubject(
  prompt: string,
): boolean {
  if (genericCreatePattern.test(prompt)) {
    return false
  }

  return (
    /\b(?:about|on|regarding|for|of|covering|explaining)\s+\S/i.test(
      prompt,
    ) ||
    prompt.length > 70
  )
}

export function artifactSourceHasCompactPreviewGap(
  source: ResolvedArtifactSource | null,
  messages: ConversationMessage[],
): boolean {
  if (!source) {
    return false
  }

  if (
    compactPreviewPattern.test(
      source.prompt,
    )
    || compactPreviewPattern.test(
      source.snapshot?.content ?? '',
    )
  ) {
    return true
  }

  if (
    source.snapshot?.kind ===
      'explicit_prompt'
  ) {
    return false
  }

  const relevantIds =
    new Set(
      source.snapshot?.message_ids
      ?? [],
    )

  return messages.some(
    (message) => {
      if (
        relevantIds.size > 0
        && !relevantIds.has(
          message.id,
        )
      ) {
        return false
      }

      if (
        !compactPreviewPattern.test(
          message.content,
        )
      ) {
        return false
      }

      const retained =
        message.artifactSourceContent
          ?.trim()

      return (
        !retained
        || compactPreviewPattern.test(
          retained,
        )
      )
    },
  )
}


export function resolveArtifactSource(
  prompt: string,
  messages: ConversationMessage[],
): ResolvedArtifactSource {
  const normalized = prompt.trim()
  const latestAssistantSource =
    findLatestAssistantSource(messages)

  // A substantial pasted source is authoritative even when its
  // narrative happens to contain words such as "previous",
  // "earlier", "above", "conversation", or "same content".
  // Those incidental words must never turn a new-document request
  // into a reference to an older chat response.
  if (
    hasSubstantialExplicitArtifactSource(
      normalized,
    )
  ) {
    return createExplicitArtifactSource(
      normalized,
    )
  }

  if (
    priorReferencePattern.test(normalized) ||
    genericCreatePattern.test(normalized)
  ) {
    if (latestAssistantSource.length > 0) {
      const snapshot = snapshotFromMessages(
        latestAssistantSource,
        'previous_response',
      )

      return {
        prompt: [
          normalized,
          '',
          (
            'Use the supplied previous Serenya response '
            + 'as the primary source. Preserve its actual '
            + 'topic and do not substitute unrelated '
            + 'Authentic AI company content.'
          ),
        ].join('\n'),
        snapshot,
        requiresClarification: false,
      }
    }

    const conversation =
      recentConversationSource(messages)

    if (conversation.length > 0) {
      return {
        prompt: normalized,
        snapshot: snapshotFromMessages(
          conversation,
          'conversation',
        ),
        requiresClarification: false,
      }
    }

    return {
      prompt: normalized,
      snapshot: undefined,
      requiresClarification: true,
      clarification:
        'What should the document be about? You can name a topic, refer to a previous answer, or upload a source file.',
    }
  }

  if (hasExplicitSubject(normalized)) {
    return createExplicitArtifactSource(
      normalized,
    )
  }

  const conversation =
    recentConversationSource(messages)

  if (conversation.length > 0) {
    return {
      prompt: normalized,
      snapshot: snapshotFromMessages(
        conversation,
        'conversation',
      ),
      requiresClarification: false,
    }
  }

  return {
    prompt: normalized,
    snapshot: undefined,
    requiresClarification: true,
    clarification:
      'What should the document be about? Please provide the topic or source content.',
  }
}
