import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Recommend from './Recommend.tsx'
import Report from './report/Report.tsx'

// No router: /report is the Report page, /diet the patient recommender, anything else the search page
// ("Page data contract").
const PAGES: Record<string, () => React.JSX.Element> = { '/report': Report, '/diet': Recommend }
const Page = PAGES[location.pathname.replace(/\/$/, '')] ?? App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
