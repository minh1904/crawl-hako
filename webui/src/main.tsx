import "@fontsource/be-vietnam-pro/400.css"
import "@fontsource/be-vietnam-pro/500.css"
import "@fontsource/be-vietnam-pro/600.css"
import "@fontsource-variable/literata"
import "@fontsource-variable/jetbrains-mono"
import "./index.css"

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { App } from "./App"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
