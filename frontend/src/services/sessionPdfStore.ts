const databaseName =
  'authentic-ai-session-files'

const databaseVersion = 1

const storeName =
  'session-pdfs'

const sessionIdKey =
  'authentic-ai:pdf-session-id'

const conversationKeyPrefix =
  'authentic-ai:pdf-conversation:'

const latestPdfKey =
  'authentic-ai:pdf-latest'

const maximumSessionFiles = 5

const maximumSessionBytes =
  80 * 1024 * 1024

interface SessionPdfRecord {
  storageKey: string
  sessionId: string
  conversationId: string

  name: string
  mimeType: string
  size: number
  lastModified: number

  blob: Blob

  createdAt: number
  updatedAt: number
}

function getCurrentSessionId():
  string {
  const existing =
    sessionStorage.getItem(
      sessionIdKey,
    )

  if (existing) {
    return existing
  }

  const generated =
    typeof crypto !==
      'undefined' &&
    typeof crypto.randomUUID ===
      'function'
      ? crypto.randomUUID()
      : [
          Date.now(),
          Math.random()
            .toString(36)
            .slice(2),
        ].join('-')

  sessionStorage.setItem(
    sessionIdKey,
    generated,
  )

  return generated
}

function openDatabase():
  Promise<IDBDatabase> {
  return new Promise(
    (resolve, reject) => {
      if (
        typeof indexedDB ===
        'undefined'
      ) {
        reject(
          new Error(
            'IndexedDB is unavailable.',
          ),
        )

        return
      }

      const request =
        indexedDB.open(
          databaseName,
          databaseVersion,
        )

      request.onupgradeneeded =
        () => {
          const database =
            request.result

          if (
            database
              .objectStoreNames
              .contains(
                storeName,
              )
          ) {
            return
          }

          const store =
            database
              .createObjectStore(
                storeName,
                {
                  keyPath:
                    'storageKey',
                },
              )

          store.createIndex(
            'sessionId',
            'sessionId',
            {
              unique: false,
            },
          )

          store.createIndex(
            'updatedAt',
            'updatedAt',
            {
              unique: false,
            },
          )
        }

      request.onsuccess =
        () => {
          resolve(
            request.result,
          )
        }

      request.onerror =
        () => {
          reject(
            request.error ??
              new Error(
                'PDF database could not be opened.',
              ),
          )
        }

      request.onblocked =
        () => {
          reject(
            new Error(
              'PDF database is blocked.',
            ),
          )
        }
    },
  )
}

function requestResult<T>(
  request: IDBRequest<T>,
): Promise<T> {
  return new Promise(
    (resolve, reject) => {
      request.onsuccess =
        () => {
          resolve(
            request.result,
          )
        }

      request.onerror =
        () => {
          reject(
            request.error ??
              new Error(
                'PDF database request failed.',
              ),
          )
        }
    },
  )
}

function transactionComplete(
  transaction:
    IDBTransaction,
): Promise<void> {
  return new Promise(
    (resolve, reject) => {
      transaction.oncomplete =
        () => {
          resolve()
        }

      transaction.onerror =
        () => {
          reject(
            transaction.error ??
              new Error(
                'PDF transaction failed.',
              ),
          )
        }

      transaction.onabort =
        () => {
          reject(
            transaction.error ??
              new Error(
                'PDF transaction was aborted.',
              ),
          )
        }
    },
  )
}

function conversationStorageKey(
  conversationId: string,
): string {
  return (
    conversationKeyPrefix +
    conversationId
  )
}

function createStorageKey(
  sessionId: string,
): string {
  const identifier =
    typeof crypto !==
      'undefined' &&
    typeof crypto.randomUUID ===
      'function'
      ? crypto.randomUUID()
      : [
          Date.now(),
          Math.random()
            .toString(36)
            .slice(2),
        ].join('-')

  return (
    `${sessionId}:${identifier}`
  )
}

async function readAllRecords(
  database:
    IDBDatabase,
): Promise<SessionPdfRecord[]> {
  const transaction =
    database.transaction(
      storeName,
      'readonly',
    )

  const completion =
    transactionComplete(
      transaction,
    )

  const request =
    transaction
      .objectStore(
        storeName,
      )
      .getAll()

  const records =
    await requestResult(
      request,
    ) as SessionPdfRecord[]

  await completion

  return records
}

