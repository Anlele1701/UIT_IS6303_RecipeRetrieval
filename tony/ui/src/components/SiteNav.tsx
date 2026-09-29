// Links between the search page, the Report page and the API docs FastAPI serves at /docs.
const LINKS = [
  { href: '/', label: 'Search' },
  { href: '/report', label: 'Report' },
  { href: '/docs', label: 'API' },
] as const

export function SiteNav({ current }: { current: '/' | '/report' }) {
  return (
    <nav aria-label="Pages" className="flex items-center gap-1 text-sm">
      {LINKS.map(l => (
        <a
          key={l.href}
          href={l.href}
          aria-current={l.href === current ? 'page' : undefined}
          className={`rounded-md px-3 py-1.5 ${
            l.href === current ? 'bg-page font-medium text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          {l.label}
        </a>
      ))}
    </nav>
  )
}
