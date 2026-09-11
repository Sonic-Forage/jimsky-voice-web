import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// LiveKit component styles carry the audio-visualizer and transcript primitives; the
// JIMSKY theme below overrides the palette without fighting the layout.
import '@livekit/components-styles'
import './styles.css'
import App from './App'

const el = document.getElementById('root')
if (!el) throw new Error('#root missing')
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
