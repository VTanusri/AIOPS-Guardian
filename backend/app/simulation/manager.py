from __future__ import annotations

import asyncio
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.events import event_bus
from app.telemetry import generator as telem

SCENARIOS: dict[str, dict[str, Any]] = {
    "db_pool_exhaustion": {
        "name": "Database Connection Pool Exhaustion",
        "description": "DB connections ramp to saturation, then timeouts and API errors follow.",
        "steps": [
            {"overrides": {"database": {"db_connection_usage": 55}}, "logs": []},
            {"overrides": {"database": {"db_connection_usage": 65}}, "logs": []},
            {"overrides": {"database": {"db_connection_usage": 75, "db_latency": 35}}, "logs": []},
            {
                "overrides": {
                    "database": {"db_connection_usage": 85, "db_latency": 60},
                    "api-gateway": {"api_latency": 220},
                },
                "logs": [
                    {
                        "severity": "WARN",
                        "service": "database",
                        "message": "Connection pool usage high (85%)",
                    }
                ],
            },
            {
                "overrides": {
                    "database": {"db_connection_usage": 95, "db_latency": 120},
                    "api-gateway": {"api_latency": 380, "error_rate": 8},
                    "order-service": {"api_latency": 350, "error_rate": 7},
                },
                "logs": [
                    {
                        "severity": "ERROR",
                        "service": "database",
                        "message": "FATAL: remaining connection slots reserved / pool timeout",
                    },
                    {
                        "severity": "ERROR",
                        "service": "order-service",
                        "message": "Database timeout while acquiring connection",
                    },
                ],
            },
            {
                "overrides": {
                    "database": {"db_connection_usage": 99, "db_latency": 200},
                    "api-gateway": {"api_latency": 520, "error_rate": 15},
                    "order-service": {"api_latency": 480, "error_rate": 14},
                    "payment-service": {"api_latency": 400, "error_rate": 10},
                },
                "logs": [
                    {
                        "severity": "ERROR",
                        "service": "api-gateway",
                        "message": "HTTP 500 upstream timeout from order-service",
                    },
                    {
                        "severity": "ERROR",
                        "service": "payment-service",
                        "message": "Downstream timeout waiting on database",
                    },
                ],
            },
        ],
    },
    "high_api_latency": {
        "name": "High API Latency",
        "description": "API latency climbs across gateway and order service.",
        "steps": [
            {"overrides": {"api-gateway": {"api_latency": 160}}, "logs": []},
            {"overrides": {"api-gateway": {"api_latency": 240}, "order-service": {"api_latency": 220}}, "logs": []},
            {
                "overrides": {
                    "api-gateway": {"api_latency": 360},
                    "order-service": {"api_latency": 340},
                    "database": {"db_latency": 45},
                },
                "logs": [{"severity": "WARN", "service": "api-gateway", "message": "p99 latency breach"}],
            },
            {
                "overrides": {
                    "api-gateway": {"api_latency": 480, "error_rate": 4},
                    "order-service": {"api_latency": 450},
                },
                "logs": [{"severity": "ERROR", "service": "order-service", "message": "Slow handler exceeded SLO"}],
            },
        ],
    },
    "high_error_rate": {
        "name": "High Error Rate",
        "description": "HTTP errors spike without immediate DB saturation.",
        "steps": [
            {"overrides": {"api-gateway": {"error_rate": 3}}, "logs": []},
            {"overrides": {"api-gateway": {"error_rate": 7}, "order-service": {"error_rate": 6}}, "logs": []},
            {
                "overrides": {"api-gateway": {"error_rate": 12}, "order-service": {"error_rate": 11}},
                "logs": [{"severity": "ERROR", "service": "order-service", "message": "Unhandled NullPointerException in checkout"}],
            },
            {
                "overrides": {"api-gateway": {"error_rate": 18, "api_latency": 300}},
                "logs": [{"severity": "ERROR", "service": "api-gateway", "message": "Elevated 5xx responses"}],
            },
        ],
    },
    "memory_leak": {
        "name": "Memory Leak",
        "description": "Memory utilization grows steadily toward exhaustion.",
        "steps": [
            {"overrides": {"order-service": {"memory_utilization": 70}}, "logs": []},
            {"overrides": {"order-service": {"memory_utilization": 80, "cpu_utilization": 55}}, "logs": []},
            {
                "overrides": {"order-service": {"memory_utilization": 90, "api_latency": 280}},
                "logs": [{"severity": "WARN", "service": "order-service", "message": "GC overhead increasing"}],
            },
            {
                "overrides": {"order-service": {"memory_utilization": 97, "error_rate": 6, "api_latency": 400}},
                "logs": [{"severity": "ERROR", "service": "order-service", "message": "OutOfMemoryError risk — heap nearly full"}],
            },
        ],
    },
    "disk_full": {
        "name": "Disk Full",
        "description": "Disk utilization approaches capacity on database host.",
        "steps": [
            {"overrides": {"database": {"disk_utilization": 82}}, "logs": []},
            {"overrides": {"database": {"disk_utilization": 90, "db_latency": 40}}, "logs": []},
            {
                "overrides": {"database": {"disk_utilization": 96, "db_latency": 90}, "order-service": {"error_rate": 5}},
                "logs": [{"severity": "ERROR", "service": "database", "message": "No space left on device"}],
            },
            {
                "overrides": {"database": {"disk_utilization": 99, "db_latency": 150}, "api-gateway": {"error_rate": 9}},
                "logs": [{"severity": "ERROR", "service": "database", "message": "Write failed: disk full"}],
            },
        ],
    },
    "network_failure": {
        "name": "Network Failure",
        "description": "Network degradation impacts external payment path.",
        "steps": [
            {"overrides": {"external-payment": {"network_utilization": 70, "api_latency": 300}}, "logs": []},
            {
                "overrides": {
                    "external-payment": {"network_utilization": 88, "api_latency": 500, "error_rate": 8},
                    "payment-service": {"api_latency": 420, "error_rate": 6},
                },
                "logs": [{"severity": "WARN", "service": "payment-service", "message": "Elevated latency to external payment"}],
            },
            {
                "overrides": {
                    "external-payment": {"network_utilization": 95, "error_rate": 20, "api_latency": 900},
                    "payment-service": {"error_rate": 15, "api_latency": 700},
                    "api-gateway": {"error_rate": 8},
                },
                "logs": [
                    {"severity": "ERROR", "service": "external-payment", "message": "Connection reset by peer"},
                    {"severity": "ERROR", "service": "payment-service", "message": "Downstream network failure"},
                ],
            },
        ],
    },
}