async function cleanSessionFiles(
  database:
    IDBDatabase,
    currentSessionId: string,
): Promise<void> {
  const records =
    await readAllRecords(
      database,
    )

  const currentRecords =
    records
      .filter(
        (record) =>
          record.sessionId ===
          currentSessionId,
      )
      .sort(
        (left, right) =>
          right.updatedAt -
          left.updatedAt,
      )

  const keysToDelete =
    records
      .filter(
        (record) =>
          record.sessionId !==
          currentSessionId,
      )
      .map(
        (record) =>
          record.storageKey,
      )

  let retainedCount = 0
  let retainedBytes = 0

  for (
    const record
    of currentRecords
  ) {
    const canRetain =
      retainedCount <
        maximumSessionFiles &&
      retainedBytes +
        record.size <=
        maximumSessionBytes

    if (canRetain) {
      retainedCount += 1
      retainedBytes +=
        record.size

      continue
    }

    keysToDelete.push(
      record.storageKey,
    )
  }

  if (
    keysToDelete.length === 0
  ) {
    return
  }

  const transaction =
    database.transaction(
      storeName,
      'readwrite',
    )

  const completion =
    transactionComplete(
      transaction,
    )

  const store =
    transaction.objectStore(
      storeName,
    )

  for (
    const storageKey
    of keysToDelete
  ) {
    store.delete(
      storageKey,
    )
  }

  await completion
}

async function readRecord(
  database:
    IDBDatabase,
  storageKey: string,
): Promise<
  SessionPdfRecord | null
> {
  const transaction =
    database.transaction(
      storeName,
      'readonly',
    )

  const completion =
    transactionComplete(
      transaction,
    )

  const request =
    transaction
      .objectStore(
        storeName,
      )
      .get(
        storageKey,
      )

  const result =
    await requestResult(
      request,
    ) as
      | SessionPdfRecord
      | undefined

  await completion

  return result ?? null
}

export async function savePdfForSession(
  conversationId: string,
  file: File,
): Promise<void> {
  const sessionId =
    getCurrentSessionId()

  const database =
    await openDatabase()

  try {
    await cleanSessionFiles(
      database,
      sessionId,
    )

    const oldStorageKey =
      sessionStorage.getItem(
        conversationStorageKey(
          conversationId,
        ),
      )

    const storageKey =
      createStorageKey(
        sessionId,
      )

    const now =
      Date.now()

    const record:
      SessionPdfRecord = {
        storageKey,
        sessionId,
        conversationId,

        name: file.name,

        mimeType:
          file.type ||
          'application/pdf',

        size: file.size,

        lastModified:
          file.lastModified,

        blob: file,

        createdAt: now,
        updatedAt: now,
      }

    const transaction =
      database.transaction(
        storeName,
        'readwrite',
      )

    const completion =
      transactionComplete(
        transaction,
      )

    const store =
      transaction.objectStore(
        storeName,
      )

    store.put(
      record,
    )

    if (oldStorageKey) {
      store.delete(
        oldStorageKey,
      )
    }

    await completion

    sessionStorage.setItem(
      conversationStorageKey(
        conversationId,
      ),
      storageKey,
    )

    sessionStorage.setItem(
      latestPdfKey,
      storageKey,
    )

    await cleanSessionFiles(
      database,
      sessionId,
    )
  } finally {
    database.close()
  }
}

export async function loadPdfForSession(
  conversationId: string,
  expectedFilename:
    string | null,
): Promise<File | null> {
  const sessionId =
    getCurrentSessionId()

  const database =
    await openDatabase()

  try {
    await cleanSessionFiles(
      database,
      sessionId,
    )

    const conversationKey =
      sessionStorage.getItem(
        conversationStorageKey(
          conversationId,
        ),
      )

    const latestKey =
      sessionStorage.getItem(
        latestPdfKey,
      )

    const candidateKeys = [
      conversationKey,
      latestKey,
    ].filter(
      (
        value,
        index,
        values,
      ): value is string =>
        typeof value ===
          'string' &&
        value.length > 0 &&
        values.indexOf(
          value,
        ) === index,
    )

    for (
      const storageKey
      of candidateKeys
    ) {
      const record =
        await readRecord(
          database,
          storageKey,
        )

      if (
        !record ||
        record.sessionId !==
          sessionId
      ) {
        continue
      }

      if (
        expectedFilename &&
        record.name !==
          expectedFilename
      ) {
        continue
      }

      sessionStorage.setItem(
        conversationStorageKey(
          conversationId,
        ),
        storageKey,
      )

      return new File(
        [
          record.blob,
        ],
        record.name,
        {
          type:
            record.mimeType ||
            'application/pdf',

          lastModified:
            record.lastModified,
        },
      )
    }

    return null
  } finally {
    database.close()
  }
}
