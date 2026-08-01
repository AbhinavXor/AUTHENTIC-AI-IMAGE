import type {
  ConversationMessage,
} from '../types/chat'

interface SourceRecord {
  id: string
  content: string
  createdAt: string
  updatedAt: string
  characterCount: number
  prefix: string
  suffix: string
}

export interface RecoveredArtifactSourcePrompt {
  content: string
  sourceId: string | null
  recovered: boolean
}

export const maximumArtifactSourceCharacters =
  4_000_000

const databaseName =
  'authentic-ai-artifact-source-vault-v1'
const storeName = 'sources'
const databaseVersion = 2

const memoryFallback =
  new Map<string, string>()

const sourceReferencePattern =
  /<!--AUTHENTIC_ARTIFACT_SOURCE_REF:([^>]+)-->/i

const sourceReferenceGlobalPattern =
  /<!--AUTHENTIC_ARTIFACT_SOURCE_REF:[^>]+-->/gi

const compactPreviewPattern =
  /\[Large source preserved(?: securely)? for document generation:\s*[\d,]+\s+middle characters hidden in chat preview\]/i

function normalizeSource(
  value: string,
): string {
  return value
    .slice(
      0,
      maximumArtifactSourceCharacters,
    )
    .trim()
}

function stripSourceReference(
  value: string,
): string {
  return value
    .replace(
      sourceReferenceGlobalPattern,
      '',
    )
    .trim()
}

function sourcePreviewParts(
  value: string,
): {
    prefix: string
    suffix: string
  } | null {
  const cleaned =
    stripSourceReference(value)

  const match =
    compactPreviewPattern.exec(cleaned)

  if (
    !match ||
    match.index === undefined
  ) {
    return null
  }

  return {
    prefix: cleaned
      .slice(0, match.index)
      .trim(),
    suffix: cleaned
      .slice(
        match.index +
          match[0].length,
      )
      .trim(),
  }
}

export function extractArtifactSourceReference(
  value: string,
): string | null {
  const match =
    value.match(
      sourceReferencePattern,
    )

  if (!match?.[1]) {
    return null
  }

  try {
    return decodeURIComponent(
      match[1],
    )
  } catch {
    return match[1]
  }
}

export function compactPreviewMatchesSource(
  preview: string,
  source: string,
): boolean {
  const parts =
    sourcePreviewParts(preview)

  if (!parts) {
    return false
  }

  const normalizedSource =
    normalizeSource(source)

  if (!normalizedSource) {
    return false
  }

  const prefix =
    parts.prefix.trim()
  const suffix =
    parts.suffix.trim()

  if (
    prefix.length < 120 ||
    suffix.length < 120
  ) {
    return false
  }

  return (
    normalizedSource.startsWith(
      prefix,
    ) &&
    normalizedSource.endsWith(
      suffix,
    )
  )
}

export function createCompactArtifactSourcePreview(
  value: string,
  sourceId?: string,
): string {
  const normalized =
    normalizeSource(value)

  const displayLimit = 16_000

  if (
    normalized.length <=
    displayLimit
  ) {
    return normalized
  }

  const beginning =
    normalized.slice(0, 10_000)
  const ending =
    normalized.slice(-3_000)
  const omitted = Math.max(
    0,
    normalized.length -
      beginning.length -
      ending.length,
  )

  const reference = sourceId
    ? (
        '<!--AUTHENTIC_ARTIFACT_SOURCE_REF:'
        + encodeURIComponent(sourceId)
        + '-->'
      )
    : ''

  return [
    beginning,
    '',
    (
      '[Large source preserved securely for document generation: '
      + `${omitted.toLocaleString()} `
      + 'middle characters hidden in chat preview]'
    ),
    reference,
    '',
    ending,
  ]
    .filter(Boolean)
    .join('\n')
}

function openDatabase():
  Promise<IDBDatabase> {
  return new Promise(
    (resolve, reject) => {
      if (
        typeof window ===
          'undefined' ||
        !('indexedDB' in window)
      ) {
        reject(
          new Error(
            'IndexedDB is unavailable.',
          ),
        )
        return
      }

      const request =
        window.indexedDB.open(
          databaseName,
          databaseVersion,
        )

      request.onupgradeneeded = () => {
        const database =
          request.result

        if (
          !database.objectStoreNames
            .contains(storeName)
        ) {
          database.createObjectStore(
            storeName,
            { keyPath: 'id' },
          )
        }
      }

      request.onsuccess = () =>
        resolve(request.result)

      request.onerror = () =>
        reject(
          request.error ??
          new Error(
            'Source vault could not be opened.',
          ),
        )
    },
  )
}

function sourceRecord(
  sourceId: string,
  content: string,
): SourceRecord {
  const normalized =
    normalizeSource(content)
  const timestamp =
    new Date().toISOString()

  return {
    id: sourceId,
    content: normalized,
    createdAt: timestamp,
    updatedAt: timestamp,
    characterCount:
      normalized.length,
    prefix:
      normalized.slice(0, 10_000),
    suffix:
      normalized.slice(-3_000),
  }
}

