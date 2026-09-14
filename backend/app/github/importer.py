from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.core.config import get_settings

GITHUB_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> tuple[str, str]:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    m = GITHUB_URL_RE.match(url)
    if not m:
        # also allow owner/repo shorthand
        parts = url.split("/")
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
        raise ValueError("Invalid GitHub URL. Use https://github.com/owner/repo")
    return m.group("owner"), m.group("repo")


@dataclass
class InferredService:
    name: str
    display_name: str
    tier: str
    dependencies: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def _default_app_metrics() -> dict[str, float]:
    return {
        "cpu_utilization": 28,
        "memory_utilization": 45,
        "request_rate": 80,
        "error_rate": 0.4,
        "api_latency": 100,
        "network_utilization": 30,
    }


def _default_db_metrics() -> dict[str, float]:
    return {
        "cpu_utilization": 35,
        "memory_utilization": 55,
        "db_connection_usage": 45,
        "db_latency": 12,
        "disk_utilization": 48,
        "error_rate": 0.1,
    }


def _default_cache_metrics() -> dict[str, float]:
    return {
        "cpu_utilization": 18,
        "memory_utilization": 60,
        "network_utilization": 25,
    }


FOLDER_HINTS = {
    "backend": ("backend", "Backend API", "app"),
    "api": ("api", "API Service", "app"),
    "server": ("server", "Server", "app"),
    "frontend": ("frontend", "Frontend", "edge"),
    "web": ("web", "Web App", "edge"),
    "client": ("client", "Client", "edge"),
    "worker": ("worker", "Background Worker", "app"),
    "jobs": ("jobs", "Job Runner", "app"),
    "gateway": ("api-gateway", "API Gateway", "edge"),
    "services": None,  # explore children later
}


