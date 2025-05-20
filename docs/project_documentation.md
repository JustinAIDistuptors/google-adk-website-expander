# Google ADK Website Expansion Framework

## Project Overview

This project implements an automated system for generating and publishing large numbers of location-based service pages (e.g., "plumber + 33442 + near me") using Google's Agent Development Kit (ADK) and Agent-to-Agent (A2A) protocol. The system follows a multi-agent architecture where specialized agents handle different aspects of the content generation and publishing pipeline.

## System Architecture

The system consists of five specialized agent components:

1. **Orchestrator Agent** - Manages the workflow and task delegation
   - Coordinates the overall process
   - Delegates tasks to specialized agents
   - Maintains the processing queue

2. **SEO Research Agent** - Gathers keywords and competitive intelligence
   - Analyzes competitors for keyword usage patterns
   - Generates primary and secondary keywords
   - Creates SEO strategy for each location+service combination

3. **Content Generation Agent** - Creates unique page content
   - Uses templates and SEO data to generate unique content
   - Ensures local relevance by incorporating location data
   - Produces structured content with proper metadata

4. **Page Assembly Agent** - Builds complete HTML pages
   - Applies HTML templates to structured content
   - Ensures proper HTML structure with schema markup
   - Validates final HTML output

5. **Publishing Agent** - Integrates with the website to deploy pages
   - Publishes pages to the target website
   - Handles URL generation according to patterns
   - Updates sitemaps and related resources

## Repository Structure

```
/
├── .github/workflows/         # CI/CD automation
│   └── ci.yml                 # GitHub Actions workflow
├── ai_agents/                 # Agent configurations and core logic
│   ├── orchestrator/          # Main coordinator agent
│   │   └── orchestrator_agent.py
│   ├── seo_research/          # SEO data gathering agent
│   │   └── seo_research_agent.py
│   ├── content_generator/     # Content creation agent
│   │   └── content_generator_agent.py
│   ├── page_assembler/        # HTML assembly agent
│   │   └── page_assembler_agent.py
│   ├── publisher/             # Publishing integration agent
│   │   └── publisher_agent.py
│   └── shared/                # Shared tools and utilities
│       └── base_agent.py      # Common base agent class
├── ai_memory/                 # Persistent memory for agents
│   ├── short_term/            # Session-specific context
│   └── long_term/             # Knowledge base and embeddings
├── data/                      # Data storage
│   ├── locations/             # Zip codes, cities, regions
│   ├── services/              # Service types definitions
│   ├── templates/             # Content templates
│   ├── pages/                 # Generated page content (JSON)
│   └── queue/                 # Task processing queue
├── docs/                      # System documentation
├── src/                       # Application code
│   ├── models/                # Data models
│   │   └── task.py            # Task data structures
│   ├── services/              # Business logic
│   │   └── orchestrator_service.py # Main service
│   ├── connectors/            # External system integrations
│   └── utils/                 # Utility functions
│       └── queue_manager.py   # Task queue management
├── scripts/                   # Utility scripts
│   ├── init_data.py           # Initialize data stores
│   └── monitoring.py          # Monitoring utilities
├── config/                    # Configuration files
│   ├── agent_config.yaml      # Agent configurations
│   ├── seo_parameters.yaml    # SEO settings
│   └── publishing_config.yaml # Publishing parameters
├── tests/                     # Test suite
├── requirements.txt           # Python dependencies
├── project_info.txt           # Project conventions
└── README.md                  # Project overview
```

## Implementation Status

### Completed Components

1. **Repository Structure** - Basic directory structure and file organization
2. **Base Agent Implementation** - Common functionality for all agents
3. **Initial Configuration Files** - YAML configurations for agents and processes
4. **Data Models** - Task and queue data structures
5. **Utility Scripts** - Data initialization and monitoring scripts
6. **Agent Implementations**:
   - Basic implementation of Orchestrator Agent
   - Basic implementation of SEO Research Agent
   - Basic implementation of Content Generator Agent
   - Basic implementation of Page Assembler Agent
   - Basic implementation of Publisher Agent
7. **Orchestrator Service** - Service for initializing and coordinating agents
8. **Queue Management** - Utilities for managing the task processing queue

### Pending Components

1. **Agent Refinements**:
   - Advanced tool implementations for agents
   - Improved prompt engineering for better content generation
   - Enhanced error handling and recovery mechanisms
2. **Integration Testing** - End-to-end workflow testing
3. **Monitoring Dashboard** - Real-time monitoring of processing status
4. **CI/CD Pipeline Enhancements** - Automated testing and deployment
5. **Production Deployment** - Cloud-based deployment configuration
6. **Documentation Expansion** - API documentation and user guides

## Technology Stack

