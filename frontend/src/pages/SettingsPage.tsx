import { Panel } from '../components/ui'

export default function SettingsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Panel title="Runtime">
        <ul className="space-y-2 text-sm text-slate-300">
          <li>Default LLM: Ollama (`llama3.2`) when available, otherwise MockLLMProvider</li>
          <li>Embeddings: `all-MiniLM-L6-v2` via Sentence Transformers</li>
          <li>Vector store: ChromaDB (persistent under knowledge_base/chroma_db)</li>
          <li>Database: SQLite locally / PostgreSQL in Docker Compose</li>
          <li>Configure via `.env` — see repository `.env.example`</li>
        </ul>
      </Panel>
    </div>
  )
}
