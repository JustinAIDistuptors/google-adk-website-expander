#!/usr/bin/env python3
"""
Test script for the SEO Research Agent.

This script tests the functionality of the SEO Research Agent by processing
a sample task and verifying the results.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the SEO Research Agent
from ai_agents.seo_research.seo_research_agent import SeoResearchAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_seo_research_agent():
    """
    Test the SEO Research Agent with a sample task.
    """
    logger.info("Initializing SEO Research Agent test")
    
    # Initialize the agent
    agent = SeoResearchAgent()
    agent.initialize_agent()
    
    # Create a sample task
    sample_task = {
        "task_id": "plumber_33442",
        "service_id": "plumber",
        "zip": "33442"
    }
    
    logger.info(f"Testing SEO Research Agent with task: {sample_task['task_id']}")
    
    # Process the task
    result = await agent.process_task(sample_task)
    
    # Verify the result
    if result:
        logger.info("Test completed successfully")
        
        # Save the result to a file for examination
        output_dir = "tests/output"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = f"{output_dir}/seo_research_test_result.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Test result saved to {output_path}")
        
        # Print a summary of the result
        print("\nSEO Research Test Summary:")
        print(f"Service: {result.get('service_id')}")
        print(f"Location: {result.get('location', {}).get('city')}, {result.get('location', {}).get('state')}")
        
        # Check if we have strategy data
        if "seo_strategy" in result:
            strategy = result["seo_strategy"]
            print("\nSEO Strategy Components:")
            for key in strategy.keys():
                print(f"- {key}")
            
            # Show some example keywords
            if "keywords" in strategy and "primary_keywords" in strategy["keywords"]:
                print("\nSample Primary Keywords:")
                for keyword in strategy["keywords"]["primary_keywords"][:3]:
                    print(f"- {keyword}")
        
        return True
    else:
        logger.error("Test failed: No result returned")
        return False

def run_test():
    """
    Run the async test function.
    """
    asyncio.run(test_seo_research_agent())

if __name__ == "__main__":
    run_test()
