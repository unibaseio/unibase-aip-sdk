"""Registry module - Thin wrapper around AIP SDK for agent management."""

from .registry import AgentRegistryClient, RegistrationMode

__all__ = [
    "AgentRegistryClient",
    "RegistrationMode",
]