- **Google Agent Development Kit (ADK)** - For building and coordinating AI agents
- **Gemini Models** - For content generation and analysis tasks
- **Python 3.9+** - Core programming language
- **Pydantic** - For data validation and models
- **YAML** - For configuration files
- **JSON** - For data exchange and storage
- **HTTP/REST** - For CMS integration
- **GitHub Actions** - For CI/CD automation

## Agent Implementation Details

### Base Agent

The Base Agent (`ai_agents/shared/base_agent.py`) provides common functionality for all specialized agents:

- Configuration loading from YAML files
- Standardized logging and error handling
- Agent initialization with ADK components
- Task processing utilities
- Timing and performance tracking

### Orchestrator Agent

The Orchestrator Agent (`ai_agents/orchestrator/orchestrator_agent.py`) manages the overall workflow:

- Loads and maintains the task queue
- Retrieves pending tasks for processing
- Delegates tasks to specialized agents
- Updates task status throughout the process
- Handles concurrent task processing with limits

### SEO Research Agent

The SEO Research Agent (`ai_agents/seo_research/seo_research_agent.py`) gathers SEO data:

- Analyzes competitor pages for keywords and content structure
- Generates primary, secondary, and long-tail keywords
- Provides SEO recommendations based on best practices
- Incorporates location-specific insights

### Content Generator Agent

The Content Generator Agent (`ai_agents/content_generator/content_generator_agent.py`) creates page content:

- Uses templates to guide content generation
- Incorporates SEO data from the SEO Research Agent
- Ensures content is locally relevant
- Structures content for easy assembly

### Page Assembler Agent

The Page Assembler Agent (`ai_agents/page_assembler/page_assembler_agent.py`) creates HTML pages:

- Applies HTML templates to structured content
- Adds schema.org markup for local businesses
- Ensures SEO elements are properly included
- Validates HTML structure

### Publisher Agent

The Publisher Agent (`ai_agents/publisher/publisher_agent.py`) handles deployment:

- Publishes pages to the target website's CMS
- Follows specified URL patterns
- Updates the sitemap with new pages
- Verifies successful publishing

## Core Services

### Orchestrator Service

The Orchestrator Service (`src/services/orchestrator_service.py`) initializes and coordinates all agents:

- Creates and configures all specialized agents
- Establishes the agent hierarchy
- Starts the continuous processing loop
- Handles high-level error management

### Queue Management

The Queue Manager (`src/utils/queue_manager.py`) handles the task processing queue:

- Loads and saves the task queue
- Retrieves pending tasks
- Updates task status
- Provides queue statistics

## Data Management

### Task Queue

The system maintains a task queue in `data/queue/task_queue.json` with entries for each service/location combination to process. Each task includes:

- Unique task ID (typically `{service_id}_{zip_code}`)
- Service identifier
- Location data (zip code, city, state)
- Processing status
- Timestamps for tracking
- URLs and metadata after publishing

### Content Storage

The system stores generated content and pages in structured directories:

- SEO data: `data/seo_research/{task_id}.json`
- Generated content: `data/pages/{service_id}/{zip_code}.json`
- Assembled HTML: `data/assembled_pages/{service_id}/{zip_code}.html`
- Published pages: `data/published_pages/{service_id}/{zip_code}.html`

## Configuration

The system uses YAML configuration files in the `config` directory:

- **agent_config.yaml** - Agent settings, model selection, timeouts
- **seo_parameters.yaml** - SEO targets, content structure guidelines
- **publishing_config.yaml** - Website integration, URL structure, publishing process

## Next Implementation Steps

1. **Complete Tool Implementations**:
   - Implement real SEO research tools with API integrations
   - Create CMS integration for publishing

2. **Enhance Agent Intelligence**:
   - Refine prompts for better content generation
   - Implement quality checks and feedback loops

3. **Develop Monitoring and Reporting**:
   - Create dashboards for tracking progress
   - Implement automated quality reporting

4. **Set Up Production Deployment**:
   - Configure cloud infrastructure
   - Set up proper security and authentication

5. **Testing and Refinement**:
   - Conduct end-to-end testing
   - Optimize for performance and resource usage

## Getting Started

### Prerequisites

- Python 3.9+
- Google Cloud account with Vertex AI access
- Google ADK installed (`pip install google-adk`)
- API keys for SEO tools (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/JustinAIDistuptors/google-adk-website-expander.git
cd google-adk-website-expander

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Initial Setup

```bash
# Initialize the data stores
python scripts/init_data.py

# Start the orchestrator agent
python src/main.py
```

### Monitoring

```bash
# Check the current processing status
python scripts/monitoring.py

# Continuously monitor with refresh
python scripts/monitoring.py --refresh 30  # Refresh every 30 seconds
```