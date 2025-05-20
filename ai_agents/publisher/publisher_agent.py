#!/usr/bin/env python3
"""
Publisher Agent for the Website Expansion Framework.

This module provides the Publisher Agent implementation, responsible for
integrating with the website to deploy assembled pages.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# Import base agent
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ai_agents.shared.base_agent import BaseAgent

# Import ADK components
from google.adk.agents import Agent
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

class PublisherAgent(BaseAgent):
    """
    Agent responsible for publishing pages to the website.
    
    The Publisher Agent integrates with the website's CMS or publishing system
    to deploy assembled pages and update the sitemap.
    """
    
    def __init__(self, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the Publisher Agent.
        
        Args:
            config_path: Path to the agent configuration file
        """
        super().__init__("publisher", config_path)
        self.publish_batch_size = self.agent_config.get('publish_batch_size', 5)
        self.dry_run = self.agent_config.get('dry_run', False)
        
        # Load publishing config
        self.publishing_config = self._load_publishing_config()
    
    def _load_publishing_config(self) -> Dict[str, Any]:
        """
        Load publishing configuration parameters.
        
        Returns:
            dict: Publishing configuration
        """
        try:
            with open("config/publishing_config.yaml", 'r') as f:
                import yaml
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Failed to load publishing config: {str(e)}")
            # Return default configuration
            return {
                'website': {
                    'base_url': "https://example.com",
                    'api_endpoint': "https://example.com/api/content",
                    'content_management_system': "wordpress"
                },
                'url_structure': {
                    'pattern': "{service_slug}/{location_zip}"
                },
                'publishing': {
                    'batch_size': 10,
                    'verification_enabled': True
                }
            }
    
    def _create_publishing_tool(self):
        """
        Create a tool for publishing pages to the website.
        
        Returns:
            callable: Publishing tool function
        """
        def publish_page_tool(service_id: str, zip_code: str, dry_run: bool = False) -> Dict[str, Any]:
            """
            Publishes a page to the website.
            
            Args:
                service_id: The service ID
                zip_code: The zip code
                dry_run: If True, simulate publishing without actual deployment
                
            Returns:
                dict: Publishing result
            """
            # This is a mock implementation
            # In a real implementation, this would call the CMS API
            
            self.logger.info(f"Publishing page for {service_id}/{zip_code} (dry_run: {dry_run})")
            
            # Get the assembled HTML
            html_path = f"data/assembled_pages/{service_id}/{zip_code}.html"
            meta_path = f"data/assembled_pages/{service_id}/{zip_code}.meta.json"
            
            if not os.path.exists(html_path) or not os.path.exists(meta_path):
                return {
                    "status": "error",
                    "error": f"Assembled page not found for {service_id}/{zip_code}"
                }
            
            try:
                # Read HTML and metadata
                with open(html_path, 'r') as f:
                    html_content = f.read()
                
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                
                # Generate URL based on pattern
                url_pattern = self.publishing_config['url_structure']['pattern']
                service_slug = service_id.lower().replace("_", "-")
                url_slug = url_pattern.format(service_slug=service_slug, location_zip=zip_code)
                
                # Base URL from config
                base_url = self.publishing_config['website']['base_url']
                full_url = f"{base_url}/{url_slug}/"
                
                # Simulate API call to CMS
                if dry_run:
                    self.logger.info(f"DRY RUN: Would publish to {full_url}")
                    result = {
                        "status": "success",
                        "message": "Page would have been published (dry run)",
                        "url": full_url
                    }
                else:
                    # Here we would actually call the CMS API
                    # For now, we'll simulate success
                    self.logger.info(f"Publishing to {full_url}")
                    
                    # Save a copy to the 'published' directory to simulate publishing
                    published_dir = f"data/published_pages/{service_id}"
                    os.makedirs(published_dir, exist_ok=True)
                    
                    with open(f"{published_dir}/{zip_code}.html", 'w') as f:
                        f.write(html_content)
                    
                    result = {
                        "status": "success",
                        "message": "Page published successfully",
                        "url": full_url
                    }
                
                # Update metadata
                metadata["published"] = True
                metadata["published_at"] = datetime.now().isoformat()
                metadata["url"] = full_url
                
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                return result
                
            except Exception as e:
                self.logger.error(f"Error in publish_page_tool: {str(e)}")
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        return publish_page_tool
    
    def _create_sitemap_tool(self):
        """
        Create a tool for updating the sitemap.
        
        Returns:
            callable: Sitemap tool function
        """
        def update_sitemap_tool() -> Dict[str, Any]:
            """
            Updates the website sitemap with newly published pages.
            
            Returns:
                dict: Sitemap update result
            """
            # This is a mock implementation
            # In a real implementation, this would generate and upload a sitemap XML file
            
            self.logger.info("Updating sitemap")
            
            # Simulate sitemap generation
            published_pages = []
            for service_dir in os.listdir("data/published_pages"):
                service_path = os.path.join("data/published_pages", service_dir)
                if os.path.isdir(service_path):
                    for filename in os.listdir(service_path):
                        if filename.endswith(".meta.json"):
                            meta_path = os.path.join(service_path, filename)
                            try:
                                with open(meta_path, 'r') as f:
                                    metadata = json.load(f)
                                    if metadata.get("published") and metadata.get("url"):
                                        published_pages.append(metadata["url"])
                            except Exception as e:
                                self.logger.error(f"Error reading metadata {meta_path}: {str(e)}")
            
            # Write sitemap file
            sitemap_dir = "data/sitemap"
            os.makedirs(sitemap_dir, exist_ok=True)
            
            sitemap_content = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            sitemap_content += "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
            
            for url in published_pages:
                sitemap_content += f"  <url>\n    <loc>{url}</loc>\n  </url>\n"
            
            sitemap_content += "</urlset>"
            
            sitemap_path = f"{sitemap_dir}/sitemap.xml"
            with open(sitemap_path, 'w') as f:
                f.write(sitemap_content)
            
            return {
                "status": "success",
                "message": f"Sitemap updated with {len(published_pages)} pages",
                "path": sitemap_path
            }
        
        return update_sitemap_tool
    
    def initialize_agent(self):
        """
        Initialize the Publisher Agent with necessary tools.
        """
        # Create publishing tools
        tools = [
            self._create_publishing_tool(),
            self._create_sitemap_tool()
        ]
        
        # Additional agent-specific instruction
        instruction = self.agent_config.get('instruction', '')
        instruction += """
        Your task is to publish assembled pages to the website and manage the sitemap.
        For each task:
        1. Verify that the page has been properly assembled
        2. Publish the page to the appropriate URL based on the URL pattern
        3. Verify that the page was published successfully
        4. Update the sitemap to include the new page
        5. Report the publishing status and URL
        
        If the dry_run flag is set, simulate the publishing process without actually
        deploying to the website.
        """
        
        self.agent_config['instruction'] = instruction
        
        # Initialize the agent with the tools
        super().initialize_agent(tools=tools)
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single publishing task.
        
        Args:
            task: The task to process, including service and location
            
        Returns:
            dict: Publishing result
        """
        task_id = task.get('task_id')
        service_id = task.get('service_id')
        zip_code = task.get('zip')
        
        self.logger.info(f"Publishing page for task {task_id}: {service_id} + {zip_code}")
        self.start_task_timer()
        
        try:
            # Check if page has been assembled
            html_path = f"data/assembled_pages/{service_id}/{zip_code}.html"
            if not os.path.exists(html_path):
                raise FileNotFoundError(f"Assembled page not found at {html_path}")
            
            # Prepare the message for the agent
            prompt = f"Publish the page for {service_id} services in zip code {zip_code}. "
            if self.dry_run:
                prompt += "This is a DRY RUN, so simulate the publishing process without actual deployment. "
            prompt += "After publishing, update the sitemap to include the new page."
            
            content = Content(
                role='user',
                parts=[Part(text=prompt)]
            )
            
            # Generate a unique session ID for this task
            session_id = f"publish_{task_id}"
            user_id = "website_expander"
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "status": "processing",
                "dry_run": self.dry_run
            }
            
            # Process the task using the Publisher Agent
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content
            ):
                # Check for the final response
                if event.is_final_response() and event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                    
                    # Extract publishing details from the response
                    if "successfully" in response_text.lower():
                        result["status"] = "published"
                    else:
                        result["status"] = "failed"
                    
                    result["message"] = response_text
                    
                    # Try to extract URL from response
                    import re
                    url_match = re.search(r'(https?://[^\s]+)', response_text)
                    if url_match:
                        result["url"] = url_match.group(1)
            
            elapsed = self.end_task_timer()
            self.log_task_completion(task_id, result["status"], elapsed, result)
            
            return result
            
        except Exception as e:
            elapsed = self.end_task_timer()
            self.logger.error(f"Error publishing page for task {task_id}: {str(e)}")
            
            result = {
                "service_id": service_id,
                "zip_code": zip_code,
                "status": "error",
                "error": str(e)
            }
            
            self.log_task_completion(task_id, "error", elapsed, result)
            return result
