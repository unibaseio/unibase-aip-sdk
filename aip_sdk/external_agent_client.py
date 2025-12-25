"""
External Agent Client SDK

Allows agents to run anywhere (local machine, behind firewall) and connect
to a remote gateway using the task queue pull model.

Example:
    from aip_sdk.external_agent_client import ExternalAgentClient

    class MyAgent(ExternalAgentClient):
        async def execute_task(self, payload):
            # Your agent logic
            return {"result": "done"}

    agent = MyAgent("my_agent", "https://gateway.example.com")
    await agent.run()
"""

import asyncio
import httpx
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, List, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExternalAgentClient(ABC):
    """
    Base class for external agents that pull tasks from gateway.

    Agents extend this class and implement execute_task() method.
    The client handles:
    - Registration with gateway
    - Task polling (long-polling)
    - Heartbeat management
    - Error handling and retries
    """

    def __init__(
        self,
        agent_name: str,
        gateway_url: str,
        poll_interval: float = 5.0,
        heartbeat_interval: float = 30.0,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Initialize external agent client.

        Args:
            agent_name: Unique agent identifier
            gateway_url: Gateway URL (e.g., https://gateway.example.com)
            poll_interval: Seconds between polls when no tasks (default: 5s)
            heartbeat_interval: Seconds between heartbeats (default: 30s)
            capabilities: List of agent capabilities
            metadata: Additional metadata about the agent
        """
        self.agent_name = agent_name
        self.gateway_url = gateway_url.rstrip('/')
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.capabilities = capabilities or []
        self.metadata = metadata or {}

        self.running = False
        self.agent_id: Optional[str] = None
        self.current_task_id: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None

        # Statistics
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.started_at: Optional[datetime] = None

    async def register(self):
        """Register agent with gateway"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/gateway/agents/register-external",
                    json={
                        "agent_name": self.agent_name,
                        "capabilities": self.capabilities,
                        "metadata": {
                            **self.metadata,
                            "sdk_version": "1.0.0"
                        }
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

                self.agent_id = data["agent_id"]

                logger.info(
                    f"Agent '{self.agent_name}' registered successfully "
                    f"(ID: {self.agent_id})"
                )
                logger.info(f"Poll URL: {data['poll_url']}")
                logger.info(f"Heartbeat URL: {data['heartbeat_url']}")

        except httpx.HTTPStatusError as e:
            logger.error(f"Registration failed with status {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise

    async def poll_task(self, timeout: float = 30.0) -> Optional[Dict]:
        """
        Poll for next task (long-polling).

        Args:
            timeout: Long-poll timeout in seconds

        Returns:
            Task dict if available, None otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.gateway_url}/gateway/tasks/poll",
                    params={
                        "agent": self.agent_name,
                        "timeout": timeout
                    },
                    timeout=timeout + 5.0  # Add buffer to request timeout
                )
                response.raise_for_status()
                data = response.json()

                if data.get("task_id"):
                    return data
                return None

        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Poll error: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Poll error: {e}")
            return None

    async def complete_task(
        self,
        task_id: str,
        result: Dict,
        status: str = "completed",
        error: Optional[str] = None,
        execution_time: Optional[float] = None
    ):
        """
        Report task completion to gateway.

        Args:
            task_id: Task identifier
            result: Task result (dict)
            status: Task status (completed or failed)
            error: Error message if failed
            execution_time: Execution time in seconds
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/gateway/tasks/complete",
                    json={
                        "task_id": task_id,
                        "status": status,
                        "result": result,
                        "error": error,
                        "execution_time": execution_time
                    },
                    timeout=10.0
                )
                response.raise_for_status()

                logger.info(
                    f"Task {task_id} completed with status '{status}' "
                    f"in {execution_time:.2f}s" if execution_time else ""
                )

        except Exception as e:
            logger.error(f"Failed to report task completion: {e}")

    async def send_heartbeat(self):
        """Send heartbeat to gateway"""
        try:
            status = "busy" if self.current_task_id else "idle"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.gateway_url}/gateway/agents/heartbeat",
                    json={
                        "agent_name": self.agent_name,
                        "status": status,
                        "current_task": self.current_task_id,
                        "metadata": {
                            "tasks_completed": self.tasks_completed,
                            "tasks_failed": self.tasks_failed,
                            "uptime": (datetime.now() - self.started_at).total_seconds()
                            if self.started_at else 0
                        }
                    },
                    timeout=5.0
                )
                response.raise_for_status()

                logger.debug(f"Heartbeat sent (status: {status})")

        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")

    async def heartbeat_loop(self):
        """Background heartbeat loop"""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")

    @abstractmethod
    async def execute_task(self, payload: Dict) -> Dict:
        """
        Execute a task. Must be implemented by subclass.

        Args:
            payload: Task payload from gateway

        Returns:
            Task result as dict

        Raises:
            Exception if task fails
        """
        raise NotImplementedError("Subclass must implement execute_task()")

    async def run(self):
        """
        Main loop: poll for tasks and execute them.

        This is the main entry point for the agent. It:
        1. Registers with gateway
        2. Starts heartbeat loop
        3. Polls for tasks
        4. Executes tasks
        5. Reports results
        """
        try:
            # Register with gateway
            await self.register()

            self.running = True
            self.started_at = datetime.now()

            # Start heartbeat loop
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

            logger.info(
                f"Agent '{self.agent_name}' started, polling for tasks... "
                f"(Press Ctrl+C to stop)"
            )

            # Main polling loop
            while self.running:
                try:
                    # Poll for task
                    task = await self.poll_task(timeout=30.0)

                    if task:
                        task_id = task["task_id"]
                        payload = task["payload"]

                        logger.info(f"Received task {task_id}")
                        logger.debug(f"Task payload: {payload}")

                        self.current_task_id = task_id
                        start_time = datetime.now()

                        try:
                            # Execute task
                            result = await self.execute_task(payload)

                            # Calculate execution time
                            execution_time = (datetime.now() - start_time).total_seconds()

                            # Report success
                            await self.complete_task(
                                task_id,
                                result,
                                status="completed",
                                execution_time=execution_time
                            )

                            self.tasks_completed += 1

                        except Exception as e:
                            logger.error(f"Task execution failed: {e}", exc_info=True)

                            # Calculate execution time
                            execution_time = (datetime.now() - start_time).total_seconds()

                            # Report failure
                            await self.complete_task(
                                task_id,
                                {"error": str(e)},
                                status="failed",
                                error=str(e),
                                execution_time=execution_time
                            )

                            self.tasks_failed += 1

                        finally:
                            self.current_task_id = None

                    else:
                        # No tasks, wait before next poll
                        await asyncio.sleep(self.poll_interval)

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break

                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(self.poll_interval)

        finally:
            self.running = False

            # Stop heartbeat loop
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass

            logger.info(
                f"Agent '{self.agent_name}' stopped. "
                f"Completed: {self.tasks_completed}, Failed: {self.tasks_failed}"
            )

    async def stop(self):
        """Stop the agent gracefully"""
        logger.info("Stopping agent...")
        self.running = False


# Example implementations

class CalculatorAgent(ExternalAgentClient):
    """Example calculator agent"""

    async def execute_task(self, payload: Dict) -> Dict:
        """Execute calculation"""
        operation = payload.get("operation")
        a = payload.get("a", 0)
        b = payload.get("b", 0)

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Division by zero")
            result = a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")

        return {"result": result}


class EchoAgent(ExternalAgentClient):
    """Example echo agent (for testing)"""

    async def execute_task(self, payload: Dict) -> Dict:
        """Echo back the payload"""
        await asyncio.sleep(0.1)  # Simulate work
        return {
            "echo": payload,
            "agent": self.agent_name,
            "timestamp": datetime.now().isoformat()
        }


# CLI for running agents
async def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="External Agent Client")
    parser.add_argument("--agent", default="calculator", help="Agent type (calculator, echo)")
    parser.add_argument("--name", default=None, help="Agent name (default: agent type)")
    parser.add_argument("--gateway", default="http://localhost:8080", help="Gateway URL")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval (seconds)")
    parser.add_argument("--heartbeat-interval", type=float, default=30.0, help="Heartbeat interval (seconds)")

    args = parser.parse_args()

    agent_name = args.name or args.agent

    # Create agent based on type
    if args.agent == "calculator":
        agent = CalculatorAgent(
            agent_name=agent_name,
            gateway_url=args.gateway,
            poll_interval=args.poll_interval,
            heartbeat_interval=args.heartbeat_interval,
            capabilities=["add", "subtract", "multiply", "divide"]
        )
    elif args.agent == "echo":
        agent = EchoAgent(
            agent_name=agent_name,
            gateway_url=args.gateway,
            poll_interval=args.poll_interval,
            heartbeat_interval=args.heartbeat_interval
        )
    else:
        print(f"Unknown agent type: {args.agent}")
        return 1

    # Run agent
    try:
        await agent.run()
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
