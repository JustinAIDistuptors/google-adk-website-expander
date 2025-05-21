#!/usr/bin/env python3
"""
Initialize data stores for the Website Expansion Framework.

This script sets up the initial data in the PostgreSQL database,
including schema initialization, location and service data import,
content template creation, and task queue generation.
"""

import os
import json
import logging
import argparse
import pandas as pd
from datetime import datetime # For timestamps in DB

import psycopg2
from psycopg2 import extras # For execute_values

# Add project root to sys.path to allow direct import of src modules
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.queue_manager import get_db_connection # Assuming this is the way to get DB conn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_schema(conn):
    """
    Initializes the database schema by executing commands from schema.sql.
    Args:
        conn: Active psycopg2 database connection.
    """
    schema_file_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
    if not os.path.exists(schema_file_path):
        logger.error(f"Schema file not found at {schema_file_path}. Cannot initialize schema.")
        return False
    
    logger.info(f"Initializing database schema from {schema_file_path}...")
    try:
        with open(schema_file_path, 'r') as f:
            sql_commands = f.read()
        
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        conn.commit()
        logger.info("Database schema initialized successfully.")
        return True
    except psycopg2.Error as e:
        logger.error(f"Error initializing database schema: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during schema initialization: {e}")
        conn.rollback()
        return False

def import_location_data(conn, file_path=None):
    """
    Import location data into the 'locations' table.
    Args:
        conn: Active psycopg2 database connection.
        file_path: Path to a CSV file with location data. If None, sample data is used.
    """
    locations_data = []
    if file_path and os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            # Ensure required columns exist, handle missing optional ones
            df['latitude'] = df.get('latitude', None)
            df['longitude'] = df.get('longitude', None)
            df['status'] = df.get('status', 'active') # Default to active
            locations_data = [
                (row['zip_code'], row['city'], row['state'], row.get('latitude'), row.get('longitude'), row.get('status', 'active'))
                for index, row in df.iterrows()
            ]
            logger.info(f"Loaded {len(locations_data)} locations from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import locations from {file_path}: {e}. Using sample data.")
            locations_data = [] # Fallback to sample
    
    if not locations_data:
        logger.info("Using sample location data.")
        sample_locations = [
            # zip_code, city, state, latitude, longitude, status
            ('33442', 'Deerfield Beach', 'FL', 26.3173, -80.0999, 'active'),
            ('90210', 'Beverly Hills', 'CA', 34.0901, -118.4065, 'active'),
            ('10001', 'New York', 'NY', 40.7501, -73.9997, 'active'),
            ('60601', 'Chicago', 'IL', 41.8842, -87.6222, 'active'),
            ('75201', 'Dallas', 'TX', 32.7848, -96.7975, 'active')
        ]
        locations_data = sample_locations

    sql = """
        INSERT INTO locations (zip_code, city, state, latitude, longitude, status, last_updated)
        VALUES %s
        ON CONFLICT (zip_code) DO UPDATE SET
            city = EXCLUDED.city,
            state = EXCLUDED.state,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            status = EXCLUDED.status,
            last_updated = CURRENT_TIMESTAMP;
    """
    try:
        with conn.cursor() as cur:
            # Add last_updated timestamp to each tuple for VALUES %s
            data_with_timestamp = [loc + (datetime.now(),) for loc in locations_data]
            # Reconstruct SQL for execute_values to match number of VALUES placeholders
            insert_sql = """
                INSERT INTO locations (zip_code, city, state, latitude, longitude, status, last_updated)
                VALUES %s
                ON CONFLICT (zip_code) DO UPDATE SET
                    city = EXCLUDED.city, state = EXCLUDED.state, latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude, status = EXCLUDED.status, last_updated = EXCLUDED.last_updated;
            """
            # extras.execute_values expects a list of tuples, where each tuple matches the columns.
            # The VALUES %s in the original sql needs to be singular for execute_values.
            # We are inserting (zip_code, city, state, lat, long, status, last_updated_ts)
            # Example tuple for execute_values: ('33442', 'City', 'ST', lat, lng, 'active', now_ts)

            # Correcting the data format for execute_values
            values_to_insert = [
                (loc[0], loc[1], loc[2], loc[3], loc[4], loc[5], datetime.now()) for loc in locations_data
            ]

            extras.execute_values(cur, insert_sql, values_to_insert, template=None, page_size=100)
        conn.commit()
        logger.info(f"Imported/updated {len(locations_data)} locations into the database.")
    except psycopg2.Error as e:
        logger.error(f"Error importing location data to DB: {e}")
        conn.rollback()
    except Exception as e:
        logger.error(f"An unexpected error occurred during location data import: {e}")
        conn.rollback()


