import { useState } from 'react'

const KEY = 'strategy'

function saved(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

/** The last choice if it's still loaded, else `semantic`, else the first loaded one. */
function pick(names: string[], last: string | null): string | null {
  if (last && names.includes(last)) return last
  if (names.includes('semantic')) return 'semantic'
  return names[0] ?? null
}

/** The Chunking strategy to search, out of `names` (null while they load). Remembered across visits. */
export function useStrategy(names: string[] | null) {
  const [last, setLast] = useState(saved)
  const strategy = names ? pick(names, last) : null
  const choose = (name: string) => {
    setLast(name)
    try {
      localStorage.setItem(KEY, name)
    } catch { /* storage blocked: the choice lasts for this visit only */ }
  }
  return [strategy, choose] as const
}
