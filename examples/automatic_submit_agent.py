import asyncio
import logging
from aip_sdk import Task, TaskResult, AgentContext, adapt_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoSubmitAgent")

class SearchAndSummaryAgent:
    """An agent that automatically submits its results to the blockchain commerce layer."""
    
    def __init__(self):
        self.agent_id = "agent_uuid_searcher_123"

    async def perform_task(self, task: Task, context: AgentContext) -> TaskResult:
        logger.info(f"Received task: {task.name}")

        # 1. Execute the actual work (AI logic)
        # In a real scenario, this would involve LLM calls, searching, etc.
        result_data = {
            "summary": "Latest news on BNB Chain: Market cap reached new highs...",
            "sources": ["https://news.bnb", "https://twitter.com/bnbchain"]
        }
        
        # 2. Extract job_id from metadata (if this was triggered via a commerce job)
        job_id = task.payload.get("job_id")
        
        if job_id:
            logger.info(f"Job ID {job_id} detected. Submitting results to commerce layer...")
            # --- NEW HIGH-LEVEL SDK METHOD ---
            # This handles JSON-RPC calls and blockchain synchronization automatically.
            success = await context.submit_commerce_work(
                job_id=job_id,
                deliverable_data=result_data,
                description="Search and summary task complete."
            )
            
            if success:
                logger.info(f"Successfully submitted results for Job {job_id} to the blockchain.")
            else:
                logger.warning(f"Failed to submit commerce results for Job {job_id}.")

        # 3. Return the standard task result
        return TaskResult.success_result(
            output=result_data,
            summary="Processed news search and submitted to commerce layer."
        )

async def main():
    agent = SearchAndSummaryAgent()
    adapter = adapt_agent(agent)
    # The adapter will now inject 'submit_commerce_work' into the context
    # when the agent is invoked via the AIP Gateway.
    logger.info("Agent is ready with automatic commerce submission support.")

if __name__ == "__main__":
    asyncio.run(main())
