// Filters mirror SearchParams in api/filters.py. Range bounds are kept as the strings the
// inputs hold, so a half-typed number is never lost; they become numbers only in toParams.

import type { Kind } from './api'

export interface Range {
  column: string
  label: string
  unit?: string
  step?: number
}

export const RANGE_GROUPS: { name: string; ranges: Range[] }[] = [
  {
    name: 'Time',
    ranges: [
      { column: 'total_minutes', label: 'Total', unit: 'min' },
      { column: 'prep_minutes', label: 'Prep', unit: 'min' },
      { column: 'cook_minutes', label: 'Cook', unit: 'min' },
    ],
  },
  {
    name: 'Ratings and servings',
    ranges: [
      { column: 'rating', label: 'Rating', step: 0.1 },
      { column: 'rating_count', label: 'Number of ratings' },
      { column: 'servings', label: 'Servings' },
    ],
  },
  {
    name: 'Nutrition per serving',
    ranges: [
      { column: 'calories', label: 'Calories', unit: 'kcal' },
      { column: 'protein_g', label: 'Protein', unit: 'g' },
      { column: 'fat_g', label: 'Fat', unit: 'g' },
      { column: 'carbohydrates_g', label: 'Carbohydrates', unit: 'g' },
      { column: 'sodium_mg', label: 'Sodium', unit: 'mg' },
    ],
  },
]

const RANGES = RANGE_GROUPS.flatMap(g => g.ranges)

export const KINDS: { value: Kind; label: string }[] = [
  { value: 'summary', label: 'Summary' },
  { value: 'ingredients', label: 'Ingredients' },
  { value: 'step', label: 'Step' },
]

export type BoundKey = `${'min' | 'max'}_${string}`

export interface Filters {
  k: number
  category: string[]
  kind: Kind[]
  bounds: Partial<Record<BoundKey, string>>
}

export const DEFAULT_FILTERS: Filters = { k: 5, category: [], kind: [], bounds: {} }

export function toParams(q: string, f: Filters): URLSearchParams {
  const p = new URLSearchParams({ q, k: String(f.k) })
  f.category.forEach(c => p.append('category', c))
  f.kind.forEach(k => p.append('kind', k))
  for (const [key, value] of Object.entries(f.bounds)) {
    if (value !== undefined && value.trim() !== '' && !Number.isNaN(Number(value))) p.append(key, value.trim())
  }
  return p
}

export interface Chip {
  id: string
  label: string
  remove: (f: Filters) => Filters
}

/** One removable chip per active Filter, in the order the Settings drawer lists them. */
export function activeChips(f: Filters): Chip[] {
  const chips: Chip[] = []
  for (const kind of f.kind) {
    chips.push({
      id: `kind-${kind}`,
      label: `${KINDS.find(k => k.value === kind)?.label} chunks`,
      remove: f => ({ ...f, kind: f.kind.filter(k => k !== kind) }),
    })
  }
  for (const c of f.category) {
    chips.push({ id: `cat-${c}`, label: c, remove: f => ({ ...f, category: f.category.filter(x => x !== c) }) })
  }
  for (const r of RANGES) {
    for (const bound of ['min', 'max'] as const) {
      const key: BoundKey = `${bound}_${r.column}`
      const value = f.bounds[key]?.trim()
      if (!value || Number.isNaN(Number(value))) continue
      chips.push({
        id: key,
        label: `${r.label} ${bound === 'min' ? '≥' : '≤'} ${value}${r.unit ? ` ${r.unit}` : ''}`,
        remove: f => {
          const bounds = { ...f.bounds }
          delete bounds[key]
          return { ...f, bounds }
        },
      })
    }
  }
  return chips
}
