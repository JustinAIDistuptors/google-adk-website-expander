#!/usr/bin/env python3
"""
Orchestrator Agent for the Website Expansion Framework.

This module provides the Orchestrator Agent implementation, responsible for
coordinating the overall flow of tasks between specialized agents.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import base agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part
from google.adk.tools import agent_tool

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    """
    Agent responsible for orchestrating the website expansion process.
    
    The Orchestrator Agent manages the workflow, delegates tasks to specialized agents,
    and ensures the sequential execution of the page generation pipeline.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the Orchestrator Agent.
        
        Args:
            config_path: Path to the agent configuration file
        """
        super().__init__("orchestrator", config_path)
        self.task_queue_path = "data/queue/task_queue.json"
        self.max_tasks_per_batch = self.agent_config.get('max_tasks_per_batch', 10)
        self.concurrent_tasks = self.agent_config.get('concurrent_tasks', 5)
    
    def initialize_agent_with_subagents(self, seo_agent, content_agent, page_agent, publisher_agent):
        """
        Initialize the agent with all necessary sub-agents.
        
        Args:
            seo_agent: SEO Research Agent
            content_agent: Content Generation Agent
            page_agent: Page Assembly Agent
            publisher_agent: Publishing Agent
        """
        # Create agent tools for each specialized agent
        tools = [
            agent_tool.AgentTool(agent=seo_agent.agent),
            agent_tool.AgentTool(agent=content_agent.agent),
            agent_tool.AgentTool(agent=page_agent.agent),
            agent_tool.AgentTool(agent=publisher_agent.agent),
        ]
        
        # Add specialized tools for the Orchestrator Agent
        # tools.append(task_management_tool)
        
        # Initialize the agent
        super().initialize_agent(tools=tools)
    
    def _load_task_queue(self) -> List[Dict[str, Any]]:
        """
        Load the task queue from storage.
        
        Returns:
            list: The task queue
        """
        try:
            with open(self.task_queue_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load task queue: {str(e)}")
            return []
    
    def _save_task_queue(self, queue: List[Dict[str, Any]]) -> None:
        """
        Save the task queue to storage.
        
        Args:
            queue: The task queue to save
        """
        try:
            with open(self.task_queue_path, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save task queue: {str(e)}")
    
    def get_next_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the next batch of pending tasks from the queue.
        
        Args:
            limit: Maximum number of tasks to retrieve
            
        Returns:
            list: List of pending tasks
        """
        queue = self._load_task_queue()
        pending_tasks = []
        
        for task in queue:
            if task['status'] == 'pending' and len(pending_tasks) < limit:
                # Mark as in_progress and update timestamp
                task['status'] = 'in_progress'
                task['updated_at'] = datetime.now().isoformat()
                pending_tasks.append(task)
        
        # Save the updated queue
        self._save_task_queue(queue)
        
        return pending_tasks
    
    def update_task_status(self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> None:
        """
        Update the status of a task in the queue.
        
        Args:
            task_id: Task identifier
            status: New status
            result: Optional result data
        """
        queue = self._load_task_queue()
        
        for task in queue:
            if task.get('task_id') == task_id:
                task['status'] = status
                task['updated_at'] = datetime.now().isoformat()
                if result:
                    task['result'] = result
                break
        
        self._save_task_queue(queue)
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single task through the complete pipeline.
        
        Args:
            task: The task to process
            
        Returns:
            dict: Task result
        """
        task_id = task.get('task_id')
        service_id = task.get('service_id')
        zip_code = task.get('zip')
        
        self.logger.info(f"Processing task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        try:
            # Prepare the message for the agent
            content = Content(
                role='user',
                parts=[Part(text=f"Process task for service '{service_id}' in location '{zip_code}'. "
                            f"coordinate with SEO Research Agent, Content Generation Agent, "
                            f"Page Assembly Agent, and Publishing Agent to complete this task.")]
            )
            
            # Generate a unique session ID for this task
            session_id = f"task_{task_id}"
            user_id = "website_expander"
            
            result = {"status": "processing"}
            final_response = None
            
            # Process the task using the Orchestrator Agent
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                # Check for the final response
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                    
                    # Extract result from the response
                    if "successfully completed" in final_response.lower():
                        result["status"] = "completed"
                    else:
                        result["status"] = "failed"
                    
                    result["message"] = final_response
            
            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, result["status"], elapsed, result)
            
            return result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            self.logger.error(f"Error processing task {task_id}: {str(e)}")
            
            result = {
                "status": "error",
                "error": str(e)
            }
            
            self.log_task_completion(task_id, "error", elapsed, result)
            return result
    
    async def start_process(self):
        """
        Start the orchestration process, processing tasks from the queue.
        """
        self.logger.info("Starting orchestration process")
        
        while True:
            # Get the next batch of pending tasks
            pending_tasks = self.get_next_pending_tasks(self.max_tasks_per_batch)
            
            if not pending_tasks:
                self.logger.info("No pending tasks found. Waiting before checking again...")
                await asyncio.sleep(60)  # Wait for 1 minute before checking again
                continue
            
            self.logger.info(f"Processing batch of {len(pending_tasks)} tasks")
            
            # Process tasks concurrently with limit
            tasks = []
            for task in pending_tasks:
                # Process task
                task_coroutine = self.process_task(task)
                tasks.append(task_coroutine)
                
                # Update task status
                self.update_task_status(task['task_id'], 'processing')
                
                # If we've reached the concurrent limit, wait for some tasks to complete
                if len(tasks) >= self.concurrent_tasks:
                    completed_tasks = await asyncio.gather(*tasks)
                    
                    # Update task statuses based on results
                    for i, result in enumerate(completed_tasks):
                        task_id = pending_tasks[i]['task_id']
                        status = result.get('status', 'error')
                        self.update_task_status(task_id, status, result)
                    
                    # Reset task list
                    tasks = []
            
            # Wait for any remaining tasks to complete
            if tasks:
                completed_tasks = await asyncio.gather(*tasks)
                
                # Update task statuses based on results
                for i, result in enumerate(completed_tasks):
                    task_id = pending_tasks[i + (len(pending_tasks) - len(tasks))]['task_id']
                    status = result.get('status', 'error')
                    self.update_task_status(task_id, status, result)
            
            # Short pause before next batch
            await asyncio.sleep(5)