class SimulationManager:
    def __init__(self) -> None:
        self.running = False
        self.scenario: Optional[str] = None
        self.step = 0
        self.total_steps = 0
        self.message = "idle"
        self._task: Optional[asyncio.Task] = None

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "scenario": self.scenario,
            "step": self.step,
            "total_steps": self.total_steps,
            "message": self.message,
        }

    async def start(self, scenario: str) -> dict[str, Any]:
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        await self.stop()
        self.running = True
        self.scenario = scenario
        self.step = 0
        self.total_steps = len(SCENARIOS[scenario]["steps"])
        self.message = f"Starting {SCENARIOS[scenario]['name']}"
        self._task = asyncio.create_task(self._run(scenario))
        await event_bus.publish("simulation", {"type": "started", **self.status()})
        return self.status()

    async def stop(self) -> dict[str, Any]:
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        telem.clear_simulation_overrides()
        self.message = "stopped"
        await event_bus.publish("simulation", {"type": "stopped", **self.status()})
        return self.status()

    async def reset(self) -> dict[str, Any]:
        await self.stop()
        self.scenario = None
        self.step = 0
        self.total_steps = 0
        self.message = "reset"
        await event_bus.publish("simulation", {"type": "reset", **self.status()})
        return self.status()

    async def _run(self, scenario: str) -> None:
        steps = SCENARIOS[scenario]["steps"]
        try:
            for i, step in enumerate(steps, start=1):
                if not self.running:
                    break
                self.step = i
                telem.set_simulation_overrides(step["overrides"])
                if step.get("logs"):
                    telem.enqueue_sim_logs(list(step["logs"]))
                self.message = f"Step {i}/{len(steps)} applied"
                await event_bus.publish(
                    "simulation",
                    {"type": "step", **self.status(), "overrides": step["overrides"]},
                )
                await asyncio.sleep(4)
            self.message = "scenario complete — pipeline will continue with live telemetry"
            self.running = False
            await event_bus.publish("simulation", {"type": "completed", **self.status()})
        except asyncio.CancelledError:
            raise


