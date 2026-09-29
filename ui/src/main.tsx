import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Report from './report/Report.tsx'

// No router: /report is the Report page, anything else the search page ("Page data contract").
const Page = location.pathname.replace(/\/$/, '') === '/report' ? Report : App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
