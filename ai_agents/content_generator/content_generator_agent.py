#!/usr/bin/env python3
"""
Content Generator Agent for the Website Expansion Framework.

This module provides the Content Generator Agent implementation, responsible for
creating unique page content based on templates and SEO data.
It now uses a PostgreSQL database for data operations.
"""

import json # Still needed for serializing JSONB data for psycopg2
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

class ContentGeneratorAgent(BaseAgent):
    """
    Agent responsible for generating content for web pages.
    Uses PostgreSQL for data storage and retrieval.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the Content Generator Agent.
        
        Args:
            config_path: Path to the agent configuration file
        """
        super().__init__("content_generator", config_path)
        self.min_word_count = self.agent_config.get('min_word_count', 500)
        self.max_word_count = self.agent_config.get('max_word_count', 1500)
        self.max_title_length = self.agent_config.get('max_title_length', 60)
        self.max_meta_description_length = self.agent_config.get('max_meta_description_length', 155)

    def _get_default_template(self) -> Dict[str, Any]:
        """Returns a minimal default template if DB lookup fails."""
        return {
            "template_id": "default_fallback",
            "template_name": "Default Fallback Template",
            "sections": [
                {"id": "header", "type": "header", "instructions": "Create a page header."},
                {"id": "content", "type": "paragraph", "instructions": "Create page content."}
            ],
            "meta_template": {
                "title": "{service} in {city}, {state}",
                "description": "Professional {service} services in {city}, {state}."
            }
        }

    def _load_template(self, template_id: str = "standard_service_page") -> Dict[str, Any]:
        """
        Load a content template from the 'content_templates' table.
        """
        sql = "SELECT template_data FROM content_templates WHERE template_id = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for template {template_id}.")
                    return self._get_default_template()
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (template_id,))
                    row = cur.fetchone()
                    if row and row['template_data']:
                        logger.info(f"Template {template_id} loaded successfully from DB.")
                        return row['template_data'] # template_data is JSONB, returned as dict by DictCursor
                    else:
                        logger.warning(f"Template {template_id} not found in DB. Using default.")
                        return self._get_default_template()
        except psycopg2.Error as e:
            logger.error(f"DB error loading template {template_id}: {e}")
            return self._get_default_template()
        except Exception as e:
            logger.error(f"Unexpected error loading template {template_id}: {e}")
            return self._get_default_template()

    def _get_seo_research_data(self, task_id: str) -> Dict[str, Any]:
        """
        Get SEO research data for a task from the 'seo_research_data' table.
        """
        sql = """
            SELECT primary_keywords, secondary_keywords, competitor_analysis, seo_recommendations 
            FROM seo_research_data WHERE task_id = %s;
            """
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for SEO data (task {task_id}).")
                    return {}
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (task_id,))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"SEO research data for task {task_id} loaded successfully.")
                        # Convert row to dict, handling None for JSONB fields if necessary
                        return {
                            "primary_keywords": row["primary_keywords"] or [],
                            "secondary_keywords": row["secondary_keywords"] or [],
                            "competitor_analysis": row["competitor_analysis"] or {}, # Assuming JSONB
                            "seo_recommendations": row["seo_recommendations"] or ""
                        }
                    else:
                        logger.warning(f"SEO research data not found for task {task_id}.")
                        return {}
        except psycopg2.Error as e:
            logger.error(f"DB error loading SEO research data for task {task_id}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading SEO data for task {task_id}: {e}")
            return {}

    def _get_location_data(self, zip_code: str) -> Dict[str, Any]:
        """
        Get location data for a zip code from the 'locations' table.
        """
        sql = "SELECT zip_code, city, state, latitude, longitude FROM locations WHERE zip_code = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for location data (zip {zip_code}).")
                    return {}
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (zip_code,))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"Location data for zip {zip_code} loaded successfully.")
                        return dict(row)
                    else:
                        logger.warning(f"Location data not found for zip code {zip_code}.")
                        return {}
        except psycopg2.Error as e:
            logger.error(f"DB error loading location data for {zip_code}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading location data for {zip_code}: {e}")
            return {}

    def _get_service_data(self, service_id: str) -> Dict[str, Any]:
        """
        Get service data for a service ID from the 'services' table.
        """
        sql = "SELECT service_id, display_name, description, keywords FROM services WHERE service_id = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for service data ({service_id}).")
                    return {}
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (service_id,))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"Service data for {service_id} loaded successfully.")
                        return dict(row)
                    else:
                        logger.warning(f"Service data not found for service ID {service_id}.")
                        return {}
        except psycopg2.Error as e:
            logger.error(f"DB error loading service data for {service_id}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading service data for {service_id}: {e}")
            return {}
            
    def initialize_agent(self):
        """
        Initialize the Content Generator Agent with necessary tools.
        """
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to generate unique, high-quality content for location-based service pages.
        For each task:
        1. Use the provided SEO data (keywords, competitors) to guide your content creation
        2. Follow the template structure to create all required page sections
        3. Ensure content is locally relevant by incorporating location-specific information
        4. Optimize content for SEO by naturally including primary and secondary keywords
        5. Create compelling meta titles and descriptions that encourage clicks
        6. Generate content that meets the target word count and readability guidelines
        7. Ensure content is 100% unique and valuable to users searching for local services
        
        The generated content should be returned as a structured JSON object with separate
        fields for each section, meta data, and SEO elements.
        """
        self.agent_config['instruction'] = instruction
        super().initialize_agent()
    
    def _calculate_word_count(self, content_data: Dict[str, Any]) -> int:
        """Calculates word count from various text fields in content_data."""
        count = 0
        if not isinstance(content_data, dict):
            return 0
            
        for key, value in content_data.items():
            if isinstance(value, str):
                count += len(value.split())
            elif isinstance(value, list): # e.g., list of paragraphs for a section
                for item in value:
                    if isinstance(item, str):
                        count += len(item.split())
                    elif isinstance(item, dict) and 'text' in item and isinstance(item['text'], str): # for section items
                         count += len(item['text'].split())
            elif isinstance(value, dict): # Nested sections
                count += self._calculate_word_count(value)
        return count

    def _save_generated_content(self, task_id: str, content_data: Dict[str, Any], word_count: int) -> bool:
        """Saves the generated content to the 'generated_content' table."""
        sql = """
            INSERT INTO generated_content (task_id, content_data, word_count, generated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                content_data = EXCLUDED.content_data,
                word_count = EXCLUDED.word_count,
                generated_at = EXCLUDED.generated_at;
            """
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for saving content (task {task_id}).")
                    return False
                with conn.cursor() as cur:
                    # Serialize content_data dict to JSON string for JSONB field
                    json_content_data = json.dumps(content_data)
                    cur.execute(sql, (task_id, json_content_data, word_count, datetime.now()))
                    conn.commit()
                    logger.info(f"Generated content for task {task_id} saved to DB.")
                    return True
        except psycopg2.Error as e:
            logger.error(f"DB error saving content for task {task_id}: {e}")
            if conn: conn.rollback() # Ensure rollback if conn was obtained
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving content for task {task_id}: {e}")
            if conn: conn.rollback()
            return False

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a single content generation task using a Task Pydantic model.
        
        Args:
            task: The Task object to process.
            
        Returns:
            dict: Result of content generation, including status.
        """
        task_id = task.task_id
        service_id = task.service_id
        zip_code = task.zip # From Task model
        
        self.logger.info(f"Generating content for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        # Prepare result structure
        process_result = {
            "task_id": task_id,
            "service_id": service_id,
            "zip_code": zip_code,
            "status": "error", # Default to error
            "message": ""
        }

        try:
            # Load template and data using DB methods
            # Assuming a default template naming convention for now
            template_id = self.agent_config.get('default_template_id', f"{service_id}_default")
            template = self._load_template(template_id)
            if template['template_id'] == "default_fallback": # Check if actual template was found
                 logger.warning(f"Using fallback template for task {task_id} as {template_id} was not found.")


            seo_data = self._get_seo_research_data(task_id)
            location_data = self._get_location_data(zip_code) # task.city and task.state are already on Task obj
            service_data = self._get_service_data(service_id)
            
            # Use city/state from Task object if available, else from location_data
            city = task.city or location_data.get('city', '')
            state = task.state or location_data.get('state', '')
            service_display = service_data.get('display_name', service_id)
            
            if not city or not state:
                logger.warning(f"City/State information missing for task {task_id}. Content might be less specific.")
            if not service_display or service_display == service_id:
                 logger.warning(f"Service display name not found for {service_id}. Using ID.")


            # Prepare the prompt for the LLM
            prompt = f"Generate content for {service_display} services in {city}, {state} (zip code: {zip_code}). "
            prompt += f"The content should be between {self.min_word_count} and {self.max_word_count} words. "
            prompt += f"Meta title should be under {self.max_title_length} characters. Meta description under {self.max_meta_description_length} characters.\n"
            
            prompt += f"\nTemplate: {template.get('template_name', 'Default Template')}\n"
            for section in template.get('sections', []):
                prompt += f"- Section '{section.get('id', 'unknown_section')}': {section.get('instructions', 'No instructions.')}\n"
            
            if seo_data:
                keywords_primary = seo_data.get('primary_keywords', [])
                keywords_secondary = seo_data.get('secondary_keywords', [])
                if keywords_primary: prompt += f"\nPrimary keywords: {', '.join(keywords_primary)}"
                if keywords_secondary: prompt += f"\nSecondary keywords: {', '.join(keywords_secondary)}"
                prompt += f"\nSEO recommendations: {seo_data.get('seo_recommendations', 'N/A')}"
            
            service_description = service_data.get('description', '')
            service_keywords = service_data.get('keywords', [])
            if service_description: prompt += f"\n\nService description: {service_description}"
            if service_keywords: prompt += f"\nService-specific keywords: {', '.join(service_keywords)}"
            
            llm_content_input = Content(role='user', parts=[Part(text=prompt)])
            
            session_id = f"content_{task_id}"
            user_id = "website_expander_content_gen" # More specific user_id
            
            llm_generated_data: Optional[Dict[str, Any]] = None
            raw_response_text = ""

            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=llm_content_input
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    raw_response_text = event.content.parts[0].text
                    try:
                        import re
                        json_match = re.search(r'```json\n(.+?)\n```', raw_response_text, re.DOTALL)
                        if json_match:
                            llm_generated_data = json.loads(json_match.group(1))
                        else:
                            logger.warning(f"Content for task {task_id} not in structured JSON format. Raw response: {raw_response_text[:200]}...")
                            # Attempt to create a basic structure if LLM fails to provide JSON
                            llm_generated_data = {"raw_text_content": raw_response_text}
                    except Exception as e:
                        logger.error(f"Failed to parse LLM JSON response for task {task_id}: {e}. Raw: {raw_response_text[:200]}...")
                        llm_generated_data = {"parsing_error": str(e), "raw_text_content": raw_response_text}
                    break # Exit loop on final response
            
            if llm_generated_data:
                word_count = self._calculate_word_count(llm_generated_data)
                if self._save_generated_content(task_id, llm_generated_data, word_count):
                    process_result["status"] = "completed"
                    process_result["message"] = f"Content generated and saved. Word count: {word_count}."
                    process_result["generated_data_preview"] = {k: v[:100] if isinstance(v, str) else type(v).__name__ for k,v in llm_generated_data.items()} # Preview
                else:
                    process_result["message"] = "Failed to save generated content to DB."
                    # Status remains 'error'
            else:
                process_result["message"] = f"LLM did not return parsable content. Raw response: {raw_response_text[:200]}..."
                # Status remains 'error', save raw response as content if needed for debugging
                # You might want to save this raw response to the DB as well.
                # For now, it's just part of the error message.
                # Fallback save of raw response for debugging:
                if raw_response_text: # If there was any response at all
                    _ = self._save_generated_content(task_id, {"raw_llm_response": raw_response_text}, len(raw_response_text.split()))


            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, process_result["status"], elapsed, process_result)
            return process_result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            logger.error(f"Critical error generating content for task {task_id}: {str(e)}", exc_info=True)
            process_result["status"] = "error"
            process_result["message"] = str(e)
            self.log_task_completion(task_id, "error", elapsed, process_result)
            return process_result

```
