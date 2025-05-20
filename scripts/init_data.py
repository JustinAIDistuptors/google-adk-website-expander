#!/usr/bin/env python3
"""
Initialize data stores for the Website Expansion Framework.

This script sets up the initial data stores, imports location and service data,
and prepares the system for operation.
"""

import os
import json
import logging
import argparse
import pandas as pd
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_directory_structure():
    """
    Create the necessary directory structure for data storage.
    """
    directories = [
        "data/locations",
        "data/services",
        "data/templates",
        "data/pages",
        "data/queue",
        "ai_memory/short_term",
        "ai_memory/long_term"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")

def import_location_data(file_path=None):
    """
    Import location data from a CSV file or use a sample dataset.
    
    Args:
        file_path: Path to a CSV file with location data. If None, a sample dataset is created.
    """
    output_path = "data/locations/locations.json"
    
    if file_path and os.path.exists(file_path):
        # Import from provided CSV file
        try:
            df = pd.read_csv(file_path)
            logger.info(f"Imported {len(df)} locations from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import locations from {file_path}: {str(e)}")
            return
    else:
        # Create sample location data
        logger.info("No location file provided. Creating sample location data.")
        sample_locations = [
            {"zip": "33442", "city": "Deerfield Beach", "state": "FL", "lat": 26.3173, "lng": -80.0999},
            {"zip": "90210", "city": "Beverly Hills", "state": "CA", "lat": 34.0901, "lng": -118.4065},
            {"zip": "10001", "city": "New York", "state": "NY", "lat": 40.7501, "lng": -73.9997},
            {"zip": "60601", "city": "Chicago", "state": "IL", "lat": 41.8842, "lng": -87.6222},
            {"zip": "75201", "city": "Dallas", "state": "TX", "lat": 32.7848, "lng": -96.7975}
        ]
        
        # Convert to DataFrame for consistent processing
        df = pd.DataFrame(sample_locations)
    
    # Add processing status field
    df['status'] = 'pending'
    df['last_updated'] = None
    
    # Save to JSON
    locations = df.to_dict(orient='records')
    with open(output_path, 'w') as f:
        json.dump(locations, f, indent=2)
    
    logger.info(f"Saved {len(locations)} locations to {output_path}")

def import_service_data(file_path=None):
    """
    Import service type data from a CSV file or use a sample dataset.
    
    Args:
        file_path: Path to a CSV file with service data. If None, a sample dataset is created.
    """
    output_path = "data/services/services.json"
    
    if file_path and os.path.exists(file_path):
        # Import from provided CSV file
        try:
            df = pd.read_csv(file_path)
            logger.info(f"Imported {len(df)} services from {file_path}")
        except Exception as e:
            logger.error(f"Failed to import services from {file_path}: {str(e)}")
            return
    else:
        # Create sample service data
        logger.info("No service file provided. Creating sample service data.")
        sample_services = [
            {
                "service_id": "plumber", 
                "display_name": "Plumber", 
                "keywords": ["emergency plumber", "plumbing repair", "water heater installation"],
                "description": "Professional plumbing services for residential and commercial properties."
            },
            {
                "service_id": "electrician", 
                "display_name": "Electrician", 
                "keywords": ["residential electrician", "electrical repair", "circuit breaker replacement"],
                "description": "Licensed electricians providing reliable electrical services."
            },
            {
                "service_id": "hvac", 
                "display_name": "HVAC Contractor", 
                "keywords": ["air conditioning repair", "heating installation", "HVAC maintenance"],
                "description": "Professional heating, ventilation, and air conditioning services."
            },
            {
                "service_id": "roofer", 
                "display_name": "Roofing Contractor", 
                "keywords": ["roof repair", "roof replacement", "roof inspection"],
                "description": "Expert roofing services for all types of residential and commercial buildings."
            },
            {
                "service_id": "landscaper", 
                "display_name": "Landscaping Services", 
                "keywords": ["lawn care", "garden design", "tree trimming"],
                "description": "Professional landscaping and lawn maintenance services."
            }
        ]
        
        # Convert to DataFrame for consistent processing
        df = pd.DataFrame(sample_services)
    
    # Save to JSON
    services = df.to_dict(orient='records')
    with open(output_path, 'w') as f:
        json.dump(services, f, indent=2)
    
    logger.info(f"Saved {len(services)} services to {output_path}")

def create_content_templates():
    """
    Create sample content templates for the system.
    """
    templates_dir = "data/templates"
    
    # Page template
    page_template = {
        "template_id": "standard_service_page",
        "template_name": "Standard Service Page",
        "sections": [
            {
                "id": "header",
                "type": "header",
                "instructions": "Create a compelling H1 header that includes the service type and location name."
            },
            {
                "id": "introduction",
                "type": "paragraph",
                "instructions": "Write an introductory paragraph that explains the service and its importance in the specified location. Include the primary keyword naturally."
            },
            {
                "id": "services_offered",
                "type": "section",
                "instructions": "Create a section with H2 'Services Offered' and 3-5 paragraphs describing specific services. Include at least 2 H3 subheadings for specific service types."
            },
            {
                "id": "local_relevance",
                "type": "section",
                "instructions": "Create a section with H2 'Serving [Location]' that describes the service area, mentions neighborhoods, and explains local factors relevant to this service."
            },
            {
                "id": "benefits",
                "type": "section",
                "instructions": "Create a section with H2 'Benefits of Our [Service]' and a bulleted list of 5-7 benefits."
            },
            {
                "id": "call_to_action",
                "type": "cta",
                "instructions": "Create a compelling call to action with phone number placeholder and form submission prompt."
            },
            {
                "id": "faq",
                "type": "faq",
                "instructions": "Create a FAQ section with 3-5 questions and answers relevant to this service in this location. Structure with H2 'Frequently Asked Questions' and H3s for each question."
            }
        ],
        "meta_template": {
            "title": "{service} in {city}, {state} | Professional {service} Near {zip}",
            "description": "Looking for professional {service} in {city}? Our experienced team provides reliable {service_lower} services in {zip} and surrounding areas. Call today!"
        }
    }
    
    # Save template
    with open(f"{templates_dir}/standard_service_page.json", 'w') as f:
        json.dump(page_template, f, indent=2)
    
    logger.info(f"Created content template: standard_service_page")

def create_task_queue():
    """
    Initialize the task queue with service-location combinations.
    """
    try:
        # Load locations and services
        with open("data/locations/locations.json", 'r') as f:
            locations = json.load(f)
        
        with open("data/services/services.json", 'r') as f:
            services = json.load(f)
        
        # Create all combinations for the queue
        queue = []
        for service in services:
            for location in locations:
                task = {
                    "task_id": f"{service['service_id']}_{location['zip']}",
                    "service_id": service['service_id'],
                    "zip": location['zip'],
                    "city": location['city'],
                    "state": location['state'],
                    "status": "pending",
                    "created_at": None,
                    "updated_at": None
                }
                queue.append(task)
        
        # Save queue to JSON
        with open("data/queue/task_queue.json", 'w') as f:
            json.dump(queue, f, indent=2)
        
        logger.info(f"Created task queue with {len(queue)} tasks")
    
    except Exception as e:
        logger.error(f"Failed to create task queue: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Initialize data for Website Expansion Framework")
    parser.add_argument('--locations', help='Path to CSV file with location data')
    parser.add_argument('--services', help='Path to CSV file with service data')
    
    args = parser.parse_args()
    
    logger.info("Starting data initialization")
    
    # Create directory structure
    create_directory_structure()
    
    # Import or create location data
    import_location_data(args.locations)
    
    # Import or create service data
    import_service_data(args.services)
    
    # Create content templates
    create_content_templates()
    
    # Create task queue
    create_task_queue()
    
    logger.info("Data initialization complete")

if __name__ == "__main__":
    main()
