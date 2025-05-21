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

### Database Setup

This project now uses a PostgreSQL database to manage tasks, content, and other operational data, replacing the previous file-based system.

#### 1. Prerequisites

*   Ensure you have a running PostgreSQL instance. You can use a local installation, a Docker container, or a cloud service like Supabase (which provides a PostgreSQL backend).
*   The `psycopg2-binary` Python package is required (already listed in `requirements.txt`).

#### 2. Environment Variables for Database Connection

The application connects to the PostgreSQL database using environment variables. You need to set these variables in your environment (e.g., in a `.env` file at the root of the project, which is loaded by `python-dotenv`).

Create a `.env` file with the following content, replacing the placeholder values with your actual database credentials:

```env
DB_HOST=your_db_host
DB_PORT=your_db_port (typically 5432 for PostgreSQL)
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

#### 3. Database Schema Initialization

The required database schema (tables, enums, functions) is defined in the `schema.sql` file in the root of this repository.

To initialize your database:
1.  Ensure your database (e.g., `your_db_name`) has been created in your PostgreSQL instance.
2.  Connect to your PostgreSQL instance using a tool like `psql` or pgAdmin.
3.  Execute the `schema.sql` script against your database.

   Example using `psql`:
   ```bash
   psql -U your_db_user -d your_db_name -f schema.sql
   ```
   (You might be prompted for `your_db_password`).

#### 4. Data Initialization (Updated `scripts/init_data.py`)

The `scripts/init_data.py` script will be updated to populate initial data (like services, locations, templates if they are moved to the DB) into the new database structure. Instructions for running this script will be updated here once the script itself is refactored.

## Usage

```bash
# Initialize the data stores
python scripts/init_data.py

# Start the orchestrator agent
python src/main.py
```

## License

MIT
