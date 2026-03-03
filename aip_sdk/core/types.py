"""Type definitions for the framework."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class AgentType(Enum):
    """Agent type enumeration."""

    AIP = "aip"
    CLAUDE = "claude"
    LANGCHAIN = "langchain"
    OPENAI = "openai"
    CUSTOM = "custom"


class AgentIdentity(BaseModel):
    """Agent identity information."""

    model_config = ConfigDict(use_enum_values=True)

    agent_id: str
    name: str
    agent_type: AgentType
    public_key: Optional[str] = None
    wallet_address: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()


class MemoryRecord(BaseModel):
    """Memory record."""

    session_id: str
    agent_id: str
    content: Dict[str, Any]
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()


class DAUploadResult(BaseModel):
    """DA upload result."""

    transaction_hash: str
    da_url: str
    size: int
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()


# Config types
class LLMProviderConfig(TypedDict, total=False):
    """LLM provider configuration for adapters (Claude, OpenAI, LangChain)."""

    api_key: str
    base_url: str
    model: str
    timeout: float
    extra_params: Dict[str, Any]


class MemoryConfig(TypedDict, total=False):
    """Memory configuration."""

    membase_endpoint: str
    da_endpoint: str
    api_key: str
    encryption: bool
    retention_policy: str


class RegistryConfig(TypedDict, total=False):
    """Registry configuration."""

    aip_endpoint: str
    membase_endpoint: str
    web3_rpc_url: str
