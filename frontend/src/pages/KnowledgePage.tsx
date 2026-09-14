import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Loading, Panel, StatCard } from '../components/ui'

export default function KnowledgePage() {
  const qc = useQueryClient()
  const { data: docs, isLoading } = useQuery({ queryKey: ['knowledge'], queryFn: api.knowledge })
  const { data: status } = useQuery({ queryKey: ['knowledge-status'], queryFn: api.knowledgeStatus, refetchInterval: 10000 })
  const [query, setQuery] = useState('database connection pool exhaustion')
  const [hits, setHits] = useState<any[]>([])

  const reindex = useMutation({
    mutationFn: api.reindex,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      qc.invalidateQueries({ queryKey: ['knowledge-status'] })
    },
  })

  const search = useMutation({
    mutationFn: () => api.ragSearch(query),
    onSuccess: (data: any) => setHits(data),
  })

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/knowledge/upload', { method: 'POST', body: fd })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      qc.invalidateQueries({ queryKey: ['knowledge-status'] })
    },
  })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Knowledge Base</h1>
        <p className="text-sm text-slate-400">Runbooks embedded with all-MiniLM-L6-v2 into ChromaDB.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Documents" value={status?.total_documents ?? '—'} />
        <StatCard label="Chunks" value={status?.total_chunks ?? '—'} />
        <StatCard label="Embedding model" value={status?.embedding_model ?? '—'} />
        <StatCard label="Vector DB" value={status?.vector_db_status ?? '—'} tone="ai" />
        <StatCard
          label="Last indexed"
          value={status?.last_indexing_time ? new Date(status.last_indexing_time).toLocaleString() : '—'}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => reindex.mutate()}
          className="rounded-md bg-indigo-600 px-3 py-2 text-sm hover:bg-indigo-500"
        >
          {reindex.isPending ? 'Reindexing…' : 'Rebuild index'}
        </button>
        <label className="cursor-pointer rounded-md border border-[#1f2a3d] px-3 py-2 text-sm hover:bg-slate-800">
          Upload .md/.txt
          <input
            type="file"
            accept=".md,.txt,text/plain,text/markdown"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) upload.mutate(f)
            }}
          />
        </label>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Documents">
          {isLoading ? (
            <Loading />
          ) : (
            <div className="space-y-2 text-sm">
              {(docs || []).map((d: any) => (
                <div key={d.id} className="flex items-center justify-between rounded border border-[#1f2a3d] px-3 py-2">
                  <div>
                    <div className="font-medium">{d.title}</div>
                    <div className="text-xs text-slate-500">
                      {d.filename} · {d.chunk_count} chunks · {d.doc_type}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="Semantic search">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button
              onClick={() => search.mutate()}
              className="rounded-md bg-slate-700 px-3 py-2 text-sm hover:bg-slate-600"
            >
              Search
            </button>
          </div>
          <div className="mt-3 space-y-2">
            {hits.map((h, i) => (
              <div key={i} className="rounded border border-[#1f2a3d] p-3 text-sm">
                <div className="font-medium text-indigo-200">
                  {h.title} · {h.score}
                </div>
                <p className="mt-1 text-slate-400">{h.content.slice(0, 220)}…</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}
