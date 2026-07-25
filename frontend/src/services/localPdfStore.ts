const databaseName =
  'authentic-ai-local-files'

const databaseVersion = 1

const pdfStoreName =
  'linked-pdfs'

const maximumStoredPdfFiles = 5

const maximumStoredPdfBytes =
  80 * 1024 * 1024

interface StoredPdfRecord {
  storageKey: string

  name: string
  mimeType: string
  size: number
  lastModified: number

  blob: Blob

  createdAt: number
  updatedAt: number
}

function openPdfDatabase():
  Promise<IDBDatabase> {
  return new Promise(
    (resolve, reject) => {
      if (
        typeof indexedDB ===
        'undefined'
      ) {
        reject(
          new Error(
            'IndexedDB is not available.',
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
            !database
              .objectStoreNames
              .contains(
                pdfStoreName,
              )
          ) {
            const store =
              database
                .createObjectStore(
                  pdfStoreName,
                  {
                    keyPath:
                      'storageKey',
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
                'Local PDF database could not be opened.',
              ),
          )
        }

      request.onblocked =
        () => {
          reject(
            new Error(
              'Local PDF database upgrade is blocked.',
            ),
          )
        }
    },
  )
}

function waitForTransaction(
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
                'Local PDF transaction failed.',
              ),
          )
        }

      transaction.onabort =
        () => {
          reject(
            transaction.error ??
              new Error(
                'Local PDF transaction was aborted.',
              ),
          )
        }
    },
  )
}

function readRequest<T>(
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
                'Local PDF read failed.',
              ),
          )
        }
    },
  )
}

function bytesToHex(
  bytes: Uint8Array,
): string {
  return Array.from(
    bytes,
    (value) =>
      value
        .toString(16)
        .padStart(2, '0'),
  ).join('')
}

async function createPdfStorageKey(
  file: File,
): Promise<string> {
  if (
    typeof crypto ===
      'undefined' ||
    !crypto.subtle
  ) {
    return [
      'pdf',
      file.name,
      file.size,
      file.lastModified,
    ].join(':')
  }

  const content =
    await file.arrayBuffer()

  const digest =
    await crypto.subtle.digest(
      'SHA-256',
      content,
    )

  return (
    'sha256:' +
    bytesToHex(
      new Uint8Array(
        digest,
      ),
    )
  )
}

async function getAllRecords(
  database:
    IDBDatabase,
): Promise<StoredPdfRecord[]> {
  const transaction =
    database.transaction(
      pdfStoreName,
      'readonly',
    )

  const store =
    transaction.objectStore(
      pdfStoreName,
    )

  const records =
    await readRequest(
      store.getAll(),
    ) as StoredPdfRecord[]

  await waitForTransaction(
    transaction,
  )

  return records
}

async function prunePdfDatabase(
  database:
    IDBDatabase,
): Promise<void> {
  const records =
    await getAllRecords(
      database,
    )

  records.sort(
    (left, right) =>
      right.updatedAt -
      left.updatedAt,
  )

  let retainedFiles = 0
  let retainedBytes = 0

  const keysToDelete:
    string[] = []

  for (const record of records) {
    const canRetain =
      retainedFiles <
        maximumStoredPdfFiles &&
      retainedBytes +
        record.size <=
        maximumStoredPdfBytes

    if (canRetain) {
      retainedFiles += 1
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
      pdfStoreName,
      'readwrite',
    )

  const store =
    transaction.objectStore(
      pdfStoreName,
    )

  for (
    const storageKey
    of keysToDelete
  ) {
    store.delete(
      storageKey,
    )
  }

  await waitForTransaction(
    transaction,
  )
}

export async function savePdfLocally(
  file: File,
): Promise<string> {
  const storageKey =
    await createPdfStorageKey(
      file,
    )

  const database =
    await openPdfDatabase()

  try {
    const existingTransaction =
      database.transaction(
        pdfStoreName,
        'readonly',
      )

    const existingStore =
      existingTransaction
        .objectStore(
          pdfStoreName,
        )

    const existing =
      await readRequest(
        existingStore.get(
          storageKey,
        ),
      ) as
        | StoredPdfRecord
        | undefined

    await waitForTransaction(
      existingTransaction,
    )

    const now = Date.now()

    const record:
      StoredPdfRecord = {
        storageKey,

        name: file.name,
        mimeType:
          file.type ||
          'application/pdf',
        size: file.size,
        lastModified:
          file.lastModified,

        blob: file,

        createdAt:
          existing?.createdAt ??
          now,

        updatedAt: now,
      }

    const writeTransaction =
      database.transaction(
        pdfStoreName,
        'readwrite',
      )

    writeTransaction
      .objectStore(
        pdfStoreName,
      )
      .put(
        record,
      )

    await waitForTransaction(
      writeTransaction,
    )

    await prunePdfDatabase(
      database,
    )

    return storageKey
  } finally {
    database.close()
  }
}

export async function loadPdfLocally(
  storageKey: string,
): Promise<File | null> {
  const database =
    await openPdfDatabase()

  try {
    const transaction =
      database.transaction(
        pdfStoreName,
        'readonly',
      )

    const store =
      transaction.objectStore(
        pdfStoreName,
      )

    const record =
      await readRequest(
        store.get(
          storageKey,
        ),
      ) as
        | StoredPdfRecord
        | undefined

    await waitForTransaction(
      transaction,
    )

    if (!record) {
      return null
    }

    const touchTransaction =
      database.transaction(
        pdfStoreName,
        'readwrite',
      )

    touchTransaction
      .objectStore(
        pdfStoreName,
      )
      .put({
        ...record,
        updatedAt:
          Date.now(),
      })

    await waitForTransaction(
      touchTransaction,
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
  } finally {
    database.close()
  }
}

export async function deleteLocalPdf(
  storageKey: string,
): Promise<void> {
  const database =
    await openPdfDatabase()

  try {
    const transaction =
      database.transaction(
        pdfStoreName,
        'readwrite',
      )

    transaction
      .objectStore(
        pdfStoreName,
      )
      .delete(
        storageKey,
      )

    await waitForTransaction(
      transaction,
    )
  } finally {
    database.close()
  }
}
