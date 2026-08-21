/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the API backend. Empty = same origin (local / FastAPI-served build).
   *  Set to the Render URL when the frontend is deployed separately (Vercel). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
