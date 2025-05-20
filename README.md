# Automated Website Expansion Framework

A scalable system for automating the generation and publication of location-based service pages using Google's Agent Development Kit (ADK) and Agent-to-Agent (A2A) protocol.

## Overview

This framework creates a closed-loop system that can autonomously generate and publish thousands of location-based service pages (e.g., "plumber + 33442 + near me"). The system utilizes specialized agents for each phase of the content creation and publishing process.

## Architecture

The system consists of five specialized agent components:

1. **Orchestrator Agent** - Manages the workflow and task delegation
2. **SEO Research Agent** - Gathers keywords and competitive intelligence
3. **Content Generation Agent** - Creates unique page content based on templates and SEO data
4. **Page Assembly Agent** - Builds complete HTML pages with proper structure
5. **Publishing Agent** - Integrates with your website to deploy pages

## Setup

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

## Usage

```bash
# Initialize the data stores
python scripts/init_data.py

# Start the orchestrator agent
python src/main.py
```

## License

MIT
