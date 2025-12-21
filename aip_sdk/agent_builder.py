"""
Agent Builder Module

Provides decorators and builders for creating agents with minimal boilerplate.

Example:
    from aip_sdk import Agent, skill

    @Agent(name="My Calculator", description="Math operations")
    class MyCalculator:

        @skill("calculate", "Perform calculations")
        async def calculate(self, task, context):
            expression = task.get("expression", "0")
            result = eval(expression)
            return {"result": result}

    # Or with function-based approach:
    @Agent(name="Weather Agent", price=0.001)
    async def weather_handler(task, context):
        location = task.get("location", "Unknown")
        return {"weather": "sunny", "location": location}
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    overload,
)
from uuid import uuid4

from aip_sdk.types import (
    AgentConfig,
    AgentContext,
    CostModel,
    SkillConfig,
    SkillInput,
    SkillOutput,
    Task,
    TaskResult,
)

T = TypeVar("T")
HandlerType = Callable[..., Awaitable[Any]]


@dataclass
class SkillDefinition:
    """Internal representation of a skill definition."""
    name: str
    description: str
    handler: HandlerType
    inputs: List[SkillInput] = field(default_factory=list)
    outputs: List[SkillOutput] = field(default_factory=list)


class SkillBuilder:
    """Builder for creating skill configurations."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._inputs: List[SkillInput] = []
        self._outputs: List[SkillOutput] = []
    
    def input(
        self,
        name: str,
        field_type: str = "string",
        description: str = "",
        required: bool = True,
        default: Any = None,
    ) -> "SkillBuilder":
        """Add an input parameter to the skill."""
        self._inputs.append(SkillInput(
            name=name,
            field_type=field_type,
            description=description,
            required=required,
            default=default,
        ))
        return self
    
    def output(
        self,
        name: str,
        field_type: str = "string",
        description: str = "",
    ) -> "SkillBuilder":
        """Add an output parameter to the skill."""
        self._outputs.append(SkillOutput(
            name=name,
            field_type=field_type,
            description=description,
        ))
        return self
    
    def build(self) -> SkillConfig:
        """Build the skill configuration."""
        return SkillConfig(
            name=self.name,
            description=self.description,
            inputs=self._inputs,
            outputs=self._outputs,
        )


def skill(
    name: str,
    description: str = "",
    inputs: Optional[List[Dict[str, Any]]] = None,
    outputs: Optional[List[Dict[str, Any]]] = None,
) -> Callable[[HandlerType], HandlerType]:
    """
    Decorator to mark a method as an agent skill.
    
    Args:
        name: Name of the skill (e.g., "weather.forecast")
        description: Human-readable description
        inputs: List of input parameter definitions
        outputs: List of output parameter definitions
        
    Example:
        class MyAgent:
            @skill("math.calculate", "Perform calculations")
            async def calculate(self, task, context):
                return {"result": 42}
    """
    def decorator(fn: HandlerType) -> HandlerType:
        skill_inputs = []
        if inputs:
            for inp in inputs:
                skill_inputs.append(SkillInput(
                    name=inp.get("name", "input"),
                    field_type=inp.get("type", inp.get("field_type", "string")),
                    description=inp.get("description", ""),
                    required=inp.get("required", True),
                ))
        
        skill_outputs = []
        if outputs:
            for out in outputs:
                skill_outputs.append(SkillOutput(
                    name=out.get("name", "output"),
                    field_type=out.get("type", out.get("field_type", "string")),
                    description=out.get("description", ""),
                ))
        
        # Store skill metadata on the function
        fn._skill_definition = SkillDefinition(
            name=name,
            description=description or fn.__doc__ or "",
            handler=fn,
            inputs=skill_inputs,
            outputs=skill_outputs,
        )
        return fn
    
    return decorator


