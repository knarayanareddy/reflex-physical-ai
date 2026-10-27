import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
// The design tokens first: `app.css` refers to every colour and font through var(--…), and until
// 2026-10-27 nothing imported this file, so every variable resolved to nothing and the dashboard
// rendered as an unstyled white page (an opaque black keep-out volume, no red/green semantics).
// `tokens.css` itself is untouched — it is owned by the design system; only the import was missing.
import './tokens.css'
import './styles/app.css'

const container = document.getElementById('root')
if (!container) throw new Error('#root missing from index.html')

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
