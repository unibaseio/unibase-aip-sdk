"""Unified Agent Card generation for A2A Protocol.

This module provides standardized Agent Card generation that aligns with:
- ERC-8004 metadata schema
- A2A SDK AgentCard type
- unibase-aip main repository unified builder

All agent card generation in the SDK should go through these functions
to ensure consistency with the main platform.
"""

from typing import Optional, List, Dict, Any

from a2a.types import (
    AgentCard,
    AgentSkillCard,
    AgentCapabilities,
    AgentProvider,
    AgentService,
)

from ..core.types import AgentIdentity


def _normalize_capabilities(capabilities: Optional[Dict[str, Any]] = None) -> AgentCapabilities:
    """Normalize capabilities to standard format."""
    if capabilities is None:
        capabilities = {}
    
    # Handle list format (e.g., ["streaming", "push"])
    if isinstance(capabilities, list):
        caps_list = capabilities
        return AgentCapabilities(
            streaming="streaming" in caps_list or "stream" in caps_list,
            pushNotifications="push" in caps_list or "notifications" in caps_list,
            stateTransitionHistory="history" in caps_list or "state" in caps_list,
        )
    
    return AgentCapabilities(
        streaming=capabilities.get("streaming", True),
        pushNotifications=capabilities.get("pushNotifications", False),
        stateTransitionHistory=capabilities.get("stateTransitionHistory", True),
    )


def _normalize_skills(
    skills: Optional[List[Dict[str, Any]]] = None,
    handle: Optional[str] = None,
) -> List[AgentSkillCard]:
    """Normalize skills to standard format."""
    result = []
    
    for skill in (skills or []):
        if isinstance(skill, AgentSkillCard):
            result.append(skill)
        elif isinstance(skill, dict):
            skill_name = skill.get("name", "skill")
            result.append(AgentSkillCard(
                id=skill.get("id") or (f"{handle}:{skill_name}" if handle else None),
                name=skill_name,
                description=skill.get("description") or skill_name,
                tags=skill.get("tags", []),
                examples=skill.get("examples", []),
                inputModes=skill.get("inputModes", ["text/plain"]),
                outputModes=skill.get("outputModes", ["application/json"]),
            ))
    
    return result


def generate_agent_card(
    identity: AgentIdentity,
    base_url: str,
    description: Optional[str] = None,
    skills: Optional[List[AgentSkillCard]] = None,
    capabilities: Optional[AgentCapabilities] = None,
    provider: Optional[AgentProvider] = None,
    version: str = "1.0.0",
) -> AgentCard:
    """Generate an A2A Agent Card from AgentIdentity.
    
    This is the standard function for generating Agent Cards in the SDK.
    It ensures consistency with the main platform's unified builder.
    
    Args:
        identity: AgentIdentity with agent metadata
        base_url: Base URL where the agent is hosted
        description: Optional description override
        skills: Optional list of skills
        capabilities: Optional capabilities override
        provider: Optional provider info
        version: Agent version string
    
    Returns:
        AgentCard ready for A2A discovery
    """
    # Normalize base URL (remove trailing slash)
    base_url = base_url.rstrip("/")

    # Default description from identity metadata
    if description is None:
        description = identity.metadata.get("description")
        if not description:
            description = f"AI agent: {identity.name}"

    # Normalize capabilities
    raw_caps = identity.metadata.get("capabilities")
    normalized_caps = _normalize_capabilities(capabilities) if capabilities else _normalize_capabilities(raw_caps)

    # Build services
    skills_list = _normalize_skills(skills, handle=identity.agent_id)
    
    # If no skills provided, try to get from identity metadata
    if not skills_list:
        metadata_skills = identity.metadata.get("skills", [])
        skills_list = _normalize_skills(metadata_skills, handle=identity.agent_id)
        
        # Fallback to default skill
        if not skills_list:
            skills_list = [AgentSkillCard(
                id=f"{identity.agent_id}-default",
                name=identity.name,
                description=description,
                tags=[identity.agent_type.value, "unibase"] if hasattr(identity, 'agent_type') else ["unibase"],
            )]

    # Build the agent card
    card = AgentCard(
        name=identity.name,
        description=description,
        url=base_url,
        version=version,
        capabilities=normalized_caps,
        skills=skills_list,
        provider=provider,
        services=[
            AgentService(
                name="A2A", 
                endpoint=f"{base_url}/.well-known/agent-card.json",
                a2aSkills=[s.name for s in skills_list]
            ),
            AgentService(name="web", endpoint=base_url)
        ],
        defaultInputModes=["text/plain", "application/json"],
        defaultOutputModes=["text/plain", "application/json"],
    )

    return card


def agent_card_from_metadata(
    metadata: Dict[str, Any],
    base_url: str
) -> AgentCard:
    """Generate an Agent Card from raw metadata dictionary.
    
    This function handles various metadata formats and normalizes them
    to the standard AgentCard format.
    
    Args:
        metadata: Raw metadata dictionary (from DB, config, etc.)
        base_url: Base URL where the agent is hosted
    
    Returns:
        Standardized AgentCard
    """
    base_url = base_url.rstrip("/")
    
    # Extract name
    name = metadata.get("name") or metadata.get("agent_name") or "agent"
    
    # Normalize skills
    skills_list = _normalize_skills(metadata.get("skills"), handle=name)
    
    # If no skills, check for tasks
    if not skills_list:
        tasks = metadata.get("tasks", [])
        for task in tasks:
            if isinstance(task, dict):
                task_name = task.get("name", "task")
                skills_list.append(AgentSkillCard(
                    id=task.get("id") or f"{name}:{task_name}",
                    name=task_name,
                    description=task.get("description") or task_name,
                    tags=task.get("tags", []),
                ))
    
    # Normalize capabilities
    capabilities = _normalize_capabilities(metadata.get("capabilities"))
    
    # Build provider
    provider = None
    if metadata.get("provider"):
        provider = AgentProvider(
            organization=metadata["provider"].get("organization", "Unibase"),
            url=metadata["provider"].get("url")
        )

    # Build description
    description = (
        metadata.get("description") or 
        metadata.get("intro") or 
        f"AI agent: {name}"
    )

    # Build card
    card = AgentCard(
        name=name,
        description=description,
        url=base_url,
        version=metadata.get("version", "1.0.0"),
        capabilities=capabilities,
        skills=skills_list,
        provider=provider,
        services=[
            AgentService(
                name="A2A", 
                endpoint=f"{base_url}/.well-known/agent-card.json",
                a2aSkills=[s.name for s in skills_list]
            ),
            AgentService(name="web", endpoint=base_url)
        ],
        defaultInputModes=metadata.get("defaultInputModes", ["text/plain", "application/json"]),
        defaultOutputModes=metadata.get("defaultOutputModes", ["text/plain", "application/json"]),
    )

    return card


__all__ = [
    "generate_agent_card",
    "agent_card_from_metadata",
]