class AgentBuilder:
    """
    Builder for creating agent configurations programmatically.
    
    Example:
        agent = (AgentBuilder("Weather Agent")
            .description("Provides weather forecasts")
            .capability("weather")
            .skill("weather.forecast", "Get weather forecast")
            .price(0.001)
            .build())
    """
    
    def __init__(self, name: str):
        self._name = name
        self._description = ""
        self._handle: Optional[str] = None
        self._skills: List[SkillConfig] = []
        self._capabilities: List[str] = []
        self._cost_model = CostModel()
        self._price = 0.001
        self._price_currency = "USD"
        self._metadata: Dict[str, Any] = {}
        self._endpoint_url: Optional[str] = None
        self._handler: Optional[HandlerType] = None
    
    def description(self, desc: str) -> "AgentBuilder":
        """Set the agent description."""
        self._description = desc
        return self
    
    def handle(self, handle: str) -> "AgentBuilder":
        """Set the agent handle (unique identifier)."""
        self._handle = handle
        return self
    
    def skill(
        self,
        name: str,
        description: str = "",
        inputs: Optional[List[SkillInput]] = None,
        outputs: Optional[List[SkillOutput]] = None,
    ) -> "AgentBuilder":
        """Add a skill to the agent."""
        self._skills.append(SkillConfig(
            name=name,
            description=description,
            inputs=inputs or [],
            outputs=outputs or [],
        ))
        return self
    
    def add_skill(self, skill_config: SkillConfig) -> "AgentBuilder":
        """Add a pre-built skill configuration."""
        self._skills.append(skill_config)
        return self
    
    def capability(self, *caps: str) -> "AgentBuilder":
        """Add capabilities to the agent."""
        self._capabilities.extend(caps)
        return self
    
    def cost(
        self,
        base_fee: float = 0.0,
        per_call_fee: float = 0.0,
    ) -> "AgentBuilder":
        """Set the cost model."""
        self._cost_model = CostModel(
            base_call_fee=base_fee,
            per_agent_call_fee=per_call_fee,
        )
        return self
    
    def price(
        self,
        amount: float,
        currency: str = "USD",
    ) -> "AgentBuilder":
        """Set the agent price."""
        self._price = amount
        self._price_currency = currency
        return self
    
    def metadata(self, **kwargs: Any) -> "AgentBuilder":
        """Add metadata to the agent."""
        self._metadata.update(kwargs)
        return self
    
    def endpoint(self, url: str) -> "AgentBuilder":
        """Set the endpoint URL for remote agents."""
        self._endpoint_url = url
        return self
    
    def handler(self, fn: HandlerType) -> "AgentBuilder":
        """Set the task handler function."""
        self._handler = fn
        return self
    
    def build(self) -> AgentConfig:
        """Build the agent configuration."""
        return AgentConfig(
            name=self._name,
            description=self._description,
            handle=self._handle,
            skills=self._skills,
            capabilities=self._capabilities,
            cost_model=self._cost_model,
            price=self._price,
            price_currency=self._price_currency,
            metadata=self._metadata,
            endpoint_url=self._endpoint_url,
        )