export async function storeArtifactSource(
  sourceId: string,
  content: string,
): Promise<void> {
  const record =
    sourceRecord(
      sourceId,
      content,
    )

  if (!record.content) {
    return
  }

  memoryFallback.set(
    sourceId,
    record.content,
  )

  try {
    const database =
      await openDatabase()

    await new Promise<void>(
      (resolve, reject) => {
        const transaction =
          database.transaction(
            storeName,
            'readwrite',
          )

        transaction.objectStore(
          storeName,
        ).put(record)

        transaction.oncomplete = () => {
          database.close()
          resolve()
        }

        transaction.onerror = () => {
          database.close()
          reject(
            transaction.error ??
            new Error(
              'Source vault write failed.',
            ),
          )
        }

        transaction.onabort = () => {
          database.close()
          reject(
            transaction.error ??
            new Error(
              'Source vault write was aborted.',
            ),
          )
        }
      },
    )
  } catch {
    // The in-memory fallback keeps the current session operational.
  }
}

export async function readArtifactSource(
  sourceId: string,
): Promise<string | null> {
  const cached =
    memoryFallback.get(sourceId)

  if (cached) {
    return cached
  }

  try {
    const database =
      await openDatabase()

    const result =
      await new Promise<SourceRecord | undefined>(
        (resolve, reject) => {
          const transaction =
            database.transaction(
              storeName,
              'readonly',
            )
          const request =
            transaction.objectStore(
              storeName,
            ).get(sourceId)

          request.onsuccess = () =>
            resolve(
              request.result as
                | SourceRecord
                | undefined,
            )

          request.onerror = () =>
            reject(
              request.error ??
              new Error(
                'Source vault read failed.',
              ),
            )

          transaction.oncomplete = () =>
            database.close()
        },
      )

    const content =
      result?.content?.trim()

    if (content) {
      memoryFallback.set(
        sourceId,
        content,
      )
      return content
    }
  } catch {
    // Fall through to null so preview matching can run.
  }

  return null
}

async function readAllArtifactSources():
  Promise<SourceRecord[]> {
  try {
    const database =
      await openDatabase()

    return await new Promise<SourceRecord[]>(
      (resolve, reject) => {
        const transaction =
          database.transaction(
            storeName,
            'readonly',
          )
        const request =
          transaction.objectStore(
            storeName,
          ).getAll()

        request.onsuccess = () => {
          const records = (
            request.result as
              SourceRecord[]
          )
            .filter(
              (record) =>
                Boolean(
                  record?.id &&
                  record?.content,
                ),
            )
            .sort(
              (left, right) =>
                String(
                  right.updatedAt ??
                  right.createdAt,
                ).localeCompare(
                  String(
                    left.updatedAt ??
                    left.createdAt,
                  ),
                ),
            )

          resolve(records)
        }

        request.onerror = () =>
          reject(
            request.error ??
            new Error(
              'Source vault listing failed.',
            ),
          )

        transaction.oncomplete = () =>
          database.close()
      },
    )
  } catch {
    return []
  }
}

export async function recoverArtifactSourcePrompt(
  value: string,
): Promise<RecoveredArtifactSourcePrompt | null> {
  const normalized =
    value.trim()

  if (!normalized) {
    return null
  }

  const sourceId =
    extractArtifactSourceReference(
      normalized,
    )

  if (sourceId) {
    const exact =
      await readArtifactSource(
        sourceId,
      )

    if (exact) {
      return {
        content: exact,
        sourceId,
        recovered: true,
      }
    }
  }

  if (
    !compactPreviewPattern.test(
      normalized,
    )
  ) {
    return null
  }

  for (
    const [id, content]
    of memoryFallback.entries()
  ) {
    if (
      compactPreviewMatchesSource(
        normalized,
        content,
      )
    ) {
      return {
        content,
        sourceId: id,
        recovered: true,
      }
    }
  }

  const records =
    await readAllArtifactSources()

  const match = records.find(
    (record) =>
      compactPreviewMatchesSource(
        normalized,
        record.content,
      ),
  )

  if (!match) {
    return null
  }

  memoryFallback.set(
    match.id,
    match.content,
  )

  return {
    content: match.content,
    sourceId: match.id,
    recovered: true,
  }
}

export async function hydrateArtifactSourceMessages(
  messages: ConversationMessage[],
): Promise<ConversationMessage[]> {
  return Promise.all(
    messages.map(async (message) => {
      if (
        message.artifactSourceContent
      ) {
        return message
      }

      if (message.artifactSourceRef) {
        const exact =
          await readArtifactSource(
            message.artifactSourceRef,
          )

        if (exact) {
          return {
            ...message,
            artifactSourceContent:
              exact,
          }
        }
      }

      if (
        !compactPreviewPattern.test(
          message.content,
        )
      ) {
        return message
      }

      const recovered =
        await recoverArtifactSourcePrompt(
          message.content,
        )

      return recovered
        ? {
            ...message,
            artifactSourceContent:
              recovered.content,
            artifactSourceRef:
              recovered.sourceId
              ?? message.artifactSourceRef,
          }
        : message
    }),
  )
}