def import_service_data(conn, file_path=None):
    """
    Import service data into the 'services' table.
    Args:
        conn: Active psycopg2 database connection.
        file_path: Path to a CSV file with service data. If None, sample data is used.
    """
    services_data = []
    if file_path and os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            # Ensure keywords are lists (e.g., if CSV stores them as comma-separated strings)
            if 'keywords' in df.columns and isinstance(df['keywords'].iloc[0], str):
                df['keywords'] = df['keywords'].apply(lambda x: [k.strip() for k in x.split(',')])
            else: # Ensure it's a list even if empty or non-string
                 df['keywords'] = df.apply(lambda row: row.get('keywords', []) if isinstance(row.get('keywords', []), list) else [], axis=1)

            services_data = [
                (row['service_id'], row['display_name'], row.get('description', ''), row.get('keywords', []))
                for index, row in df.iterrows()
            ]
            logger.info(f"Loaded {len(services_data)} services from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import services from {file_path}: {e}. Using sample data.")
            services_data = [] # Fallback

    if not services_data:
        logger.info("Using sample service data.")
        sample_services = [
            ("plumber", "Plumber", "Professional plumbing services.", ["emergency plumber", "plumbing repair"]),
            ("electrician", "Electrician", "Licensed electrical services.", ["residential electrician", "electrical repair"]),
            ("hvac", "HVAC Contractor", "Heating, ventilation, and AC.", ["air conditioning repair", "heating installation"]),
            ("roofer", "Roofing Contractor", "Expert roofing services.", ["roof repair", "roof replacement"]),
            ("landscaper", "Landscaping Services", "Lawn care and garden design.", ["lawn care", "garden design"])
        ]
        services_data = sample_services
    
    sql = """
        INSERT INTO services (service_id, display_name, description, keywords)
        VALUES %s
        ON CONFLICT (service_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            keywords = EXCLUDED.keywords;
    """
    try:
        with conn.cursor() as cur:
            extras.execute_values(cur, sql, services_data, template=None, page_size=100)
        conn.commit()
        logger.info(f"Imported/updated {len(services_data)} services into the database.")
    except psycopg2.Error as e:
        logger.error(f"Error importing service data to DB: {e}")
        conn.rollback()
    except Exception as e:
        logger.error(f"An unexpected error occurred during service data import: {e}")
        conn.rollback()

def create_content_templates(conn):
    """
    Create sample content templates in the 'content_templates' table.
    Args:
        conn: Active psycopg2 database connection.
    """
    page_template_dict = {
        "template_id": "standard_service_page",
        "template_name": "Standard Service Page",
        "sections": [
            {"id": "header", "type": "header", "instructions": "Compelling H1: {service} in {city}, {state}"},
            {"id": "introduction", "type": "paragraph", "instructions": "Intro about {service} in {city}."},
            {"id": "services_offered", "type": "section", "instructions": "H2: Services Offered. Describe specific services."},
            {"id": "local_relevance", "type": "section", "instructions": "H2: Serving {city}. Mention local factors."},
            {"id": "benefits", "type": "section", "instructions": "H2: Benefits of Our {service}. Bulleted list."},
            {"id": "call_to_action", "type": "cta", "instructions": "Compelling CTA."},
            {"id": "faq", "type": "faq", "instructions": "H2: FAQs. 3-5 Q&As."}
        ],
        "meta_template": {
            "title": "{service} in {city}, {state} | Professional {service} Near {zip}",
            "description": "Looking for professional {service} in {city}? Call today!"
        },
        # Example for PageAssembler if it expects HTML template string here
        "html_body_template": """
<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>{meta_title}</title><meta name="description" content="{meta_description}">{schema_markup_script_tag}</head>
<body><header><h1>{header_content}</h1></header><main>{introduction_content}{services_offered_content}{local_relevance_content}{benefits_content}{faq_content}</main><footer>{call_to_action_content}</footer>
</body></html>
        """
    }
    
    templates_to_insert = [
        (page_template_dict["template_id"], page_template_dict["template_name"], json.dumps(page_template_dict))
    ]

    sql = """
        INSERT INTO content_templates (template_id, template_name, template_data, created_at, updated_at)
        VALUES %s
        ON CONFLICT (template_id) DO UPDATE SET
            template_name = EXCLUDED.template_name,
            template_data = EXCLUDED.template_data,
            updated_at = CURRENT_TIMESTAMP;
    """
    try:
        with conn.cursor() as cur:
            # Add created_at, updated_at for VALUES %s
            current_time = datetime.now()
            data_with_timestamps = [
                (tpl[0], tpl[1], tpl[2], current_time, current_time) for tpl in templates_to_insert
            ]
            extras.execute_values(cur, sql, data_with_timestamps, template=None, page_size=100)
        conn.commit()
        logger.info(f"Created/updated {len(templates_to_insert)} content templates in the database.")
    except psycopg2.Error as e:
        logger.error(f"Error creating content templates in DB: {e}")
        conn.rollback()
    except Exception as e:
        logger.error(f"An unexpected error occurred during content template creation: {e}")
        conn.rollback()

