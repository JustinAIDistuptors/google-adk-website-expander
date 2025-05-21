-- Enum type for task statuses
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'seo_research_complete',
    'content_generation_complete',
    'page_assembly_complete',
    'published',
    'failed',
    'error'
);

-- Table for managing tasks (replaces data/queue/task_queue.json)
CREATE TABLE tasks (
    task_id VARCHAR(255) PRIMARY KEY, -- e.g., {service_id}_{zip_code}
    service_id VARCHAR(100) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    status task_status DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    -- Foreign keys to link to location and service definitions if they are also in DB
    -- CONSTRAINT fk_service FOREIGN KEY (service_id) REFERENCES services(service_id),
    -- CONSTRAINT fk_location FOREIGN KEY (zip_code) REFERENCES locations(zip_code)
    published_url TEXT -- Store the final published URL
);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_service_id ON tasks(service_id);
CREATE INDEX idx_tasks_zip_code ON tasks(zip_code);

-- Table for storing location data (replaces data/locations/locations.json)
CREATE TABLE locations (
    zip_code VARCHAR(10) PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50) NOT NULL,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    status VARCHAR(50) DEFAULT 'pending', -- e.g., 'active', 'inactive'
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing service definitions (replaces data/services/services.json)
CREATE TABLE services (
    service_id VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    keywords TEXT[] -- Array of keywords
);

-- Table for storing content templates (replaces data/templates/*.json)
-- Storing as structured JSONB might be flexible enough, or could be normalized further
CREATE TABLE content_templates (
    template_id VARCHAR(100) PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL,
    template_data JSONB NOT NULL, -- Stores the full template structure
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for SEO research data (replaces data/seo_research/{task_id}.json)
CREATE TABLE seo_research_data (
    task_id VARCHAR(255) PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
    primary_keywords TEXT[],
    secondary_keywords TEXT[],
    competitor_analysis JSONB, -- Store competitor URLs, keywords, etc.
    seo_recommendations TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for generated content (replaces data/pages/{service_id}/{zip_code}.json)
CREATE TABLE generated_content (
    task_id VARCHAR(255) PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
    content_data JSONB NOT NULL, -- Store the structured content from ContentGenerator (title, meta, sections, etc.)
    word_count INTEGER,
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table for assembled HTML pages (replaces data/assembled_pages/{service_id}/{zip_code}.html and .meta.json)
CREATE TABLE assembled_pages (
    task_id VARCHAR(255) PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
    html_content TEXT NOT NULL,
    schema_markup JSONB,
    assembled_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB -- Store other metadata like url_slug
);

-- Table for basic agent run logging (optional, could be more sophisticated)
CREATE TABLE agent_logs (
    log_id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) REFERENCES tasks(task_id) ON DELETE SET NULL, -- Link to task if applicable
    agent_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(100), -- e.g., 'task_start', 'task_complete', 'error'
    message TEXT,
    details JSONB, -- For structured log details
    log_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_agent_logs_task_id ON agent_logs(task_id);
CREATE INDEX idx_agent_logs_agent_name ON agent_logs(agent_name);
CREATE INDEX idx_agent_logs_log_time ON agent_logs(log_time);

-- Basic table for agent status/heartbeat (optional)
CREATE TABLE agent_status (
    agent_name VARCHAR(100) PRIMARY KEY,
    status VARCHAR(50), -- e.g., 'running', 'idle', 'error'
    last_heartbeat TIMESTAMPTZ,
    current_task_id VARCHAR(255)
);

-- Trigger function to update 'updated_at' timestamp on row update for relevant tables
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger to tables that have an 'updated_at' column
CREATE TRIGGER set_timestamp_tasks
BEFORE UPDATE ON tasks
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TRIGGER set_timestamp_content_templates
BEFORE UPDATE ON content_templates
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

CREATE TRIGGER set_timestamp_seo_research_data
BEFORE UPDATE ON seo_research_data
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- Note: locations.last_updated is meant to be updated manually or by specific processes, not necessarily every row update.
