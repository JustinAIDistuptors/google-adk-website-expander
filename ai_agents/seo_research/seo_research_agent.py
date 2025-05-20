#!/usr/bin/env python3
"""
SEO Research Agent for the Website Expansion Framework.

This module provides the SEO Research Agent implementation, responsible for
gathering keywords and competitive intelligence for target pages.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import base agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

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
    
    def _create_serp_analysis_tool(self):
        """
        Create a tool for SERP analysis.
        
        Returns:
            callable: SERP analysis tool function
        """
        def serp_analysis_tool(query: str, location: str = None) -> Dict[str, Any]:
            """
            Analyzes search engine result pages for the given query and location.
            
            Args:
                query: Search query to analyze
                location: Optional location to target (e.g., "33442")
                
            Returns:
                dict: SERP analysis results including top ranking pages and keywords
            """
            # This is a mock implementation
            # In a real implementation, this would call a SERP API or use a web search tool
            
            self.logger.info(f"SERP analysis for query: {query}, location: {location}")
            
            # Mock results
            return {
                "query": query,
                "location": location,
                "top_results": [
                    {
                        "title": f"Best {query} in {location or 'Your Area'} | Professional Services",
                        "url": f"https://example.com/{query.lower().replace(' ', '-')}-{location or 'services'}",
                        "description": f"Looking for professional {query} in {location or 'your area'}? Our experienced team provides top-rated services. Call today!",
                        "position": 1
                    },
                    {
                        "title": f"{location or 'Local'} {query} - 24/7 Emergency Service",
                        "url": f"https://example.org/{query.lower().replace(' ', '-')}",
                        "description": f"Fast & reliable {query} service in {location or 'the area'}. Licensed professionals, free estimates, and affordable rates.",
                        "position": 2
                    }
                ],
                "common_keywords": [
                    f"{query} near me",
                    f"best {query} in {location or 'city'}",
                    f"emergency {query}",
                    f"professional {query} service",
                    f"affordable {query}"
                ]
            }
        
        return serp_analysis_tool
    
    def _create_keyword_generation_tool(self):
        """
        Create a tool for keyword generation.
        
        Returns:
            callable: Keyword generation tool function
        """
        def keyword_generation_tool(service: str, location: str = None) -> Dict[str, Any]:
            """
            Generates keyword sets for the given service and location.
            
            Args:
                service: Service type (e.g., "plumber")
                location: Optional location to target (e.g., "33442")
                
            Returns:
                dict: Generated keyword sets
            """
            # This is a mock implementation
            # In a real implementation, this would use keyword research APIs
            
            self.logger.info(f"Keyword generation for service: {service}, location: {location}")
            
            # Get location data for context
            location_data = self._get_location_data(location) if location else None
            city = location_data.get('city', '') if location_data else ''
            state = location_data.get('state', '') if location_data else ''
            
            # Mock results
            return {
                "service": service,
                "location": location,
                "primary_keywords": [
                    f"{service} {location}" if location else service,
                    f"{service} {city} {state}" if city and state else f"{service} near me"
                ],
                "secondary_keywords": [
                    f"best {service} in {city}" if city else f"best {service}",
                    f"professional {service} {location}" if location else f"professional {service}",
                    f"licensed {service} {city}" if city else f"licensed {service}",
                    f"emergency {service} service"
                ],
                "long_tail_keywords": [
                    f"{service} service cost in {city}" if city else f"{service} service cost",
                    f"24 hour {service} in {location}" if location else f"24 hour {service}",
                    f"affordable {service} in {city} {state}" if city and state else f"affordable {service} near me",
                    f"best rated {service} {city}" if city else f"best rated {service}"
                ]
            }
        
        return keyword_generation_tool
    
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
            self._create_serp_analysis_tool(),
            self._create_keyword_generation_tool()
            # Add more SEO tools as needed
        ]
        
        # Additional agent-specific instruction based on SEO parameters
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to conduct comprehensive SEO research for location-based service pages.
        For each task:
        1. Analyze the service type and location to understand the target audience and intent
        2. Generate primary, secondary, and long-tail keywords optimized for local search
        3. Analyze top-ranking competitor pages to identify content patterns and keyword usage
        4. Create a comprehensive SEO strategy that includes:
           - Recommended primary and secondary keywords
           - Title tag and meta description templates
           - Content structure recommendations
           - Local relevance factors to include
        
        Ensure all recommendations are tailored to the specific service and location combination.
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
            content = Content(
                role='user',
                parts=[Part(text=f"Conduct SEO research for {service_display} services in {city}, {state} (zip code: {zip_code}). "
                            f"Generate primary and secondary keywords, analyze competitors, and create a comprehensive SEO strategy. "
                            f"Consider these service-specific keywords as a starting point: {', '.join(service_keywords)}.")]
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
                }
            }
            
            # Process the task using the SEO Research Agent
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
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
                            result.update(seo_data)
                        else:
                            # Process unstructured text response
                            result["keywords"] = {
                                "primary": [],
                                "secondary": [],
                                "long_tail": []
                            }
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
