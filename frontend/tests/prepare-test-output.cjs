const fs = require('node:fs')
const path = require('node:path')

const outputDirectory = path.resolve(
  __dirname,
  '..',
  '.test-dist',
)

fs.mkdirSync(
  outputDirectory,
  { recursive: true },
)

fs.writeFileSync(
  path.join(
    outputDirectory,
    'package.json',
  ),
  '{"type":"commonjs"}\n',
  'utf8',
)
