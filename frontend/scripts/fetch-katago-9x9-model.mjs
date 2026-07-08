import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const KATAGO_9X9_MODEL_REMOTE =
  'https://github.com/lightvector/KataGo/releases/download/v1.13.2-kata9x9/kata9x9-b18c384nbt-20231025.bin.gz'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outDir = path.join(projectRoot, 'public', 'models')
const outPath = path.join(outDir, 'kata9x9.bin.gz')

async function exists(filePath) {
  try {
    await fs.stat(filePath)
    return true
  } catch {
    return false
  }
}

async function main() {
  if (await exists(outPath)) {
    console.log('KataGo 9x9 model already present')
    return
  }

  console.log(`Downloading KataGo model (~94 MB) from ${KATAGO_9X9_MODEL_REMOTE}`)
  const res = await fetch(KATAGO_9X9_MODEL_REMOTE)
  if (!res.ok) {
    throw new Error(`Failed to download KataGo model: ${res.status} ${res.statusText}`)
  }
  const buf = Buffer.from(await res.arrayBuffer())
  await fs.mkdir(outDir, { recursive: true })
  await fs.writeFile(outPath, buf)
  console.log(`Saved ${path.relative(projectRoot, outPath)} (${buf.length} bytes)`)
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
