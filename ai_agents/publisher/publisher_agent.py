#!/usr/bin/env python3
"""
Publisher Agent for the Website Expansion Framework.

This module provides the Publisher Agent implementation, responsible for
integrating with the website to deploy assembled pages.
It now uses a PostgreSQL database for data operations and task status updates.
"""

import json # For parsing JSONB metadata
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os # Still needed for sitemap path creation

import psycopg2
from psycopg2 import extras # For dict cursor

# Import base agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part

# Database connection utility & Task related models
from src.utils.queue_manager import get_db_connection, QueueManager
from src.models.task import Task, TaskStatus as PythonTaskStatus


logger = logging.getLogger(__name__)

class PublisherAgent(BaseAgent):
    """
    Agent responsible for publishing pages to the website.
    Uses PostgreSQL for data retrieval and task status updates.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the Publisher Agent.
        """
        super().__init__("publisher", config_path)
        # self.publish_batch_size = self.agent_config.get('publish_batch_size', 5) # Potentially for orchestrator
        self.dry_run = self.agent_config.get('dry_run', False)
        self.publishing_config = self._load_publishing_config()
        self.queue_manager = QueueManager() # For updating task status
    
    def _load_publishing_config(self) -> Dict[str, Any]:
        """Load publishing configuration parameters."""
        try:
            with open("config/publishing_config.yaml", 'r') as f:
                import yaml
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load publishing config: {str(e)}")
            return { # Minimal default
                'website': {'base_url': "https://example.com"},
                'url_structure': {'pattern': "{service_slug}/{location_zip}"}
            }
    
    def _create_publishing_tool(self):
        """Create a tool for publishing pages to the website."""
        def publish_page_tool(task_id: str, service_id: str, zip_code: str, dry_run: bool = False) -> Dict[str, Any]:
            """
            Publishes a page to the website by fetching its data from the DB.
            Args:
                task_id: The unique ID of the task.
                service_id: The service ID (used for URL generation).
                zip_code: The zip code (used for URL generation).
                dry_run: If True, simulate publishing.
            Returns:
                dict: Publishing result with status, URL (if successful), or error.
            """
            self.logger.info(f"Publishing page for task_id {task_id} (dry_run: {dry_run})")
            
            html_content: Optional[str] = None
            # page_metadata: Optional[Dict[str, Any]] = None # Not directly used by mock

            sql = "SELECT html_content, metadata FROM assembled_pages WHERE task_id = %s;"
            try:
                with get_db_connection() as conn:
                    if conn is None:
                        return {"status": "error", "error": f"DB connection failed for task {task_id}."}
                    with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                        cur.execute(sql, (task_id,))
                        row = cur.fetchone()
                        if not row:
                            return {"status": "error", "error": f"Assembled page not found in DB for task_id {task_id}"}
                        html_content = row['html_content']
                        # page_metadata = row['metadata'] # Contains source_template_id, etc.
                
                if not html_content: # Should not happen if row was found, but good check
                     return {"status": "error", "error": f"HTML content is empty in DB for task_id {task_id}"}

                # Generate URL based on pattern (service_id and zip_code are passed to tool for this)
                url_pattern = self.publishing_config.get('url_structure', {}).get('pattern', "{service_slug}/{location_zip}")
                service_slug = service_id.lower().replace("_", "-") # Use passed service_id
                url_slug = url_pattern.format(service_slug=service_slug, location_zip=zip_code)
                base_url = self.publishing_config.get('website', {}).get('base_url', "https://example.com")
                full_url = f"{base_url.rstrip('/')}/{url_slug.lstrip('/')}/"
                
                # Simulate API call to CMS
                if dry_run:
                    self.logger.info(f"DRY RUN: Would publish to {full_url} for task {task_id}")
                    return {"status": "success", "message": "Page would have been published (dry run)", "url": full_url}
                else:
                    # TODO: Implement actual CMS publishing logic here
                    # For now, we'll simulate success
                    self.logger.info(f"SIMULATED PUBLISH: Publishing to {full_url} for task {task_id}")
                    # No file writing needed here anymore. Success is marked in DB by process_task.
                    return {"status": "success", "message": "Page published successfully (simulated)", "url": full_url}
                
            except psycopg2.Error as e:
                logger.error(f"DB error in publish_page_tool for task {task_id}: {e}")
                return {"status": "error", "error": f"DB error: {e}"}
            except Exception as e:
                logger.error(f"Error in publish_page_tool for task {task_id}: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}
        
        return publish_page_tool
    
    def _create_sitemap_tool(self):
        """Create a tool for updating the sitemap."""
        def update_sitemap_tool() -> Dict[str, Any]:
            """
            Updates the website sitemap with newly published pages from the DB.
            """
            self.logger.info("Updating sitemap by fetching published URLs from DB.")
            published_urls: List[str] = []
            
            sql = "SELECT published_url FROM tasks WHERE status = 'published' AND published_url IS NOT NULL;"
            try:
                with get_db_connection() as conn:
                    if conn is None:
                        return {"status": "error", "error": "Sitemap DB connection failed."}
                    with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                        cur.execute(sql)
                        rows = cur.fetchall()
                        for row in rows:
                            published_urls.append(row['published_url'])
                
                sitemap_dir = self.agent_config.get("sitemap_output_dir", "data/sitemap")
                os.makedirs(sitemap_dir, exist_ok=True) # Ensure directory exists
                
                sitemap_content = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                sitemap_content += "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
                for url in published_urls:
                    sitemap_content += f"  <url>\n    <loc>{url}</loc>\n  </url>\n"
                sitemap_content += "</urlset>"
                
                sitemap_path = os.path.join(sitemap_dir, "sitemap.xml")
                with open(sitemap_path, 'w') as f:
                    f.write(sitemap_content)
                
                logger.info(f"Sitemap updated with {len(published_urls)} pages at {sitemap_path}.")
                return {"status": "success", "message": f"Sitemap updated with {len(published_urls)} pages.", "path": sitemap_path}

            except psycopg2.Error as e:
                logger.error(f"DB error updating sitemap: {e}")
                return {"status": "error", "error": f"Sitemap DB error: {e}"}
            except Exception as e:
                logger.error(f"Error updating sitemap: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}
        
        return update_sitemap_tool
    
    def initialize_agent(self):
        """Initialize the Publisher Agent with necessary tools."""
        tools = [self._create_publishing_tool(), self._create_sitemap_tool()]
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to publish assembled pages to the website and manage the sitemap.
        For each task (identified by task_id, service_id, zip_code):
        1. Call `publish_page_tool` with `task_id`, `service_id`, `zip_code`, and the current `dry_run` setting.
        2. If publishing is successful, the tool will return a URL.
        3. After attempting to publish all relevant pages in a batch or individually, call `update_sitemap_tool` once to refresh the sitemap.
        Report the outcome.
        """
        self.agent_config['instruction'] = instruction
        super().initialize_agent(tools=tools)
    
    async def _is_page_assembled(self, task_id: str) -> bool:
        """Checks if the page for the given task_id exists in assembled_pages table."""
        sql = "SELECT EXISTS (SELECT 1 FROM assembled_pages WHERE task_id = %s);"
        try:
            with get_db_connection() as conn:
                if conn is None: return False
                with conn.cursor() as cur:
                    cur.execute(sql, (task_id,))
                    return cur.fetchone()[0]
        except psycopg2.Error as e:
            logger.error(f"DB error checking if page assembled for task {task_id}: {e}")
            return False
        return False

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a single publishing task using a Task Pydantic model.
        """
        task_id = task.task_id
        service_id = task.service_id
        zip_code = task.zip
        
        self.logger.info(f"Processing publish task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        process_result = {
            "task_id": task_id,
            "status": "error", # Default to error
            "message": "",
            "url": None,
            "dry_run": self.dry_run
        }

        try:
            if not await self._is_page_assembled(task_id):
                process_result["message"] = f"Assembled page not found in DB for task {task_id}. Cannot publish."
                raise FileNotFoundError(process_result["message"])
            
            # The ADK agent will call the tools. We form a prompt that guides it.
            # The tool itself now takes task_id, service_id, zip_code.
            prompt_text = (
                f"Publish the page for task_id '{task_id}' (service: {service_id}, zip: {zip_code}). "
                f"Current dry_run setting is {self.dry_run}. "
                "After publishing, ensure the sitemap is updated." # This might trigger sitemap tool too early if batching.
                                                                  # For now, assume one task = one sitemap update for simplicity.
            )
            
            llm_input_content = Content(role='user', parts=[Part(text=prompt_text)])
            session_id = f"publish_{task_id}"
            user_id = "website_expander_publisher"
            
            tool_call_results = [] # To store results from tool calls if ADK provides them this way

            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=llm_input_content
            ):
                if event.is_tool_code() and event.content:
                    # This block might be useful if we needed to inspect/log tool calls,
                    # but the actual tool execution result comes via is_tool_response().
                    pass
                if event.is_tool_response() and event.content:
                    for part in event.content.parts:
                        if part.tool_response:
                             tool_call_results.append(part.tool_response.response) # ADK v1.0 style
                
                if event.is_final_response() and event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                    process_result["message"] = response_text # LLM's summary
                    
                    # Analyze tool_call_results to find publish_page_tool's output
                    publish_tool_output = None
                    sitemap_tool_output = None
                    for res_dict in tool_call_results:
                        if not isinstance(res_dict, dict): continue # Ensure it's a dict
                        if 'url' in res_dict and res_dict.get('status') == 'success': # Heuristic for publish_page_tool
                            publish_tool_output = res_dict
                        if 'path' in res_dict and 'sitemap' in res_dict.get('message','').lower(): # Heuristic for sitemap
                            sitemap_tool_output = res_dict
                    
                    if publish_tool_output:
                        published_url = publish_tool_output.get('url')
                        if published_url:
                            self.queue_manager.update_task_status(task_id, PythonTaskStatus.PUBLISHED, url=published_url)
                            process_result["status"] = PythonTaskStatus.PUBLISHED.value
                            process_result["url"] = published_url
                            process_result["message"] = f"Successfully published (mocked): {published_url}. LLM: {response_text}"
                        else:
                            self.queue_manager.update_task_status(task_id, PythonTaskStatus.FAILED, error_message="Publish tool success but no URL.")
                            process_result["message"] = f"Publish tool reported success but no URL. LLM: {response_text}"
                    else: # publish_tool_output is None or indicates failure
                        # Attempt to get a more specific error from tool results if possible
                        err_msg = "Publishing failed or tool did not return expected output."
                        for res_dict in tool_call_results:
                            if isinstance(res_dict, dict) and res_dict.get('status') == 'error' and 'publish' in res_dict.get('message','').lower(): # Heuristic
                                err_msg = res_dict.get('error', err_msg)
                                break
                        self.queue_manager.update_task_status(task_id, PythonTaskStatus.FAILED, error_message=err_msg)
                        process_result["message"] = f"Publishing failed. Tool error: {err_msg}. LLM: {response_text}"

                    if sitemap_tool_output:
                         logger.info(f"Sitemap tool output: {sitemap_tool_output.get('message')}")
                    break # Exit on final response
            
            if process_result["status"] == "error" and not tool_call_results : # If loop finishes with no tool response and still error
                # This means LLM might not have called the tool or some other issue.
                default_error_msg = "LLM did not complete publishing actions or no tool response received."
                process_result["message"] = process_result.get("message", default_error_msg) if process_result.get("message") else default_error_msg
                self.queue_manager.update_task_status(task_id, PythonTaskStatus.FAILED, error_message=process_result["message"])


            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, process_result["status"], elapsed, process_result)
            return process_result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            logger.error(f"Critical error publishing page for task {task_id}: {str(e)}", exc_info=True)
            process_result["status"] = PythonTaskStatus.ERROR.value # System error
            process_result["message"] = str(e)
            # Update task status to ERROR to signify a system issue rather than just a publish failure
            self.queue_manager.update_task_status(task_id, PythonTaskStatus.ERROR, error_message=str(e))
            self.log_task_completion(task_id, "error", elapsed, process_result)
            return process_result
```
