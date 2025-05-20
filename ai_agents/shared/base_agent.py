#!/usr/bin/env python3
"""
Base Agent class for the Website Expansion Framework.

This module provides a common base class for all ADK agents in the system,
with shared functionality for configuration, logging, and error handling.
"""

import os
import time
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Import ADK components
from google.adk.agents import Agent, LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

logger = logging.getLogger(__name__)

class BaseAgent:
    """
    Base class for all agents in the Website Expansion Framework.
    
    This class provides common functionality for configuration loading,
    standardized logging, error handling, and agent initialization.
    """
    
    def __init__(self, agent_type: str, config_path: str = "config/agent_config.yaml"):
        """
        Initialize the base agent.
        
        Args:
            agent_type: Type of agent (e.g., 'orchestrator', 'seo_research')
            config_path: Path to the agent configuration file
        """
        self.agent_type = agent_type
        self.config = self._load_config(config_path)
        self.agent_config = self.config['agents'].get(agent_type, {})
        self.global_config = self.config['global']
        
        # Set up agent-specific logger
        self.logger = logging.getLogger(f"agent.{agent_type}")
        
        # Initialize ADK components
        self.session_service = InMemorySessionService()
        self.agent = None
        self.runner = None
        
        # Task tracking
        self.current_task = None
        self.start_time = None
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            dict: Configuration dictionary
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {str(e)}")
            # Return default configuration
            return {
                'global': {
                    'project_id': 'default-project',
                    'max_retry_attempts': 3,
                    'retry_delay_seconds': 5,
                    'logging_level': 'INFO'
                },
                'models': {
                    'default': 'gemini-2.0-flash'
                },
                'agents': {
                    self.agent_type: {
                        'name': f"{self.agent_type}_agent",
                        'description': f"Default {self.agent_type} agent",
                        'model': 'gemini-2.0-flash',
                        'timeout_seconds': 180
                    }
                }
            }
    
    def _resolve_model(self, model_key: str) -> Union[str, LiteLlm]:
        """
        Resolve model configuration, which can be a direct model name or a reference
        to a model in the configuration.
        
        Args:
            model_key: Model name or reference (e.g., '${models.default}')
            
        Returns:
            Union[str, LiteLlm]: Resolved model name or LiteLlm object
        """
        if not model_key:
            # Use default model if not specified
            return self.config['models']['default']
        
        if model_key.startswith('${') and model_key.endswith('}'): 
            # Handle variable references like ${models.default}
            var_path = model_key[2:-1].split('.')
            value = self.config
            for key in var_path:
                value = value.get(key, '')
            return value if value else self.config['models']['default']
        
        # Direct model name
        return model_key
    
    def initialize_agent(self, tools: List[Any] = None, sub_agents: List[Any] = None) -> None:
        """
        Initialize the ADK agent with configuration and tools.
        
        Args:
            tools: List of tools to provide to the agent
            sub_agents: List of sub-agents for delegation
        """
        try:
            name = self.agent_config.get('name', f"{self.agent_type}_agent")
            description = self.agent_config.get('description', f"{self.agent_type.capitalize()} agent")
            model = self._resolve_model(self.agent_config.get('model'))
            instruction = self.agent_config.get('instruction', '')
            
            # Create the ADK agent
            self.agent = Agent(
                name=name,
                model=model,
                description=description,
                instruction=instruction,
                tools=tools or [],
                sub_agents=sub_agents or []
            )
            
            # Create the runner
            app_name = f"website_expander_{self.agent_type}"
            self.runner = Runner(
                agent=self.agent,
                app_name=app_name,
                session_service=self.session_service
            )
            
            self.logger.info(f"Initialized {self.agent_type} agent with model {model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {str(e)}")
            raise
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task with the agent. This method should be overridden by subclasses.
        
        Args:
            task: The task to process
            
        Returns:
            dict: Task result
        """
        raise NotImplementedError("Subclasses must implement process_task")
    
    def start_task_timer(self) -> None:
        """
        Start the task execution timer.
        """
        self.start_time = time.time()
    
    def end_task_timer(self) -> float:
        """
        End the task timer and return the elapsed time.
        
        Returns:
            float: Elapsed time in seconds
        """
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.start_time = None
            return elapsed
        return 0.0
    
    def log_task_completion(self, task_id: str, status: str, elapsed: float, 
                            result: Optional[Dict[str, Any]] = None) -> None:
        """
        Log task completion details.
        
        Args:
            task_id: Unique task identifier
            status: Task status (e.g., 'completed', 'failed')
            elapsed: Elapsed time in seconds
            result: Optional result data
        """
        self.logger.info(
            f"Task {task_id} {status} in {elapsed:.2f} seconds"
        )
        
        # Additional detailed logging could be implemented here
        # e.g., writing to a structured log file or database