def create_task_queue(conn):
    """
    Initialize the task queue in the 'tasks' table.
    Args:
        conn: Active psycopg2 database connection.
    """
    logger.info("Creating task queue...")
    try:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur: # Use DictCursor for easy column access
            cur.execute("SELECT zip_code, city, state FROM locations WHERE status = 'active';")
            locations = cur.fetchall()
            
            cur.execute("SELECT service_id FROM services;")
            services = cur.fetchall()

        if not locations or not services:
            logger.warning("No active locations or services found in DB. Task queue will be empty.")
            return

        tasks_to_insert = []
        for service_row in services:
            service_id = service_row['service_id']
            for location_row in locations:
                zip_code = location_row['zip_code']
                task_id = f"{service_id}_{zip_code}"
                tasks_to_insert.append((
                    task_id, service_id, zip_code, 
                    location_row['city'], location_row['state'], 'pending' # Default status
                ))
        
        if not tasks_to_insert:
            logger.info("No tasks generated (perhaps no active locations/services).")
            return

        sql = """
            INSERT INTO tasks (task_id, service_id, zip_code, city, state, status)
            VALUES %s
            ON CONFLICT (task_id) DO NOTHING; 
        """ # created_at, updated_at have defaults
        
        with conn.cursor() as cur:
            extras.execute_values(cur, sql, tasks_to_insert, template=None, page_size=500)
        conn.commit()
        logger.info(f"Created/updated task queue with {len(tasks_to_insert)} potential tasks in the database.")
        # A follow-up query could count how many were actually inserted if needed.
        
    except psycopg2.Error as e:
        logger.error(f"Error creating task queue in DB: {e}")
        conn.rollback()
    except Exception as e:
        logger.error(f"An unexpected error occurred during task queue creation: {e}")
        conn.rollback()

def create_remaining_directories():
    """
    Create other necessary directories not directly tied to DB data.
    (e.g., for AI memory, sitemaps, logs if stored as files)
    """
    directories = [
        "ai_memory/short_term",
        "ai_memory/long_term",
        "data/sitemap", # Publisher agent still writes sitemap.xml here
        # "data/assembled_pages", # No longer needed if not debugging locally
        # "data/published_pages", # No longer needed
        # "data/seo_research", # No longer needed
        # "data/pages", # (generated content) No longer needed
    ]
    for directory in directories:
        if not os.path.exists(directory): # Use os.path.exists for simplicity
            os.makedirs(directory, exist_ok=True) # Use os.makedirs
            logger.info(f"Ensured directory exists: {directory}")


def main():
    parser = argparse.ArgumentParser(description="Initialize data for Website Expansion Framework (PostgreSQL)")
    parser.add_argument('--locations_csv', help='Path to CSV file with location data')
    parser.add_argument('--services_csv', help='Path to CSV file with service data')
    parser.add_argument('--init-schema', action='store_true', help='Initialize DB schema from schema.sql')
    
    args = parser.parse_args()
    
    logger.info("Starting data initialization for PostgreSQL...")
    
    db_conn = get_db_connection()
    if not db_conn:
        logger.error("Failed to connect to the database. Halting initialization.")
        return

    try:
        if args.init_schema:
            if not initialize_schema(db_conn):
                logger.error("Schema initialization failed. Halting further data operations.")
                return # Stop if schema init fails
        
        import_location_data(db_conn, args.locations_csv)
        import_service_data(db_conn, args.services_csv)
        create_content_templates(db_conn) # Uses hardcoded sample data
        create_task_queue(db_conn)         # Generates tasks from DB locations/services
        
        create_remaining_directories() # Create other necessary filesystem directories

        logger.info("Data initialization process complete.")
        
    except Exception as e:
        logger.error(f"An error occurred during the main initialization process: {e}", exc_info=True)
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    main()
```
