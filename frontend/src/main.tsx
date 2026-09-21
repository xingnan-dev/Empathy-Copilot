import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { DemoHostShell } from './demo/DemoHostShell'
import './design-system/tokens.css'
import './design-system/typography.css'
import './design-system/surfaces.css'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DemoHostShell />
  </StrictMode>,
)
