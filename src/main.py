#!/usr/bin/env python3
"""
Main entry point for the Automated Website Expansion Framework.

This script initializes the Orchestrator Agent and starts the autonomous page generation process.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from src.services.orchestrator_service import OrchestratorService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("website_expander.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def main():
    """
    Initialize and run the website expansion process.
    """
    logger.info("Starting Website Expansion Framework")
    
    try:
        # Initialize the orchestrator service
        orchestrator = OrchestratorService()
        
        # Start the orchestration process
        await orchestrator.start_process()
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
