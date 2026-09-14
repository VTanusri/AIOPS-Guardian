from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import KnowledgeDocument, Service, User

SEED_SERVICES = [
    {
        "name": "api-gateway",
        "display_name": "API Gateway",
        "tier": "edge",
        "dependencies": ["order-service", "payment-service"],
    },
    {
        "name": "order-service",
        "display_name": "Order Service",
        "tier": "app",
        "dependencies": ["database", "inventory-service"],
    },
    {
        "name": "payment-service",
        "display_name": "Payment Service",
        "tier": "app",
        "dependencies": ["database", "external-payment"],
    },
    {
        "name": "inventory-service",
        "display_name": "Inventory Service",
        "tier": "app",
        "dependencies": ["database"],
    },
    {
        "name": "database",
        "display_name": "PostgreSQL Database",
        "tier": "data",
        "dependencies": [],
    },
    {
        "name": "external-payment",
        "display_name": "External Payment Provider",
        "tier": "external",
        "dependencies": [],
    },
    {
        "name": "cache",
        "display_name": "Redis Cache",
        "tier": "data",
        "dependencies": [],
    },
]


def seed_database(db: Session) -> None:
    if db.query(User).count() == 0:
        db.add(User(username="sre", display_name="SRE Operator", role="sre"))

    existing = {s.name for s in db.query(Service).all()}
    for svc in SEED_SERVICES:
        if svc["name"] not in existing:
            db.add(Service(**svc, status="healthy"))

    db.commit()