class GitHubClient:
    def __init__(self, token: Optional[str] = None) -> None:
        settings = get_settings()
        self.token = token or settings.github_token or None
        self.base = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AIOps-Guardian",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_json(self, path: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30.0, headers=self._headers()) as client:
            resp = await client.get(f"{self.base}{path}", params=params or {})
            if resp.status_code == 404:
                raise ValueError("Repository not found or private (set GITHUB_TOKEN for private repos)")
            if resp.status_code == 403:
                raise ValueError("GitHub API rate limited or forbidden. Set GITHUB_TOKEN in .env")
            resp.raise_for_status()
            return resp.json()

    async def get_text(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=30.0, headers=self._headers(), follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text


def infer_services_from_tree(paths: list[str], languages: dict[str, int] | None = None) -> list[InferredService]:
    """Infer a service topology from repository paths (A — repo-aware)."""
    top_dirs = sorted({p.split("/")[0] for p in paths if "/" in p or p.endswith("/")})
    top_files = {p for p in paths if "/" not in p}

    services: dict[str, InferredService] = {}

    for d in top_dirs:
        key = d.lower().rstrip("/")
        hint = FOLDER_HINTS.get(key)
        if hint:
            name, display, tier = hint
            services[name] = InferredService(
                name=name,
                display_name=display,
                tier=tier,
                metrics=_default_app_metrics(),
            )

    # monorepo packages/
    for p in paths:
        if p.startswith("packages/") and p.count("/") >= 1:
            pkg = p.split("/")[1]
            if pkg and pkg not in services:
                services[pkg] = InferredService(
                    name=pkg.lower().replace(" ", "-"),
                    display_name=pkg.title(),
                    tier="app",
                    metrics=_default_app_metrics(),
                )

    # docker-compose hints from filenames
    compose_names = [p for p in top_files if "docker-compose" in p.lower() or p == "compose.yaml"]
    has_compose = bool(compose_names) or any("docker-compose" in p for p in paths)

    # language-based defaults if nothing found
    if not services:
        langs = languages or {}
        primary = max(langs, key=langs.get) if langs else "Unknown"
        services["app"] = InferredService(
            name="app",
            display_name=f"{primary} Application",
            tier="app",
            metrics=_default_app_metrics(),
        )
        if any(f in top_files for f in ("package.json", "vite.config.ts", "next.config.js")):
            services["web"] = InferredService(
                name="web",
                display_name="Web Frontend",
                tier="edge",
                metrics=_default_app_metrics(),
            )

    # Always attach shared infra for AIOps demo realism
    services["database"] = InferredService(
        name="database",
        display_name="Database",
        tier="data",
        metrics=_default_db_metrics(),
    )
    if has_compose or "redis" in " ".join(paths).lower() or "cache" in top_dirs:
        services["cache"] = InferredService(
            name="cache",
            display_name="Cache",
            tier="data",
            metrics=_default_cache_metrics(),
        )

    # Wire dependencies: edge/app → database
    app_names = [s.name for s in services.values() if s.tier in {"app", "edge"}]
    for s in services.values():
        if s.name == "database":
            continue
        deps = []
        if s.tier in {"app", "edge"} and "database" in services:
            deps.append("database")
        if s.tier == "edge":
            # edge depends on first non-edge app if present
            for a in app_names:
                if a != s.name and services[a].tier == "app":
                    deps.append(a)
                    break
        if "cache" in services and s.tier == "app":
            deps.append("cache")
        s.dependencies = sorted(set(deps))

    return list(services.values())


async def fetch_repo_bundle(url: str, token: Optional[str] = None) -> dict[str, Any]:
    """Fetch repo metadata + tree + docs + real GitHub signals (A+B)."""
    owner, repo = parse_github_url(url)
    client = GitHubClient(token=token)

    meta = await client.get_json(f"/repos/{owner}/{repo}")
    default_branch = meta.get("default_branch") or "main"

    # recursive tree (truncated for large repos)
    tree_payload = await client.get_json(
        f"/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )
    tree = tree_payload.get("tree") or []
    paths = [t["path"] for t in tree if t.get("path")][:4000]

    languages = await client.get_json(f"/repos/{owner}/{repo}/languages")

    # README
    readme_text = ""
    try:
        readme_meta = await client.get_json(f"/repos/{owner}/{repo}/readme")
        download = readme_meta.get("download_url")
        if download:
            readme_text = await client.get_text(download)
    except Exception:
        readme_text = meta.get("description") or ""

    # Collect a few markdown docs
    doc_paths = [
        p
        for p in paths
        if p.lower().endswith((".md", ".txt"))
        and any(seg in p.lower() for seg in ("readme", "docs/", "doc/", "runbook", "ops", "architecture"))
    ][:12]

    docs: list[dict[str, str]] = []
    if readme_text:
        docs.append(
            {
                "id": f"github_{owner}_{repo}_readme",
                "title": f"{owner}/{repo} README",
                "content": readme_text[:50000],
                "source": f"github:{owner}/{repo}/README",
            }
        )

    for p in doc_paths:
        if p.lower() in {"readme.md", "readme"}:
            continue
        try:
            content_meta = await client.get_json(f"/repos/{owner}/{repo}/contents/{p}")
            if isinstance(content_meta, dict) and content_meta.get("download_url"):
                text = await client.get_text(content_meta["download_url"])
                docs.append(
                    {
                        "id": f"github_{owner}_{repo}_{p.replace('/', '_')}",
                        "title": f"{repo}/{p}",
                        "content": text[:30000],
                        "source": f"github:{owner}/{repo}/{p}",
                    }
                )
        except Exception:
            continue

    services = infer_services_from_tree(paths, languages=languages)

    # --- Real signals (B) ---
    workflows: list[dict[str, Any]] = []
    commits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    try:
        runs = await client.get_json(
            f"/repos/{owner}/{repo}/actions/runs",
            params={"per_page": 8},
        )
        for run in runs.get("workflow_runs") or []:
            workflows.append(
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "html_url": run.get("html_url"),
                    "created_at": run.get("created_at"),
                    "head_branch": run.get("head_branch"),
                }
            )
    except Exception as exc:
        workflows = [{"error": str(exc)}]

    try:
        commit_rows = await client.get_json(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": 8},
        )
        for c in commit_rows or []:
            commits.append(
                {
                    "sha": (c.get("sha") or "")[:7],
                    "message": (c.get("commit") or {}).get("message", "").split("\n")[0][:160],
                    "author": ((c.get("commit") or {}).get("author") or {}).get("name"),
                    "date": ((c.get("commit") or {}).get("author") or {}).get("date"),
                    "html_url": c.get("html_url"),
                }
            )
    except Exception as exc:
        commits = [{"error": str(exc)}]

    try:
        issue_rows = await client.get_json(
            f"/repos/{owner}/{repo}/issues",
            params={"state": "open", "per_page": 8},
        )
        for i in issue_rows or []:
            if i.get("pull_request"):
                continue
            issues.append(
                {
                    "number": i.get("number"),
                    "title": i.get("title"),
                    "html_url": i.get("html_url"),
                    "created_at": i.get("created_at"),
                    "labels": [lb.get("name") for lb in (i.get("labels") or [])],
                }
            )
    except Exception as exc:
        issues = [{"error": str(exc)}]

    failed_runs = [w for w in workflows if w.get("conclusion") in {"failure", "timed_out", "cancelled"}]
    open_bugs = [i for i in issues if any("bug" in (l or "").lower() for l in i.get("labels") or [])]

    return {
        "owner": owner,
        "repo": repo,
        "full_name": meta.get("full_name") or f"{owner}/{repo}",
        "html_url": meta.get("html_url") or f"https://github.com/{owner}/{repo}",
        "description": meta.get("description") or "",
        "default_branch": default_branch,
        "stars": meta.get("stargazers_count") or 0,
        "language": meta.get("language"),
        "languages": languages,
        "topics": meta.get("topics") or [],
        "private": bool(meta.get("private")),
        "services": [
            {
                "name": s.name,
                "display_name": s.display_name,
                "tier": s.tier,
                "dependencies": s.dependencies,
                "metrics": s.metrics,
            }
            for s in services
        ],
        "docs_indexed": len(docs),
        "docs": docs,
        "signals": {
            "workflows": workflows,
            "commits": commits,
            "issues": issues,
            "failed_workflow_count": len(failed_runs),
            "open_issue_count": len([i for i in issues if "error" not in i]),
            "open_bug_count": len(open_bugs),
            "has_token": bool(client.token),
        },
        "mode": "combined_a_b",
    }
