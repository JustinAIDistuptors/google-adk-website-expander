#!/usr/bin/env python3
"""
SEO Research Agent for the Website Expansion Framework.

This module provides the SEO Research Agent implementation, responsible for
gathering keywords and competitive intelligence for target pages.
"""

import os
import json
import yaml
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# Import base agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

# Import SEO research tools
from ai_agents.seo_research.tools.serp_analyzer import create_serp_analysis_tool
from ai_agents.seo_research.tools.keyword_generator import create_keyword_generation_tool
from ai_agents.seo_research.tools.content_analyzer import create_content_analysis_tool

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

class SeoResearchAgent(BaseAgent):
    """
    Agent responsible for SEO research and keyword analysis.
    
    The SEO Research Agent analyzes competitor pages, identifies keywords and semantic terms,
    and builds a comprehensive SEO strategy for each target page.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the SEO Research Agent.
        
        Args:
            config_path: Path to the agent configuration file
        """
        super().__init__("seo_research", config_path)
        self.max_competitor_pages = self.agent_config.get('max_competitor_pages', 5)
        self.max_keywords_per_page = self.agent_config.get('max_keywords_per_page', 20)
        
        # Load SEO parameters
        self.seo_params = self._load_seo_parameters()
        
        # Create output directory
        os.makedirs("data/seo_research", exist_ok=True)
    
    def _load_seo_parameters(self) -> Dict[str, Any]:
        """
        Load SEO parameters from configuration.
        
        Returns:
            dict: SEO parameters
        """
        try:
            with open("config/seo_parameters.yaml", 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load SEO parameters: {str(e)}")
            # Return default SEO parameters
            return {
                'seo_targets': {
                    'min_keyword_density': 1.0,
                    'max_keyword_density': 3.0,
                    'title_max_length': 60,
                    'meta_description_max_length': 155
                },
                'keyword_strategies': {
                    'primary_keyword_count': 1,
                    'secondary_keyword_count': 3
                }
            }
    
    def _get_location_data(self, zip_code: str) -> Dict[str, Any]:
        """
        Get location data for a zip code.
        
        Args:
            zip_code: The zip code to look up
            
        Returns:
            dict: Location data (city, state, etc.)
        """
        try:
            with open("data/locations/locations.json", 'r') as f:
                locations = json.load(f)
                
                for location in locations:
                    if location.get('zip') == zip_code:
                        return location
                
                return {}
        except Exception as e:
            self.logger.error(f"Failed to get location data for {zip_code}: {str(e)}")
            return {}
    
    def _get_service_data(self, service_id: str) -> Dict[str, Any]:
        """
        Get service data for a service ID.
        
        Args:
            service_id: The service ID to look up
            
        Returns:
            dict: Service data
        """
        try:
            with open("data/services/services.json", 'r') as f:
                services = json.load(f)
                
                for service in services:
                    if service.get('service_id') == service_id:
                        return service
                
                return {}
        except Exception as e:
            self.logger.error(f"Failed to get service data for {service_id}: {str(e)}")
            return {}
    
    def initialize_agent(self):
        """
        Initialize the SEO Research Agent with necessary tools.
        """
        # Create SEO research tools
        tools = [
            create_serp_analysis_tool(),
            create_keyword_generation_tool(),
            create_content_analysis_tool()
        ]
        
        # Additional agent-specific instruction based on SEO parameters
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to conduct comprehensive SEO research for location-based service pages.
        For each task:
        
        1. Analyze the service type and location to understand the target audience and intent.
        
        2. Use the keyword_generation_tool to generate primary, secondary, and long-tail keywords 
           optimized for local search. Pay special attention to user intent categories (informational,
           navigational, transactional, commercial).
        
        3. Use the serp_analysis_tool to analyze top-ranking competitor pages for the target keywords.
           Extract insights about title formats, meta descriptions, and common content elements.
        
        4. Use the content_analysis_tool to get deeper insights into the content structure, headings,
           and local relevance factors that contribute to high rankings.
        
        5. Create a comprehensive SEO strategy that includes:
           - Recommended primary and secondary keywords with clear intent mapping
           - Title tag and meta description templates optimized for CTR
           - Content structure recommendations (headings, sections, word count)
           - Local relevance factors to include for better local search visibility
           - Schema markup recommendations for rich results
        
        Ensure all recommendations are tailored to the specific service and location combination,
        focusing on local search intent for "near me" queries.
        
        Return your findings as a structured JSON object with clear sections for each aspect of the
        SEO strategy. Include a natural language summary of your recommendations for the content team.
        """
        
        self.agent_config['instruction'] = instruction
        
        # Initialize the agent with the tools
        super().initialize_agent(tools=tools)
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single SEO research task.
        
        Args:
            task: The task to process, including service and location
            
        Returns:
            dict: SEO research results
        """
        task_id = task.get('task_id')
        service_id = task.get('service_id')
        zip_code = task.get('zip')
        
        self.logger.info(f"Processing SEO research for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        try:
            # Get additional context data
            location_data = self._get_location_data(zip_code)
            service_data = self._get_service_data(service_id)
            
            city = location_data.get('city', '')
            state = location_data.get('state', '')
            service_display = service_data.get('display_name', service_id)
            service_keywords = service_data.get('keywords', [])
            
            # Prepare the message for the agent
            prompt = f"Conduct comprehensive SEO research for {service_display} services in {city}, {state} (zip code: {zip_code}). "
            prompt += f"Generate primary and secondary keywords, analyze competitors, and create a complete SEO strategy. "
            prompt += f"Consider these service-specific keywords: {', '.join(service_keywords)}. "
            prompt += f"Focus on local search intent for users looking for services 'near me'.\n\n"
            
            # Add specific tool usage instructions
            prompt += "Follow these steps:\n"
            prompt += "1. Use the keyword_generation_tool to generate keyword sets\n"
            prompt += "2. Use the serp_analysis_tool to analyze search results for primary keywords\n"
            prompt += "3. Use the content_analysis_tool to analyze content patterns from top ranking pages\n"
            prompt += "4. Synthesize all data into a comprehensive SEO strategy\n\n"
            
            # Add format instructions
            prompt += "Return your findings as a JSON object with these sections:\n"
            prompt += "- keywords: Primary, secondary, and long-tail keywords\n"
            prompt += "- serp_insights: Insights from search results analysis\n"
            prompt += "- content_strategy: Recommendations for content structure\n"
            prompt += "- metadata: Title and meta description templates\n"
            prompt += "- local_relevance: How to optimize for local search\n"
            prompt += "- schema_markup: Recommended structured data\n"
            prompt += "- summary: Natural language summary of all findings"
            
            content = Content(
                role='user',
                parts=[Part(text=prompt)]
            )
            
            # Generate a unique session ID for this task
            session_id = f"seo_{task_id}"
            user_id = "website_expander"
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "location": {
                    "city": city,
                    "state": state
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Process the task using the SEO Research Agent
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                # Process function calls (tool usage)
                function_calls = event.get_function_calls()
                if function_calls:
                    # Log tool usage for debugging
                    for function_call in function_calls:
                        self.logger.info(f"Tool call: {function_call.name} with args: {function_call.args}")
                
                # Process function responses (tool results)
                function_responses = event.get_function_responses()
                if function_responses:
                    # Record tool results for output
                    for function_response in function_responses:
                        tool_name = function_response.function_call_id.split('/')[-1]
                        if 'keyword' in tool_name.lower():
                            result["keyword_data"] = function_response.response
                        elif 'serp' in tool_name.lower():
                            result["serp_data"] = function_response.response
                        elif 'content' in tool_name.lower():
                            result["content_data"] = function_response.response
                
                # Check for the final response
                if event.is_final_response() and event.content and event.content.parts:
                    # Try to parse the structured data from the response
                    response_text = event.content.parts[0].text
                    try:
                        # Extract JSON data if present
                        import re
                        json_match = re.search(r'```json\n(.+?)\n```', response_text, re.DOTALL)
                        
                        if json_match:
                            seo_data = json.loads(json_match.group(1))
                            result["seo_strategy"] = seo_data
                        else:
                            # Process unstructured text response
                            result["seo_recommendations"] = response_text
                    except Exception as e:
                        self.logger.error(f"Failed to parse SEO results: {str(e)}")
                        result["seo_recommendations"] = response_text
            
            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, "completed", elapsed, result)
            
            # Save the SEO research results
            output_dir = f"data/seo_research"
            os.makedirs(output_dir, exist_ok=True)
            with open(f"{output_dir}/{task_id}.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            self.logger.error(f"Error processing SEO research for task {task_id}: {str(e)}")
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "status": "error",
                "error": str(e)
            }
            
            self.log_task_completion(task_id, "error", elapsed, result)
            return result
