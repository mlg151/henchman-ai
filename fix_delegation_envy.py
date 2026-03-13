import re

with open('src/henchman/agents/orchestrator_delegation_ctrl.py', 'r') as f:
    content = f.read()

# I will unpack the parameters to reduce the attribute accesses on `params`
new_func = """    async def _run_delegation(
        self: DelegationController,
        params: DelegationExecutionParams,
    ) -> AsyncIterator[AgentEvent]:
        \"\"\"Execute delegation and yield result event.\"\"\"
        max_retries = self.orchestrator.settings.agents.max_delegation_retries
        final_state = _StreamState()
        
        target = params.target
        task = params.task
        agent = params.agent
        tool_call = params.tool_call

        for attempt in range(max_retries + 1):
            state = _StreamState()
            async for sub_event in self._stream_delegation(params, state):
                yield sub_event

            result = state.result_content or "Delegation completed (no output)."
            if state.status == "no_work_done":
                result = (
                    f"\\u26a0\\ufe0f Agent {target} ended without "
                    f"making any tool calls.\\n\\n{result}"
                )

            update_ledger(
                self.orchestrator.ledger,
                params.ledger_record,
                result,
                had_error=state.had_error,
            )
            final_state = state

            if not state.had_error or attempt >= max_retries:
                break

            ledger = self.orchestrator.ledger
            if ledger:
                params.ledger_record = ledger.add_delegation(
                    agent=target, task=task
                )

        final_result = final_state.result_content or "Delegation completed (no output)."
        if final_state.status == "no_work_done":
            final_result = (
                f"\\u26a0\\ufe0f Agent {target} ended without "
                f"making any tool calls.\\n\\n{final_result}"
            )

        submitted = final_result
        ledger = self.orchestrator.ledger
        if ledger:
            submitted = f"{final_result}\\n\\n{ledger.render()}"

        agent.submit_tool_result(tool_call.id, submitted)
        yield create_tool_result_event(agent, tool_call, final_result)"""

content = re.sub(r'    async def _run_delegation\([\s\S]*?yield create_tool_result_event[^)]+\)', new_func, content)

with open('src/henchman/agents/orchestrator_delegation_ctrl.py', 'w') as f:
    f.write(content)
