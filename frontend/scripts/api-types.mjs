import fs from 'node:fs/promises'
import openapiTS, { astToString } from 'openapi-typescript'
const spec = new URL('../../shared/openapi.json', import.meta.url)
const output = new URL('../../shared/api.generated.ts', import.meta.url)
const generated = astToString(await openapiTS(spec))
if (process.argv.includes('--check')) {
  if (await fs.readFile(output, 'utf8') !== generated) throw new Error('Generated API types are stale. Run pnpm api:generate.')
} else await fs.writeFile(output, generated)