class SDKAgent:
    """
    Wrapper class for SDK-created agents.
    
    This provides compatibility with the AIP domain Agent class
    while supporting the SDK's simplified interface.
    """
    
    def __init__(
        self,
        config: AgentConfig,
        handler: Optional[HandlerType] = None,
        skill_handlers: Optional[Dict[str, HandlerType]] = None,
    ):
        self.config = config
        self._handler = handler
        self._skill_handlers = skill_handlers or {}
        self._identity: Optional[Any] = None
        self._domain_agent: Optional[Any] = None
    
    @property
    def agent_id(self) -> str:
        """Get the agent ID."""
        if self._identity:
            return self._identity.identity_id
        handle = self.config.handle or self.config.name.lower().replace(" ", "_")
        return f"erc8004:{handle}"
    
    @property
    def identity(self) -> Any:
        """Get or create the agent identity."""
        if self._identity is None:
            from aip_sdk._internal import ERC8004Identity, IdentityMetadata

            handle = self.config.handle or self.config.name.lower().replace(" ", "_")
            metadata = IdentityMetadata(
                display_name=self.config.name,
                capabilities=self.config.capabilities,
                extra=self.config.metadata,
            )
            self._identity = ERC8004Identity.create(handle, metadata)
        return self._identity
    
    @property
    def skills(self) -> List[Any]:
        """Get the skills as domain objects."""
        from aip_sdk._internal import ClaudeSkillTemplate, SkillIOField
        
        domain_skills = []
        for skill_config in self.config.skills:
            domain_skills.append(ClaudeSkillTemplate(
                name=skill_config.name,
                description=skill_config.description,
                inputs=[
                    SkillIOField(
                        name=i.name,
                        field_type=i.field_type,
                        description=i.description,
                    )
                    for i in skill_config.inputs
                ],
                outputs=[
                    SkillIOField(
                        name=o.name,
                        field_type=o.field_type,
                        description=o.description,
                    )
                    for o in skill_config.outputs
                ],
            ))
        return domain_skills
    
    @property
    def cost_model(self) -> Any:
        """Get the cost model as domain object."""
        from aip_sdk._internal import AgentCostModel
        
        return AgentCostModel(
            base_call_fee=self.config.cost_model.base_call_fee,
            per_agent_call_fee=self.config.cost_model.per_agent_call_fee,
        )
    
    async def perform_task(
        self,
        task: Any,
        context: Any,
    ) -> Any:
        """
        Execute a task.

        This is compatible with the domain Agent.perform_task interface.
        """
        from aip_sdk._internal import AgentInvocationResult
        
        # Convert domain types to SDK types
        sdk_task = Task.from_domain(task)
        sdk_context = AgentContext.from_execution_context(context)
        
        # Find the appropriate handler
        handler = self._handler
        if not handler and task.name in self._skill_handlers:
            handler = self._skill_handlers[task.name]
        
        if not handler:
            raise ValueError(f"No handler found for task: {task.name}")
        
        try:
            # Check handler signature
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            
            # Call handler based on its signature
            if len(params) >= 2:
                result = await handler(sdk_task, sdk_context)
            elif len(params) == 1:
                result = await handler(sdk_task.payload)
            else:
                result = await handler()
            
            # Normalize result
            if isinstance(result, TaskResult):
                return AgentInvocationResult(
                    output=result.output,
                    summary=result.summary,
                    used_tools=result.used_tools,
                    downstream_calls=result.downstream_calls,
                )
            elif isinstance(result, dict):
                return AgentInvocationResult(
                    output=result,
                    summary=str(result),
                )
            else:
                return AgentInvocationResult(
                    output={"result": result},
                    summary=str(result),
                )
                
        except Exception as e:
            return AgentInvocationResult(
                output={"error": str(e)},
                summary=f"Error: {e}",
            )
    
    def to_domain_agent(self) -> Any:
        """Convert to a domain Agent instance."""
        if self._domain_agent is None:
            from aip_sdk._internal import Agent
            
            # Create a dynamic agent class
            sdk_agent = self
            
            class DynamicAgent(Agent):
                def __init__(self):
                    super().__init__(
                        identity=sdk_agent.identity,
                        skills=sdk_agent.skills,
                        cost_model=sdk_agent.cost_model,
                    )
                    self._sdk_agent = sdk_agent
                
                async def perform_task(self, task, context):
                    return await self._sdk_agent.perform_task(task, context)
            
            self._domain_agent = DynamicAgent()
        
        return self._domain_agent


@overload
def Agent(
    _fn: HandlerType,
) -> SDKAgent: ...

