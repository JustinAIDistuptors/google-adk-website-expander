#!/usr/bin/env python3
"""
Content Generator Agent for the Website Expansion Framework.

This module provides the Content Generator Agent implementation, responsible for
creating unique page content based on templates and SEO data.
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

class ContentGeneratorAgent(BaseAgent):
    """
    Agent responsible for generating content for web pages.
    
    The Content Generator Agent creates unique, SEO-optimized content for each
    location-based service page based on templates and SEO research data.
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
    
    def _load_template(self, template_id: str = "standard_service_page") -> Dict[str, Any]:
        """
        Load a content template.
        
        Args:
            template_id: Template identifier
            
        Returns:
            dict: The template data
        """
        try:
            template_path = f"data/templates/{template_id}.json"
            with open(template_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load template {template_id}: {str(e)}")
            # Return a minimal default template
            return {
                "template_id": "default",
                "template_name": "Default Template",
                "sections": [
                    {
                        "id": "header",
                        "type": "header",
                        "instructions": "Create a page header."
                    },
                    {
                        "id": "content",
                        "type": "paragraph",
                        "instructions": "Create page content."
                    }
                ],
                "meta_template": {
                    "title": "{service} in {city}, {state}",
                    "description": "Professional {service} services in {city}, {state}."
                }
            }
    
    def _get_seo_research_data(self, task_id: str) -> Dict[str, Any]:
        """
        Get SEO research data for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            dict: SEO research data
        """
        try:
            seo_path = f"data/seo_research/{task_id}.json"
            if os.path.exists(seo_path):
                with open(seo_path, 'r') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"SEO research data not found for task {task_id}")
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load SEO research data for task {task_id}: {str(e)}")
            return {}
    
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
        Initialize the Content Generator Agent with necessary tools.
        """
        # Additional agent-specific instruction
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
        
        # Initialize the agent
        super().initialize_agent()
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single content generation task.
        
        Args:
            task: The task to process, including service and location
            
        Returns:
            dict: Generated content
        """
        task_id = task.get('task_id')
        service_id = task.get('service_id')
        zip_code = task.get('zip')
        
        self.logger.info(f"Generating content for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        try:
            # Load template and data
            template = self._load_template()
            seo_data = self._get_seo_research_data(task_id)
            location_data = self._get_location_data(zip_code)
            service_data = self._get_service_data(service_id)
            
            city = location_data.get('city', '')
            state = location_data.get('state', '')
            service_display = service_data.get('display_name', service_id)
            
            # Prepare the message for the agent
            prompt = f"Generate content for {service_display} services in {city}, {state} (zip code: {zip_code}). "
            prompt += f"The content should be between {self.min_word_count} and {self.max_word_count} words. "
            
            # Add template details
            prompt += f"\n\nTemplate: {template['template_name']}\n"
            for section in template['sections']:
                prompt += f"- {section['id']}: {section['instructions']}\n"
            
            # Add SEO data if available
            if seo_data:
                keywords_primary = seo_data.get('keywords', {}).get('primary', [])
                keywords_secondary = seo_data.get('keywords', {}).get('secondary', [])
                
                if keywords_primary:
                    prompt += f"\nPrimary keywords: {', '.join(keywords_primary)}"
                if keywords_secondary:
                    prompt += f"\nSecondary keywords: {', '.join(keywords_secondary)}"
                
                prompt += f"\n\nSEO recommendations: {seo_data.get('seo_recommendations', '')}"
            
            # Add service-specific details
            service_description = service_data.get('description', '')
            service_keywords = service_data.get('keywords', [])
            if service_description:
                prompt += f"\n\nService description: {service_description}"
            if service_keywords:
                prompt += f"\n\nService keywords: {', '.join(service_keywords)}"
            
            content = Content(
                role='user',
                parts=[Part(text=prompt)]
            )
            
            # Generate a unique session ID for this task
            session_id = f"content_{task_id}"
            user_id = "website_expander"
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "location": {
                    "city": city,
                    "state": state
                },
                "template_id": template["template_id"]
            }
            
            # Process the task using the Content Generator Agent
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
                            content_data = json.loads(json_match.group(1))
                            result["content"] = content_data
                        else:
                            # Process unstructured text response
                            self.logger.warning("Content not returned in structured JSON format")
                            result["content"] = {
                                "raw_response": response_text
                            }
                    except Exception as e:
                        self.logger.error(f"Failed to parse content results: {str(e)}")
                        result["content"] = {
                            "raw_response": response_text
                        }
            
            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, "completed", elapsed)
            
            # Save the generated content
            output_dir = f"data/pages/{service_id}"
            os.makedirs(output_dir, exist_ok=True)
            with open(f"{output_dir}/{zip_code}.json", 'w') as f:
                json.dump(result, f, indent=2)
            
            return result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            self.logger.error(f"Error generating content for task {task_id}: {str(e)}")
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "status": "error",
                "error": str(e)
            }
            
            self.log_task_completion(task_id, "error", elapsed, result)
            return result
