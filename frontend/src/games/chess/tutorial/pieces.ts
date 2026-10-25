/** cburnett piece set, same files as the main board. */
const PIECE_SVG_MODULES = import.meta.glob('../../../assets/chess/pieces/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

export const PIECE_SRC: Record<string, string> = Object.fromEntries(
  Object.entries(PIECE_SVG_MODULES).map(([path, url]) => [
    path.split('/').pop()!.replace('.svg', ''),
    url,
  ]),
)

export function pieceSrc(color: 'w' | 'b', type: string): string {
  return PIECE_SRC[`${color}${type.toUpperCase()}`] ?? ''
}
