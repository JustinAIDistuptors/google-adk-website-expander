#!/usr/bin/env python3
"""
Queue Manager for the Website Expansion Framework.

This module provides utilities for managing the task queue, including
reading, updating, and tracking task status.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from src.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

class QueueManager:
    """
    Manages the task queue for service/location processing.
    """
    
    def __init__(self, queue_path: str = "data/queue/task_queue.json"):
        """
        Initialize the Queue Manager.
        
        Args:
            queue_path: Path to the task queue file
        """
        self.queue_path = queue_path
        self._ensure_queue_exists()
    
    def _ensure_queue_exists(self):
        """
        Ensure that the queue file exists.
        """
        queue_dir = os.path.dirname(self.queue_path)
        os.makedirs(queue_dir, exist_ok=True)
        
        if not os.path.exists(self.queue_path):
            # Create an empty queue file
            with open(self.queue_path, 'w') as f:
                json.dump([], f)
    
    def load_queue(self) -> List[Dict[str, Any]]:
        """
        Load the task queue from storage.
        
        Returns:
            list: The task queue
        """
        try:
            with open(self.queue_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load task queue: {str(e)}")
            return []
    
    def save_queue(self, queue: List[Dict[str, Any]]) -> None:
        """
        Save the task queue to storage.
        
        Args:
            queue: The task queue to save
        """
        try:
            with open(self.queue_path, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save task queue: {str(e)}")
    
    def get_pending_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a list of pending tasks up to the specified limit.
        
        Args:
            limit: Maximum number of tasks to retrieve
            
        Returns:
            list: List of pending tasks
        """
        queue = self.load_queue()
        pending_tasks = []
        
        for task in queue:
            if task['status'] == TaskStatus.PENDING and len(pending_tasks) < limit:
                pending_tasks.append(task)
        
        return pending_tasks
    
    def mark_tasks_in_progress(self, tasks: List[Dict[str, Any]]) -> None:
        """
        Mark the specified tasks as in progress.
        
        Args:
            tasks: Tasks to mark as in progress
        """
        queue = self.load_queue()
        task_ids = [task['task_id'] for task in tasks]
        
        updated = False
        for task in queue:
            if task['task_id'] in task_ids and task['status'] == TaskStatus.PENDING:
                task['status'] = TaskStatus.IN_PROGRESS
                task['updated_at'] = datetime.now().isoformat()
                updated = True
        
        if updated:
            self.save_queue(queue)
    
    def update_task_status(self, task_id: str, status: str, 
                           result: Optional[Dict[str, Any]] = None) -> None:
        """
        Update the status of a task in the queue.
        
        Args:
            task_id: Task identifier
            status: New status
            result: Optional result data
        """
        queue = self.load_queue()
        
        for task in queue:
            if task.get('task_id') == task_id:
                task['status'] = status
                task['updated_at'] = datetime.now().isoformat()
                
                # For completed or failed tasks, set completed_at
                if status in [TaskStatus.PUBLISHED, TaskStatus.FAILED, TaskStatus.ERROR]:
                    task['completed_at'] = datetime.now().isoformat()
                
                # Update with result data if provided
                if result:
                    # Add any relevant fields from result
                    if 'url' in result:
                        task['url'] = result['url']
                    if 'error' in result:
                        task['error_message'] = result['error']
                
                break
        
        self.save_queue(queue)
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by its ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            dict: Task data if found, None otherwise
        """
        queue = self.load_queue()
        
        for task in queue:
            if task.get('task_id') == task_id:
                return task
        
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the task queue.
        
        Returns:
            dict: Queue statistics
        """
        queue = self.load_queue()
        
        # Count tasks by status
        status_counts = {}
        for task in queue:
            status = task.get('status', TaskStatus.PENDING)
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        total = len(queue)
        pending = status_counts.get(TaskStatus.PENDING, 0)
        in_progress = status_counts.get(TaskStatus.IN_PROGRESS, 0)
        completed = status_counts.get(TaskStatus.PUBLISHED, 0)
        failed = status_counts.get(TaskStatus.FAILED, 0) + status_counts.get(TaskStatus.ERROR, 0)
        
        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "status_counts": status_counts
        }