simulation_manager = SimulationManager()


def _service_aliases() -> dict[str, str]:
    """Map classic demo service names onto the active GitHub-derived topology."""
    baseline = telem.get_baseline()
    names = list(baseline.keys())
    edge = next((n for n, m in baseline.items() if "api_latency" in m and n != "database"), names[0] if names else "app")
    apps = [n for n in names if n not in {"database", "cache", edge}]
    app1 = apps[0] if apps else edge
    app2 = apps[1] if len(apps) > 1 else app1
    return {
        "api-gateway": edge,
        "order-service": app1,
        "payment-service": app2,
        "inventory-service": app1,
        "external-payment": app2,
        "database": "database" if "database" in baseline else names[-1],
        "cache": "cache" if "cache" in baseline else app1,
    }


def _remap_step(step: dict[str, Any]) -> dict[str, Any]:
    aliases = _service_aliases()
    overrides: dict[str, dict[str, float]] = {}
    for svc, metrics in (step.get("overrides") or {}).items():
        target = aliases.get(svc, svc)
        if target not in telem.get_baseline():
            # skip metrics for missing services; keep if metric exists on any service
            continue
        allowed = telem.get_baseline().get(target, {})
        filtered = {k: v for k, v in metrics.items() if k in allowed}
        if not filtered and metrics:
            # if exact metrics missing, map latency/error onto available keys
            for k, v in metrics.items():
                if k in allowed:
                    filtered[k] = v
                elif "latency" in k and "api_latency" in allowed:
                    filtered["api_latency"] = v
                elif k == "error_rate" and "error_rate" in allowed:
                    filtered["error_rate"] = v
        if filtered:
            overrides.setdefault(target, {}).update(filtered)
    logs = []
    for log in step.get("logs") or []:
        svc = aliases.get(log.get("service", ""), log.get("service", "app"))
        logs.append({**log, "service": svc})
    return {"overrides": overrides, "logs": logs}


# patch run loop to remap
_original_run = SimulationManager._run


async def _run_remapped(self, scenario: str) -> None:
    steps = SCENARIOS[scenario]["steps"]
    try:
        for i, step in enumerate(steps, start=1):
            if not self.running:
                break
            self.step = i
            mapped = _remap_step(step)
            telem.set_simulation_overrides(mapped["overrides"])
            if mapped.get("logs"):
                telem.enqueue_sim_logs(list(mapped["logs"]))
            self.message = f"Step {i}/{len(steps)} applied"
            await event_bus.publish(
                "simulation",
                {"type": "step", **self.status(), "overrides": mapped["overrides"]},
            )
            await asyncio.sleep(4)
        self.message = "scenario complete — pipeline will continue with live telemetry"
        self.running = False
        await event_bus.publish("simulation", {"type": "completed", **self.status()})
    except asyncio.CancelledError:
        raise


SimulationManager._run = _run_remapped


def list_scenarios() -> list[dict[str, str]]:
    return [
        {"key": key, "name": val["name"], "description": val["description"]}
        for key, val in SCENARIOS.items()
    ]
