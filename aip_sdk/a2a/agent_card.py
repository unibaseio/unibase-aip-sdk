"""Agent Card generation from AgentIdentity."""

from typing import Optional, List, Dict, Any

# Import directly from Google A2A SDK
from a2a.types import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    AgentProvider,
    AgentInterface,
)

from ..core.types import AgentIdentity


def generate_agent_card(
    identity: AgentIdentity,
    base_url: str,
    description: Optional[str] = None,
    skills: Optional[List[AgentSkill]] = None,
    capabilities: Optional[AgentCapabilities] = None,
    provider: Optional[AgentProvider] = None,
    version: str = "1.0.0",
) -> AgentCard:
    """Generate an A2A Agent Card from AgentIdentity."""
    # Normalize base URL (remove trailing slash)
    base_url = base_url.rstrip("/")

    # Default description from identity name
    if description is None:
        description = f"AI agent: {identity.name}"
        if identity.metadata.get("description"):
            description = identity.metadata["description"]

    # Default capabilities
    if capabilities is None:
        capabilities = AgentCapabilities(
            streaming=True,
            pushNotifications=False,
            stateTransitionHistory=True
        )

    # Default skill from identity metadata if none provided
    if skills is None:
        skills = []
        # Check if identity has skill metadata
        if identity.metadata.get("skills"):
            for skill_data in identity.metadata["skills"]:
                skills.append(AgentSkill(
                    id=skill_data.get("id", f"{identity.name.lower()}-skill"),
                    name=skill_data.get("name", identity.name),
                    description=skill_data.get("description", description),
                    tags=skill_data.get("tags", []),
                    examples=skill_data.get("examples"),
                ))
        else:
            # Create a default skill
            skills.append(AgentSkill(
                id=f"{identity.agent_id}-default",
                name=identity.name,
                description=description,
                tags=[identity.agent_type.value, "unibase"],
            ))

    # Build the agent card
    card = AgentCard(
        name=identity.name,
        description=description,
        url=base_url,
        version=version,
        capabilities=capabilities,
        skills=skills,
        provider=provider,
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
    )

    return card


def agent_card_from_metadata(
    metadata: Dict[str, Any],
    base_url: str
) -> AgentCard:
    """Generate an Agent Card from raw metadata dictionary."""
    skills = []
    for skill_data in metadata.get("skills", []):
        skills.append(AgentSkill(
            id=skill_data["id"],
            name=skill_data["name"],
            description=skill_data["description"],
            tags=skill_data.get("tags", []),
            examples=skill_data.get("examples"),
        ))

    capabilities = AgentCapabilities(
        streaming=metadata.get("capabilities", {}).get("streaming", True),
        pushNotifications=metadata.get("capabilities", {}).get("push_notifications", False),
        stateTransitionHistory=metadata.get("capabilities", {}).get("state_transition_history", True)
    )

    provider = None
    if metadata.get("provider"):
        provider = AgentProvider(
            organization=metadata["provider"]["organization"],
            url=metadata["provider"].get("url")
        )

    return AgentCard(
        name=metadata["name"],
        description=metadata.get("description", f"AI agent: {metadata['name']}"),
        url=base_url,
        version=metadata.get("version", "1.0.0"),
        capabilities=capabilities,
        skills=skills,
        provider=provider,
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
    )
