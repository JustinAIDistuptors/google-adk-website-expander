#!/usr/bin/env python3
"""
Monitoring script for the Website Expansion Framework.

This script provides monitoring capabilities for the ongoing page generation process,
including progress tracking, error reporting, and performance metrics.
"""

import os
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def load_task_queue():
    """
    Load the current task queue from storage.
    
    Returns:
        list: The task queue data.
    """
    try:
        with open("data/queue/task_queue.json", 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load task queue: {str(e)}")
        return []

def get_task_status_summary(tasks):
    """
    Generate a summary of task statuses.
    
    Args:
        tasks: List of tasks from the queue.
        
    Returns:
        dict: Summary of status counts.
    """
    status_counts = Counter(task['status'] for task in tasks)
    total = len(tasks)
    
    summary = {
        'total': total,
        'counts': dict(status_counts),
        'percentages': {}
    }
    
    # Calculate percentages
    for status, count in status_counts.items():
        summary['percentages'][status] = round((count / total) * 100, 2) if total > 0 else 0
    
    return summary

def get_recent_errors(tasks, hours=24):
    """
    Identify tasks with errors in the recent time period.
    
    Args:
        tasks: List of tasks from the queue.
        hours: Number of hours to look back.
        
    Returns:
        list: Tasks with errors in the specified timeframe.
    """
    recent_errors = []
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    for task in tasks:
        if task['status'] == 'error' and task.get('updated_at'):
            try:
                updated_time = datetime.fromisoformat(task['updated_at'])
                if updated_time > cutoff_time:
                    recent_errors.append(task)
            except (ValueError, TypeError):
                # Skip tasks with invalid timestamps
                pass
    
    return recent_errors

def get_completion_rate(tasks, hours=1):
    """
    Calculate the completion rate (tasks completed per hour).
    
    Args:
        tasks: List of tasks from the queue.
        hours: Number of hours to calculate rate for.
        
    Returns:
        float: Tasks completed per hour.
    """
    completed_recently = 0
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    for task in tasks:
        if task['status'] == 'completed' and task.get('updated_at'):
            try:
                updated_time = datetime.fromisoformat(task['updated_at'])
                if updated_time > cutoff_time:
                    completed_recently += 1
            except (ValueError, TypeError):
                # Skip tasks with invalid timestamps
                pass
    
    return completed_recently / hours if hours > 0 else 0

def get_service_status_breakdown(tasks):
    """
    Break down task status by service type.
    
    Args:
        tasks: List of tasks from the queue.
        
    Returns:
        dict: Status breakdown by service.
    """
    service_breakdown = {}
    
    for task in tasks:
        service_id = task.get('service_id')
        status = task.get('status')
        
        if service_id and status:
            if service_id not in service_breakdown:
                service_breakdown[service_id] = Counter()
            
            service_breakdown[service_id][status] += 1
    
    return service_breakdown

def display_summary(tasks):
    """
    Display a summary of the current processing status.
    
    Args:
        tasks: List of tasks from the queue.
    """
    status_summary = get_task_status_summary(tasks)
    recent_errors = get_recent_errors(tasks)
    completion_rate = get_completion_rate(tasks)
    service_breakdown = get_service_status_breakdown(tasks)
    
    print("\n=== Website Expansion Framework - Status Summary ===\n")
    
    # Overall progress
    print(f"Total Tasks: {status_summary['total']}")
    for status, count in status_summary['counts'].items():
        percentage = status_summary['percentages'][status]
        print(f"  {status.upper()}: {count} ({percentage}%)")
    
    # Completion rate
    print(f"\nCompletion Rate: {completion_rate:.2f} pages per hour")
    
    # Recent errors
    print(f"\nRecent Errors (24h): {len(recent_errors)}")
    if recent_errors and len(recent_errors) > 0:
        print("  Most recent errors:")
        for task in recent_errors[:5]:  # Show only the 5 most recent errors
            print(f"    {task['service_id']} - {task['zip']} - {task.get('updated_at', 'unknown time')}")
    
    # Service breakdown (top 3 services)
    print("\nService Status Breakdown (Top 3):")
    top_services = sorted(service_breakdown.items(), 
                        key=lambda x: sum(x[1].values()), 
                        reverse=True)[:3]
    
    for service_id, status_counts in top_services:
        total = sum(status_counts.values())
        completed = status_counts.get('completed', 0)
        percentage = (completed / total) * 100 if total > 0 else 0
        
        print(f"  {service_id}: {completed}/{total} completed ({percentage:.2f}%)")
    
    print("\n=== End of Status Summary ===\n")

def main():
    parser = argparse.ArgumentParser(description="Monitor the Website Expansion Framework")
    parser.add_argument('--refresh', type=int, default=0, 
                        help='Refresh interval in seconds (0 for one-time display)')
    
    args = parser.parse_args()
    
    try:
        if args.refresh > 0:
            # Continuous monitoring mode
            while True:
                tasks = load_task_queue()
                os.system('cls' if os.name == 'nt' else 'clear')  # Clear screen
                display_summary(tasks)
                print(f"Refreshing in {args.refresh} seconds... (Press Ctrl+C to exit)")
                time.sleep(args.refresh)
        else:
            # One-time display
            tasks = load_task_queue()
            display_summary(tasks)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except Exception as e:
        logger.error(f"Error in monitoring: {str(e)}")

if __name__ == "__main__":
    main()
