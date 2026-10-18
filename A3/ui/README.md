# Recipe Search UI

React + Tailwind page that runs one query through the Sparse, Hybrid and Dense endpoints and shows the three rankings side by side. Lines join the same Chunk across columns (wide screens only). Filters, results per column, theme and service status are in the Settings drawer.

## Run the demo

Build once, then FastAPI serves the page at `/`:

```sh
cd ui && npm install && npm run build   # writes ../api/static
cd .. && uv run uvicorn api.main:app    # open http://localhost:8000
```

## Develop

Run the API and the Vite dev server side by side. Vite forwards API calls to `API_URL` (default `http://localhost:8000`):

```sh
uv run uvicorn api.main:app --reload --port 8001
cd ui && API_URL=http://localhost:8001 npm run dev
```

## Where things are

- `src/App.tsx`: search box, examples, active filter chips, the three columns
- `src/components/SettingsDrawer.tsx`: filters (edited as a draft until you press Apply), theme, service status
- `src/components/Connectors.tsx`: lines from each Hybrid card to the same Chunk in Sparse and Dense
- `src/filters.ts`: mirrors `SearchParams` in `api/filters.py`; add a filter in both places
- `src/index.css`: color tokens for light and dark
