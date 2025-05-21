#!/usr/bin/env python3
"""
Page Assembler Agent for the Website Expansion Framework.

This module provides the Page Assembler Agent implementation, responsible for
building complete HTML pages with proper structure from generated content.
It now uses a PostgreSQL database for data operations.
"""

import json # For JSONB serialization and schema markup
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import psycopg2
from psycopg2 import extras # For dict cursor

# Import base agent
import sys
import os # Keep os for sys.path manipulation for now
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part

# Database connection utility (temporary import path)
from src.utils.queue_manager import get_db_connection
from src.models.task import Task # Assuming Task Pydantic model is passed

logger = logging.getLogger(__name__)

class PageAssemblerAgent(BaseAgent):
    """
    Agent responsible for assembling HTML pages from generated content.
    Uses PostgreSQL for data storage and retrieval.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the Page Assembler Agent.
        """
        super().__init__("page_assembler", config_path)
        # self.template_directory = self.agent_config.get('template_directory', './data/templates') # Less relevant now

    def _get_default_html_template_string(self) -> str:
        """Returns a very basic HTML template string if DB lookup fails."""
        return """
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{meta_title}</title></head>
        <body><h1>{h1_title}</h1><div>{main_content}</div></body></html>
        """

    def _get_html_template(self, template_id: str) -> str:
        """
        Get an HTML template string from the 'content_templates' table.
        Assumes 'template_data' in the DB is a JSONB field containing a key like 'html_body_template'.
        """
        sql = "SELECT template_data FROM content_templates WHERE template_id = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for HTML template {template_id}.")
                    return self._get_default_html_template_string()
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (template_id,))
                    row = cur.fetchone()
                    if row and row['template_data'] and isinstance(row['template_data'], dict):
                        # Attempt to find a specific key for the HTML body.
                        # This part is an assumption of how HTML might be stored in a structured template.
                        html_str = row['template_data'].get('html_body_template', 
                                   row['template_data'].get('html_template', 
                                   row['template_data'].get('template_string'))) # Check common keys
                        if html_str and isinstance(html_str, str):
                             logger.info(f"HTML template {template_id} loaded successfully from DB.")
                             return html_str
                        else:
                            logger.warning(f"HTML string not found in template_data for {template_id} (keys: {row['template_data'].keys()}). Using default.")
                            return self._get_default_html_template_string()
                    else:
                        logger.warning(f"HTML template {template_id} not found or not a dict in DB. Using default.")
                        return self._get_default_html_template_string()
        except psycopg2.Error as e:
            logger.error(f"DB error loading HTML template {template_id}: {e}")
            return self._get_default_html_template_string()
        except Exception as e:
            logger.error(f"Unexpected error loading HTML template {template_id}: {e}")
            return self._get_default_html_template_string()

    def _get_content_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get generated content data for a task from the 'generated_content' table.
        """
        sql = "SELECT content_data FROM generated_content WHERE task_id = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for content data (task {task_id}).")
                    return None
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (task_id,))
                    row = cur.fetchone()
                    if row and row['content_data']:
                        logger.info(f"Content data for task {task_id} loaded successfully.")
                        return row['content_data'] # content_data is JSONB, returned as dict
                    else:
                        logger.warning(f"Content data not found for task {task_id}.")
                        return None
        except psycopg2.Error as e:
            logger.error(f"DB error loading content data for task {task_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading content data for task {task_id}: {e}")
            return None
    
    def _generate_schema_markup(self, content_data: Dict[str, Any], task: Task) -> Dict[str, Any]:
        """
        Generate schema.org markup dictionary for the page.
        """
        # Extract relevant info from content_data and task
        # This is a simplified example; real implementation would be more robust
        page_title = content_data.get('meta_title', content_data.get('title', f"Service in {task.city}"))
        description = content_data.get('meta_description', content_data.get('introduction', 'N/A'))

        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness", # Or more specific type based on service
            "name": page_title,
            "description": description,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": task.city,
                "addressRegion": task.state,
                "postalCode": task.zip,
                "addressCountry": "US" # Assuming US, make configurable if needed
            }
            # Add more fields like geo, telephone, openingHours, etc.
        }
        # Add service type if available
        service_data = content_data.get('service_details', {})
        if isinstance(service_data, dict) and 'name' in service_data :
            schema['hasOffer'] = {
                "@type": "Offer",
                "itemOffered": {
                    "@type": "Service",
                    "name": service_data.get('name', task.service_id)
                }
            }
        return schema

    def _save_assembled_page(self, task_id: str, html_content: str, schema_markup: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
        """Saves the assembled page data to the 'assembled_pages' table."""
        sql = """
            INSERT INTO assembled_pages (task_id, html_content, schema_markup, metadata, assembled_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                html_content = EXCLUDED.html_content,
                schema_markup = EXCLUDED.schema_markup,
                metadata = EXCLUDED.metadata,
                assembled_at = EXCLUDED.assembled_at;
            """
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for saving assembled page (task {task_id}).")
                    return False
                with conn.cursor() as cur:
                    json_schema_markup = json.dumps(schema_markup)
                    json_metadata = json.dumps(metadata)
                    cur.execute(sql, (task_id, html_content, json_schema_markup, json_metadata, datetime.now()))
                    conn.commit()
                    logger.info(f"Assembled page for task {task_id} saved to DB.")
                    return True
        except psycopg2.Error as e:
            logger.error(f"DB error saving assembled page for task {task_id}: {e}")
            if conn: conn.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving assembled page for task {task_id}: {e}")
            if conn: conn.rollback()
            return False

    def initialize_agent(self):
        """Initialize the Page Assembler Agent."""
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to assemble complete HTML pages from structured content data using a provided HTML template.
        For each task:
        1. Take the structured content (JSON format) generated for a specific service and location.
        2. Take the base HTML template string.
        3. Intelligently and accurately substitute placeholders in the HTML template with the corresponding values from the content JSON. Common placeholders might include {meta_title}, {meta_description}, {h1_title}, {main_content}, {faq_title}, {faq_content}, {cta_title}, {cta_content}, {current_year}.
        4. The content for sections like 'main_content' or 'faq_content' might be complex (e.g., multiple paragraphs, lists, or sub-headings from the JSON). Format these appropriately into valid HTML.
        5. Generate appropriate schema.org markup (JSON-LD) based on the content and include it in the <head> of the HTML.
        6. Ensure all meta tags and SEO elements are properly formatted.
        7. Generate valid, well-structured HTML that is ready for publishing.
        
        The final output should ONLY be the complete HTML content of the assembled page. Do NOT include any explanations or markdown formatting like ```html ... ```.
        """
        self.agent_config['instruction'] = instruction
        super().initialize_agent()
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a single page assembly task using a Task Pydantic model.
        """
        task_id = task.task_id
        service_id = task.service_id # Available from Task model
        zip_code = task.zip         # Available from Task model
        
        self.logger.info(f"Assembling page for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()

        process_result = {
            "task_id": task_id,
            "status": "error", # Default to error
            "message": ""
        }
        
        try:
            content_data = self._get_content_data(task_id)
            if not content_data:
                process_result["message"] = f"Content data not found for task {task_id}."
                raise ValueError(process_result["message"])
            
            # Determine template_id (e.g., from agent config or convention)
            template_id = self.agent_config.get('default_html_template_id', f"{service_id}_html_default")
            html_template_string = self._get_html_template(template_id)
            if html_template_string == self._get_default_html_template_string():
                 logger.warning(f"Using fallback HTML template for task {task_id} as {template_id} was not found or suitable.")

            # Prepare schema.org markup (as a dictionary first)
            schema_org_dict = self._generate_schema_markup(content_data, task)
            schema_org_json_string_for_html = json.dumps(schema_org_dict, indent=2) # For embedding in HTML
            
            # Prepare the prompt for the LLM
            # Convert dicts to JSON strings for inclusion in the prompt
            content_json_for_prompt = json.dumps(content_data, indent=2)
            
            prompt = (
                f"Assemble an HTML page for {service_id} services in {task.city}, {task.state} (zip: {zip_code}).\n"
                f"Use the following HTML template string:\n```html\n{html_template_string}\n```\n\n"
                f"Use the following content data (JSON format) to populate the template:\n```json\n{content_json_for_prompt}\n```\n\n"
                f"The schema.org JSON-LD to be included in the <head> is:\n```json\n{schema_org_json_string_for_html}\n```\n\n"
                "Instructions for assembly:\n"
                "1. Replace placeholders in the HTML template (like {meta_title}, {h1_title}, {main_content}, etc.) with corresponding values from the content data.\n"
                "2. If content data provides structured sections (e.g., paragraphs, lists), format them into appropriate HTML tags.\n"
                "3. Embed the provided schema.org JSON-LD string within a <script type=\"application/ld+json\"> tag in the <head> section.\n"
                "4. Ensure the final output is ONLY the complete, valid HTML content of the page. Do not add any explanations or markdown."
            )
            
            llm_input_content = Content(role='user', parts=[Part(text=prompt)])
            session_id = f"assembly_{task_id}"
            user_id = "website_expander_page_assembler"
            
            final_html_content: Optional[str] = None
            
            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=llm_input_content
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                    # Expect LLM to return only the HTML content based on refined prompt
                    final_html_content = response_text.strip()
                    # Basic check if it looks like HTML
                    if not (final_html_content.startswith("<!DOCTYPE html>") or final_html_content.startswith("<html>")):
                        logger.warning(f"LLM response for task {task_id} does not look like full HTML. Using as is. Preview: {final_html_content[:200]}")
                    break 
            
            if final_html_content:
                page_metadata = {
                    "source_template_id": template_id,
                    "llm_assembly_model": self.llm.model_name if self.llm else "unknown",
                    "url_slug_suggestion": f"{service_id.replace('_', '-')}/{task.zip}-{task.city.lower().replace(' ', '-')}"
                }
                
                if self._save_assembled_page(task_id, final_html_content, schema_org_dict, page_metadata):
                    process_result["status"] = "completed"
                    process_result["message"] = "Page assembled and saved to DB."
                    process_result["html_preview"] = final_html_content[:250] # Add a small preview
                else:
                    process_result["message"] = "Failed to save assembled page to DB."
                    # status remains 'error'
            else:
                process_result["message"] = f"LLM did not return assemblable HTML content for task {task_id}."
                # status remains 'error'

            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, process_result["status"], elapsed, process_result)
            return process_result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            logger.error(f"Critical error assembling page for task {task_id}: {str(e)}", exc_info=True)
            process_result["status"] = "error"
            process_result["message"] = str(e)
            self.log_task_completion(task_id, "error", elapsed, process_result)
            return process_result

```
