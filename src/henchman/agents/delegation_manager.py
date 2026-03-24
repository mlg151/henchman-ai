"""Delegation manager for asynchronous delegation execution."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from henchman.core.events import EventType

from .orchestrator_types import DelegationParams

if TYPE_CHECKING:

    from henchman.agents.delegation import DelegationRunner
    from henchman.core.agent import Agent
    from henchman.providers.base import ToolCall


logger = logging.getLogger(__name__)

# Maximum number of completed tasks to retain in memory
MAX_COMPLETED_TASKS = 10000


@dataclass
class DelegationTask:
    """Represents an ongoing delegation task."""

    id: str
    target_role: str
    task: str
    tool_call_id: str
    source_agent: Agent
    depth: int
    task_future: asyncio.Future[tuple[str, bool]]  # (result, success)
    output_buffer: deque[str] = field(default_factory=lambda: deque(maxlen=100))
    completed: bool = False
    error: str | None = None
    start_time: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class DelegationManager:
    """Manages asynchronous delegation execution."""

    def __init__(self, delegation_runner: DelegationRunner) -> None:
        """Initialize the delegation manager.
        
        Args:
            delegation_runner: The delegation runner to use for executing delegations.
        """
        self.delegation_runner = delegation_runner
        self.ongoing_tasks: dict[str, DelegationTask] = {}
        self.completed_tasks: OrderedDict[str, DelegationTask] = OrderedDict()
        self._task_counter = 0

    async def start_delegation(
        self,
        source_agent: Agent,
        tool_call: ToolCall,
        depth: int,
    ) -> str:
        """Start a delegation asynchronously.
        
        Args:
            source_agent: The agent that initiated the delegation.
            tool_call: The tool call that triggered the delegation.
            depth: Current delegation depth.
            
        Returns:
            Delegation task ID.
        """
        task_id = f"delegation_{self._task_counter}"
        self._task_counter += 1

        # Extract delegation parameters
        target_role = tool_call.arguments.get("agent", "")
        task = tool_call.arguments.get("task", "")

        # Create future for the delegation result
        loop = asyncio.get_event_loop()
        task_future = loop.create_future()

        # Create delegation task
        delegation_task = DelegationTask(
            id=task_id,
            target_role=target_role,
            task=task,
            tool_call_id=tool_call.id,
            source_agent=source_agent,
            depth=depth,
            task_future=task_future,
        )

        # Store task
        self.ongoing_tasks[task_id] = delegation_task

        # Start delegation in background
        asyncio.create_task(self._run_delegation(delegation_task, tool_call))

        logger.info("Started asynchronous delegation %s: %s -> %s",
                   task_id, source_agent, target_role)

        return task_id

    async def _run_delegation(
        self,
        delegation_task: DelegationTask,
        tool_call: ToolCall,
    ) -> None:
        """Run a delegation in the background.
        
        Args:
            delegation_task: The delegation task to run.
            tool_call: The original tool call.
        """
        try:
            # Create delegation parameters
            brief = tool_call.arguments.get("brief", {})
            delegation_params = DelegationParams(
                target_role=delegation_task.target_role,
                task=delegation_task.task,
                brief=brief,
                depth=delegation_task.depth + 1,
            )

            # Run delegation and capture output
            result_content = ""
            success = True

            async for event in self.delegation_runner.run_delegation(delegation_params):
                # Capture content events
                if event.type == EventType.CONTENT:
                    content = str(event.data)
                    delegation_task.output_buffer.append(content)
                    result_content += content
                elif event.type == EventType.ERROR:
                    error_msg = str(event.data)
                    delegation_task.output_buffer.append(f"ERROR: {error_msg}")
                    delegation_task.error = error_msg
                    success = False
                elif event.type == EventType.AGENT_COMPLETED:
                    # Extract completion result
                    if isinstance(event.data, dict) and "result" in event.data:
                        completion_result = str(event.data["result"])
                        delegation_task.output_buffer.append(f"COMPLETED: {completion_result}")
                        result_content += f"\n\n{completion_result}"

            # Mark as completed
            delegation_task.completed = True

            # Set future result
            if not delegation_task.task_future.done():
                delegation_task.task_future.set_result((result_content, success))

            # Move to completed tasks (with bounded cache)
            self._add_completed_task(delegation_task.id, delegation_task)
            del self.ongoing_tasks[delegation_task.id]

            logger.info("Completed asynchronous delegation %s", delegation_task.id)

        except Exception as e:
            logger.exception("Delegation %s failed: %s", delegation_task.id, e)
            delegation_task.completed = True
            delegation_task.error = str(e)

            if not delegation_task.task_future.done():
                delegation_task.task_future.set_exception(e)

            # Still move to completed (failed, with bounded cache)
            self._add_completed_task(delegation_task.id, delegation_task)
            if delegation_task.id in self.ongoing_tasks:
                del self.ongoing_tasks[delegation_task.id]

    def get_ongoing_delegations(self) -> list[DelegationTask]:
        """Get list of ongoing delegations.
        
        Returns:
            List of ongoing delegation tasks.
        """
        return list(self.ongoing_tasks.values())

    def get_delegation(self, task_id: str) -> DelegationTask | None:
        """Get a delegation task by ID.
        
        Args:
            task_id: The delegation task ID.
            
        Returns:
            The delegation task, or None if not found.
        """
        if task_id in self.ongoing_tasks:
            return self.ongoing_tasks[task_id]
        return self.completed_tasks.get(task_id)

    def _add_completed_task(self, task_id: str, task: DelegationTask) -> None:
        """Add a task to completed_tasks with bounded cache.

        Args:
            task_id: The delegation task ID.
            task: The completed delegation task.
        """
        # Evict oldest if at capacity
        while len(self.completed_tasks) >= MAX_COMPLETED_TASKS:
            oldest_key = next(iter(self.completed_tasks))
            del self.completed_tasks[oldest_key]
            logger.debug("Evicted oldest completed task %s (cache full)", oldest_key)

        self.completed_tasks[task_id] = task

    def tail_delegation_output(self, task_id: str, lines: int = 25) -> str:
        """Get the last N lines of output from a delegation.
        
        Args:
            task_id: The delegation task ID.
            lines: Number of lines to return.
            
        Returns:
            The last N lines of output, or error message if delegation not found.
        """
        task = self.get_delegation(task_id)
        if not task:
            return f"Delegation {task_id} not found."

        # Get last N lines from buffer
        output_lines = list(task.output_buffer)
        if len(output_lines) <= lines:
            return "\n".join(output_lines)

        return "\n".join(output_lines[-lines:])

    async def wait_for_delegation(self, task_id: str, timeout: float | None = None) -> tuple[str, bool]:
        """Wait for a delegation to complete.
        
        Args:
            task_id: The delegation task ID.
            timeout: Timeout in seconds, or None for no timeout.
            
        Returns:
            Tuple of (result_content, success).
            
        Raises:
            asyncio.TimeoutError: If timeout is reached.
            ValueError: If delegation not found.
        """
        task = self.get_delegation(task_id)
        if not task:
            raise ValueError(f"Delegation {task_id} not found.")

        if task.completed and task.task_future.done():
            return task.task_future.result()

        return await asyncio.wait_for(task.task_future, timeout)

    def cancel_delegation(self, task_id: str) -> bool:
        """Cancel an ongoing delegation.
        
        Args:
            task_id: The delegation task ID.
            
        Returns:
            True if delegation was cancelled, False otherwise.
        """
        task = self.ongoing_tasks.get(task_id)
        if not task:
            return False

        if not task.task_future.done():
            task.task_future.cancel()
            task.error = "Cancelled by user"
            task.completed = True

        # Move to completed (with bounded cache)
        self._add_completed_task(task_id, task)
        del self.ongoing_tasks[task_id]

        logger.info("Cancelled delegation %s", task_id)
        return True

    def submit_delegation_result(self, task_id: str) -> bool:
        """Submit the result of a completed delegation to the source agent.
        
        Args:
            task_id: The delegation task ID.
            
        Returns:
            True if result was submitted, False otherwise.
        """
        task = self.completed_tasks.get(task_id)
        if not task or not task.task_future.done():
            return False

        try:
            result_content, success = task.task_future.result()
            if task.error:
                result_content = f"ERROR: {task.error}\n\n{result_content}"

            # Submit result to source agent
            task.source_agent.submit_tool_result(task.tool_call_id, result_content)
            return True
        except (asyncio.CancelledError, Exception) as e:
            logger.warning("Failed to submit delegation result %s: %s", task_id, e)
            return False
