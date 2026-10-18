import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ChatPage from './chat/ChatPage.tsx'
import Report from './report/Report.tsx'

// No router: /report is the Report page, /chat the chat assistant, anything else the search page ("Page data contract").
const path = location.pathname.replace(/\/$/, '')
const Page = path === '/report' ? Report : path === '/chat' ? ChatPage : App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
