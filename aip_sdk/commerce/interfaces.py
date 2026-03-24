from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REFUNDED = "refunded"


@dataclass
class JobSpec:
    job_id: str
    client_id: str
    description: str
    reward_amount: float
    reward_token: str
    evaluator_id: str
    expires_at: Optional[int] = None
    hook: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    client_id: str
    provider_id: Optional[str]
    evaluator_id: str
    reward_amount: float
    reward_token: str
    deliverable_hash: Optional[str] = None
    deliverable_uri: Optional[str] = None
    assertion_id: Optional[str] = None
    liveness_end: Optional[int] = None
    hook: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0


class BaseMarketDriver:
    """Abstract interface for all commerce drivers (on-chain or mock)."""

    async def create_job(self, spec: JobSpec) -> str:
        raise NotImplementedError

    async def accept_job(self, job_id: str, provider_id: str, chain_id: Optional[int] = None) -> bool:
        raise NotImplementedError

    async def submit_deliverable(
        self, job_id: str, provider_id: str, deliverable_hash: str, deliverable_uri: str, chain_id: Optional[int] = None
    ) -> bool:
        raise NotImplementedError

    async def complete_job(
        self, job_id: str, evaluator_id: str, reason_hash: str, chain_id: Optional[int] = None
    ) -> bool:
        raise NotImplementedError

    async def reject_job(
        self, job_id: str, rejector_id: str, reason_hash: str, chain_id: Optional[int] = None
    ) -> bool:
        raise NotImplementedError

    async def set_budget(self, job_id: str, amount: float, chain_id: Optional[int] = None) -> bool:
        raise NotImplementedError

    async def get_job(self, job_id: str, chain_id: Optional[int] = None) -> Optional[JobRecord]:
        raise NotImplementedError
