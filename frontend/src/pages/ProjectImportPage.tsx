import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { Badge, Panel, StatCard } from '../components/ui'

export default function ProjectImportPage() {
  const qc = useQueryClient()
  const [url, setUrl] = useState('https://github.com/PranavSatya/Tanu')
  const [token, setToken] = useState('')
  const { data: project } = useQuery({ queryKey: ['github-project'], queryFn: api.githubProject, refetchInterval: 8000 })

  const importMut = useMutation({
    mutationFn: () => api.githubImport(url, token || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['github-project'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['services'] })
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      qc.invalidateQueries({ queryKey: ['knowledge-status'] })
    },
  })

  const clearMut = useMutation({
    mutationFn: api.githubClear,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['github-project'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['services'] })
    },
  })

  const refreshMut = useMutation({
    mutationFn: api.githubRefresh,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['github-project'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const result = importMut.data as any

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">GitHub Project</h1>
        <p className="text-sm text-slate-400">
          Paste a GitHub URL. The platform infers services and simulates metrics for that topology (A),
          and attaches real GitHub Actions / commits / issues as signals (B).
        </p>
      </div>

      <Panel title="Import repository">
        <div className="space-y-3">
          <input
            className="w-full rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
            placeholder="https://github.com/owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <input
            className="w-full rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
            placeholder="Optional GitHub token (private repos / higher rate limits)"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => importMut.mutate()}
              disabled={!url || importMut.isPending}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm hover:bg-indigo-500 disabled:opacity-50"
            >
              {importMut.isPending ? 'Importing & indexing…' : 'Import GitHub project'}
            </button>
            <button
              onClick={() => refreshMut.mutate()}
              disabled={!project?.active || refreshMut.isPending}
              className="rounded-md border border-[#1f2a3d] px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-50"
            >
              Refresh signals
            </button>
            <button
              onClick={() => clearMut.mutate()}
              className="rounded-md border border-[#1f2a3d] px-4 py-2 text-sm hover:bg-slate-800"
            >
              Clear / use demo defaults
            </button>
          </div>
          {importMut.isError && (
            <div className="text-sm text-rose-400">{(importMut.error as Error).message}</div>
          )}
          {result?.message && <div className="text-sm text-emerald-300">{result.message}</div>}
        </div>
      </Panel>

      {project?.active && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Active project" value={project.full_name} tone="ai" />
            <StatCard label="Inferred services" value={project.service_count} />
            <StatCard label="Docs indexed" value={project.docs_indexed ?? 0} />
            <StatCard
              label="Failed Actions"
              value={project.signals?.failed_workflow_count ?? 0}
              tone={project.signals?.failed_workflow_count ? 'warn' : 'ok'}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Repo">
              <div className="space-y-2 text-sm text-slate-300">
                <div>{project.description || 'No description'}</div>
                <div className="text-xs text-slate-500">
                  Language: {project.language || '—'} · Stars: {project.stars ?? 0} · Mode: {project.mode}
                </div>
                <a className="text-indigo-300 hover:underline" href={project.html_url} target="_blank" rel="noreferrer">
                  Open on GitHub →
                </a>
                <div className="pt-2">
                  <Link to="/simulation" className="text-sm text-indigo-300 hover:underline">
                    Run simulation on this topology →
                  </Link>
                </div>
              </div>
            </Panel>
            <Panel title="Real GitHub signals (B)">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Open issues</span>
                  <Badge tone="INFO">{project.signals?.open_issue_count ?? 0}</Badge>
                </div>
                <div className="flex justify-between">
                  <span>Open bugs</span>
                  <Badge tone={project.signals?.open_bug_count ? 'MEDIUM' : 'INFO'}>
                    {project.signals?.open_bug_count ?? 0}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span>Token used</span>
                  <span>{project.signals?.has_token ? 'yes' : 'no (public API)'}</span>
                </div>
                <div className="mt-3 max-h-40 space-y-1 overflow-auto text-xs text-slate-400">
                  {(project.signals?.workflows || [])
                    .filter((w: any) => !w.error)
                    .slice(0, 5)
                    .map((w: any) => (
                      <div key={w.id} className="flex justify-between gap-2 border-b border-[#1f2a3d]/60 py-1">
                        <span className="truncate">{w.name}</span>
                        <span>{w.conclusion || w.status}</span>
                      </div>
                    ))}
                  {(project.signals?.commits || [])
                    .filter((c: any) => !c.error)
                    .slice(0, 3)
                    .map((c: any) => (
                      <div key={c.sha} className="truncate py-1">
                        {c.sha} · {c.message}
                      </div>
                    ))}
                </div>
              </div>
            </Panel>
          </div>
          {result?.services && (
            <Panel title="Inferred service topology (A)">
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {result.services.map((s: any) => (
                  <div key={s.name} className="rounded border border-[#1f2a3d] px-3 py-2 text-sm">
                    <div className="font-medium">{s.display_name}</div>
                    <div className="text-xs text-slate-500">
                      {s.name} · {s.tier}
                    </div>
                    <div className="text-xs text-slate-500">deps: {(s.dependencies || []).join(', ') || '—'}</div>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </>
      )}

      {!project?.active && (
        <Panel>
          <p className="text-sm text-slate-400">
            No project imported yet. Until you import, the demo uses the default microservices topology.
            Try importing <code className="text-indigo-300">https://github.com/PranavSatya/Tanu</code>.
          </p>
        </Panel>
      )}
    </div>
  )
}