@overload
def Agent(
    *,
    name: str,
    description: str = "",
    handle: Optional[str] = None,
    skills: Optional[List[SkillConfig]] = None,
    capabilities: Optional[List[str]] = None,
    price: float = 0.001,
    base_fee: float = 0.0,
    per_call_fee: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable[[Union[HandlerType, Type[T]]], SDKAgent]: ...

def Agent(
    _fn: Optional[HandlerType] = None,
    *,
    name: Optional[str] = None,
    description: str = "",
    handle: Optional[str] = None,
    skills: Optional[List[SkillConfig]] = None,
    capabilities: Optional[List[str]] = None,
    price: float = 0.001,
    base_fee: float = 0.0,
    per_call_fee: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Union[SDKAgent, Callable[[Union[HandlerType, Type[T]]], SDKAgent]]:
    """
    Decorator for creating agents.
    
    Can be used with functions or classes:
    
    Example (function):
        @Agent(name="Weather", description="Weather service")
        async def weather_handler(task, context):
            return {"weather": "sunny"}
    
    Example (class):
        @Agent(name="Calculator", description="Math operations")
        class Calculator:
            @skill("calculate", "Perform calculations")
            async def calculate(self, task, context):
                return {"result": 42}
    """
    def decorator(fn_or_class: Union[HandlerType, Type[T]]) -> SDKAgent:
        nonlocal name, description
        
        # Infer name from function/class if not provided
        if name is None:
            name = getattr(fn_or_class, "__name__", "Agent")
            # Convert snake_case to Title Case
            name = name.replace("_", " ").title()
        
        if not description:
            description = getattr(fn_or_class, "__doc__", "") or ""
        
        # Build configuration
        config = AgentConfig(
            name=name,
            description=description,
            handle=handle,
            skills=skills or [],
            capabilities=capabilities or [],
            cost_model=CostModel(
                base_call_fee=base_fee,
                per_agent_call_fee=per_call_fee,
            ),
            price=price,
            metadata=metadata or {},
        )
        
        # Handle class-based agents
        if isinstance(fn_or_class, type):
            # Extract skills from decorated methods
            skill_handlers: Dict[str, HandlerType] = {}
            instance = fn_or_class()
            
            for attr_name in dir(instance):
                attr = getattr(instance, attr_name, None)
                if hasattr(attr, "_skill_definition"):
                    skill_def: SkillDefinition = attr._skill_definition
                    config.skills.append(SkillConfig(
                        name=skill_def.name,
                        description=skill_def.description,
                        inputs=skill_def.inputs,
                        outputs=skill_def.outputs,
                    ))
                    skill_handlers[skill_def.name] = attr
            
            return SDKAgent(config, skill_handlers=skill_handlers)
        
        # Handle function-based agents
        if asyncio.iscoroutinefunction(fn_or_class):
            # If no skills defined, create a default one
            if not config.skills:
                skill_name = handle or name.lower().replace(" ", "_")
                config.skills.append(SkillConfig(
                    name=skill_name,
                    description=description,
                ))
            
            return SDKAgent(config, handler=fn_or_class)
        
        raise ValueError(
            "Agent decorator must be applied to a class or async function"
        )
    
    # Handle bare decorator usage: @Agent
    if _fn is not None:
        return decorator(_fn)
    
    return decorator


def create_agent(
    name: str,
    handler: HandlerType,
    *,
    description: str = "",
    skill_name: Optional[str] = None,
    price: float = 0.001,
    **kwargs: Any,
) -> SDKAgent:
    """
    Create an agent from a handler function.
    
    This is a simpler alternative to the @Agent decorator.
    
    Args:
        name: Agent name
        handler: Async function to handle tasks
        description: Agent description
        skill_name: Name for the agent's skill
        price: Agent price
        **kwargs: Additional configuration
        
    Returns:
        SDKAgent instance
    """
    skill_name = skill_name or name.lower().replace(" ", "_")
    
    config = AgentConfig(
        name=name,
        description=description,
        skills=[SkillConfig(name=skill_name, description=description)],
        price=price,
        **kwargs,
    )
    
    return SDKAgent(config, handler=handler)
