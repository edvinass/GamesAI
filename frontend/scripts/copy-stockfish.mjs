import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const srcDir = path.join(projectRoot, 'node_modules', 'stockfish', 'bin')
const outDir = path.join(projectRoot, 'public', 'stockfish')

/** Full NNUE builds (multi-threaded + single-threaded) plus the lite single-threaded fallback. */
const FLAVORS = ['stockfish-19', 'stockfish-19-single', 'stockfish-19-lite-single']

async function copyIfChanged(src, dst) {
  const [srcStat, dstStat] = await Promise.all([fs.stat(src), fs.stat(dst).catch(() => null)])
  if (dstStat && dstStat.size === srcStat.size && dstStat.mtimeMs >= srcStat.mtimeMs) return false
  await fs.copyFile(src, dst)
  return true
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  let copied = 0
  for (const flavor of FLAVORS) {
    for (const ext of ['.js', '.wasm']) {
      if (await copyIfChanged(path.join(srcDir, flavor + ext), path.join(outDir, flavor + ext))) copied++
    }
  }
  console.log(`Stockfish engine files ready in public/stockfish/ (${copied} updated)`)
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
