#!/usr/bin/env python3
"""
SEO Research Agent for the Website Expansion Framework.

This module provides the SEO Research Agent implementation, responsible for
gathering keywords and competitive intelligence for target pages.
It now uses a PostgreSQL database for its data operations.
"""

import json # For JSONB serialization
import yaml
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

# Import SEO research tools
from ai_agents.seo_research.tools.serp_analyzer import create_serp_analysis_tool
from ai_agents.seo_research.tools.keyword_generator import create_keyword_generation_tool
from ai_agents.seo_research.tools.content_analyzer import create_content_analysis_tool

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part

# Database connection utility & Task model
from src.utils.queue_manager import get_db_connection
from src.models.task import Task

logger = logging.getLogger(__name__)

class SeoResearchAgent(BaseAgent):
    """
    Agent responsible for SEO research and keyword analysis.
    Uses PostgreSQL for data storage and retrieval.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the SEO Research Agent.
        """
        super().__init__("seo_research", config_path)
        self.max_competitor_pages = self.agent_config.get('max_competitor_pages', 5)
        self.max_keywords_per_page = self.agent_config.get('max_keywords_per_page', 20)
        self.seo_params = self._load_seo_parameters()
        # Removed: os.makedirs("data/seo_research", exist_ok=True)
    
    def _load_seo_parameters(self) -> Dict[str, Any]:
        """Load SEO parameters from configuration."""
        try:
            with open("config/seo_parameters.yaml", 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load SEO parameters: {str(e)}")
            return { # Minimal default
                'seo_targets': {'min_keyword_density': 1.0},
                'keyword_strategies': {'primary_keyword_count': 1}
            }
    
    def _get_location_data(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """Get location data for a zip code from the 'locations' table."""
        sql = "SELECT city, state, latitude, longitude FROM locations WHERE zip_code = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for location data (zip {zip_code}).")
                    return None
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (zip_code,))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"Location data for zip {zip_code} loaded successfully.")
                        return dict(row)
                    else:
                        logger.warning(f"Location data not found for zip code {zip_code}.")
                        return None
        except psycopg2.Error as e:
            logger.error(f"DB error loading location data for {zip_code}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading location data for {zip_code}: {e}")
            return None

    def _get_service_data(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get service data for a service ID from the 'services' table."""
        sql = "SELECT display_name, description, keywords FROM services WHERE service_id = %s;"
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for service data ({service_id}).")
                    return None
                with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                    cur.execute(sql, (service_id,))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"Service data for {service_id} loaded successfully.")
                        return dict(row)
                    else:
                        logger.warning(f"Service data not found for service ID {service_id}.")
                        return None
        except psycopg2.Error as e:
            logger.error(f"DB error loading service data for {service_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading service data for {service_id}: {e}")
            return None

    def _save_seo_research_data(self, task_id: str, primary_keywords: List[str], 
                                secondary_keywords: List[str], competitor_analysis: Dict[str, Any], 
                                seo_recommendations: str) -> bool:
        """Saves the SEO research data to the 'seo_research_data' table."""
        sql = """
            INSERT INTO seo_research_data 
                (task_id, primary_keywords, secondary_keywords, competitor_analysis, seo_recommendations, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO UPDATE SET
                primary_keywords = EXCLUDED.primary_keywords,
                secondary_keywords = EXCLUDED.secondary_keywords,
                competitor_analysis = EXCLUDED.competitor_analysis,
                seo_recommendations = EXCLUDED.seo_recommendations,
                updated_at = EXCLUDED.updated_at;
        """
        current_time = datetime.now()
        try:
            with get_db_connection() as conn:
                if conn is None:
                    logger.error(f"Failed to get DB connection for saving SEO data (task {task_id}).")
                    return False
                with conn.cursor() as cur:
                    json_competitor_analysis = json.dumps(competitor_analysis)
                    cur.execute(sql, (
                        task_id, primary_keywords, secondary_keywords, 
                        json_competitor_analysis, seo_recommendations, 
                        current_time, current_time
                    ))
                    conn.commit()
                    logger.info(f"SEO research data for task {task_id} saved to DB.")
                    return True
        except psycopg2.Error as e:
            logger.error(f"DB error saving SEO data for task {task_id}: {e}")
            if conn: conn.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving SEO data for task {task_id}: {e}")
            if conn: conn.rollback()
            return False

    def initialize_agent(self):
        """Initialize the SEO Research Agent with necessary tools."""
        tools = [
            create_serp_analysis_tool(),
            create_keyword_generation_tool(),
            create_content_analysis_tool()
        ]
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to conduct comprehensive SEO research for location-based service pages.
        For each task:
        1. Analyze the service type and location to understand the target audience and intent.
        2. Use the keyword_generation_tool to generate primary, secondary, and long-tail keywords.
        3. Use the serp_analysis_tool to analyze top-ranking competitor pages.
        4. Use the content_analysis_tool to get deeper insights into content structure.
        5. Create a comprehensive SEO strategy.
        Return your findings as a structured JSON object with these sections:
           - keywords: {"primary": ["kw1", "kw2"], "secondary": ["kw3", "kw4"], "long_tail": ["ltkw1"]}
           - competitor_analysis: {"top_competitors": [{"url": "...", "title": "...", "strengths": ["..."]}, ...], "common_themes": ["..."]}
           - content_strategy: {"recommended_headings": ["H1", "H2: Topic A", "H2: Topic B"], "word_count_target": 750, "internal_linking_suggestions": ["link to X page"]}
           - metadata_templates: {"title": "Best {service} in {city} | CompanyName", "meta_description": "Get expert {service} in {city}, {state}. Call CompanyName today for a free quote!"}
           - local_relevance_factors: ["mention local landmarks", "include city/state in H1/meta", "NAP consistency"]
           - schema_markup_recommendations: ["LocalBusiness", "FAQPage", "Service"]
           - seo_summary_text: "A natural language summary of all findings and recommendations."
        """
        self.agent_config['instruction'] = instruction
        super().initialize_agent(tools=tools)
    
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """
        Process a single SEO research task using a Task Pydantic model.
        """
        task_id = task.task_id
        service_id = task.service_id
        zip_code = task.zip # From Task model
        
        self.logger.info(f"Processing SEO research for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()

        process_result = {
            "task_id": task_id,
            "status": "error", # Default to error
            "message": ""
        }
        
        try:
            location_data = self._get_location_data(zip_code)
            service_data = self._get_service_data(service_id)
            
            city = task.city or (location_data.get('city', '') if location_data else '')
            state = task.state or (location_data.get('state', '') if location_data else '')
            service_display = service_data.get('display_name', service_id) if service_data else service_id
            service_base_keywords = service_data.get('keywords', []) if service_data else []
            
            if not city or not state:
                logger.warning(f"City/State information missing for task {task_id}. SEO research might be less effective.")
            
            prompt = f"Conduct comprehensive SEO research for {service_display} services in {city}, {state} (zip code: {zip_code}). "
            prompt += f"Base service keywords: {', '.join(service_base_keywords) if service_base_keywords else 'N/A'}. "
            prompt += "Focus on local search intent. Follow the structured JSON output format specified in your instructions."
            
            llm_input_content = Content(role='user', parts=[Part(text=prompt)])
            session_id = f"seo_{task_id}"
            user_id = "website_expander_seo_agent"
            
            llm_response_json: Optional[Dict[str, Any]] = None
            raw_response_text = ""

            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=llm_input_content
            ):
                # Tool calls and responses are handled by the ADK runner and tools themselves.
                # We are interested in the final aggregated response from the LLM.
                if event.is_final_response() and event.content and event.content.parts:
                    raw_response_text = event.content.parts[0].text
                    try:
                        import re
                        json_match = re.search(r'```json\n(.+?)\n```', raw_response_text, re.DOTALL)
                        if json_match:
                            llm_response_json = json.loads(json_match.group(1))
                        else:
                            # Try to parse the whole string if no markdown block found
                            llm_response_json = json.loads(raw_response_text) 
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response for task {task_id}: {e}. Raw: {raw_response_text[:300]}...")
                        # Store raw text for manual review if parsing fails
                        llm_response_json = {"parsing_error": str(e), "raw_seo_recommendations": raw_response_text}
                    break 
            
            if llm_response_json:
                # Extract data for DB insertion based on expected structure
                keywords_data = llm_response_json.get('keywords', {})
                primary_keywords = keywords_data.get('primary', [])
                secondary_keywords = keywords_data.get('secondary', [])
                # long_tail_keywords = keywords_data.get('long_tail', []) # Not in seo_research_data table schema directly

                competitor_analysis_data = llm_response_json.get('competitor_analysis', {})
                
                # seo_summary_text is a good candidate for seo_recommendations field
                seo_recommendations_text = llm_response_json.get('seo_summary_text', 
                                           llm_response_json.get('summary', raw_response_text if "parsing_error" in llm_response_json else "No summary provided."))

                if not isinstance(primary_keywords, list): primary_keywords = [str(primary_keywords)]
                if not isinstance(secondary_keywords, list): secondary_keywords = [str(secondary_keywords)]
                if not isinstance(competitor_analysis_data, dict): competitor_analysis_data = {"raw": str(competitor_analysis_data)}
                if not isinstance(seo_recommendations_text, str): seo_recommendations_text = str(seo_recommendations_text)


                if self._save_seo_research_data(task_id, primary_keywords, secondary_keywords, 
                                                competitor_analysis_data, seo_recommendations_text):
                    process_result["status"] = "completed"
                    process_result["message"] = "SEO research completed and data saved to DB."
                else:
                    process_result["message"] = "SEO research completed but failed to save data to DB."
                    # status remains 'error'
            else:
                process_result["message"] = f"LLM did not return usable SEO data for task {task_id}. Raw response: {raw_response_text[:300]}..."
                # status remains 'error'

            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, process_result["status"], elapsed, process_result)
            return process_result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            logger.error(f"Critical error processing SEO research for task {task_id}: {str(e)}", exc_info=True)
            process_result["status"] = "error"
            process_result["message"] = str(e)
            self.log_task_completion(task_id, "error", elapsed, process_result)
            return process_result
```
