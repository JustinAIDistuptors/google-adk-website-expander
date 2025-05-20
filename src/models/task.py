#!/usr/bin/env python3
"""
Task-related data models for the Website Expansion Framework.

This module defines the data structures for tasks and their status tracking.
"""

from enum import Enum, auto
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    """
    Status values for tasks in the processing pipeline.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"
    SEO_COMPLETE = "seo_complete"
    CONTENT_COMPLETE = "content_complete"
    ASSEMBLY_COMPLETE = "assembly_complete"
    PUBLISHED = "published"
    FAILED = "failed"
    ERROR = "error"

class TaskLocation(BaseModel):
    """
    Location details for a task.
    """
    zip: str
    city: Optional[str] = None
    state: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class Task(BaseModel):
    """
    Task model representing a service/location combination to process.
    """
    task_id: str
    service_id: str
    zip: str
    city: Optional[str] = None
    state: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    url: Optional[str] = None
    
    class Config:
        use_enum_values = True

class TaskResult(BaseModel):
    """
    Result of a task processing operation.
    """
    task_id: str
    status: str
    service_id: str
    zip_code: str
    message: Optional[str] = None
    error: Optional[str] = None
    url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class TaskBatch(BaseModel):
    """
    A batch of tasks for processing.
    """
    batch_id: str
    tasks: List[Task]
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
