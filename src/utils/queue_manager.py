#!/usr/bin/env python3
"""
QueueManager for interacting with a PostgreSQL database.

This module replaces the previous JSON file-based queue management with
a PostgreSQL backend, using psycopg2 for database interactions.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

import psycopg2
from psycopg2 import extras # For dict cursor
from psycopg2.extensions import connection

from src.models.task import Task, TaskStatus as PythonTaskStatus

# Configure logging
logger = logging.getLogger(__name__)

# Mapping from Python TaskStatus enum values to DB enum values
# Only include those that differ or are problematic.
PYTHON_TO_DB_STATUS_MAP = {
    PythonTaskStatus.SEO_COMPLETE.value: "seo_research_complete",
    PythonTaskStatus.CONTENT_COMPLETE.value: "content_generation_complete",
    PythonTaskStatus.ASSEMBLY_COMPLETE.value: "page_assembly_complete",
    # PythonTaskStatus.PROCESSING.value is not in DB enum.
    # If an attempt is made to save "processing", it will be an error or needs specific handling.
}

# Mapping from DB enum values to Python TaskStatus enum values
DB_TO_PYTHON_STATUS_MAP = {v: k for k, v in PYTHON_TO_DB_STATUS_MAP.items()}

def get_db_connection() -> Optional[connection]:
    """
    Establishes a connection to the PostgreSQL database using environment variables.

    Returns:
        psycopg2.extensions.connection: A connection object or None if connection fails.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "website_expansion_dev"),
            user=os.getenv("DB_USER", "devuser"),
            password=os.getenv("DB_PASSWORD", "devpass")
        )
        logger.info("Successfully connected to the PostgreSQL database.")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to PostgreSQL database: {e}")
        return None

class QueueManager:
    """
    Manages tasks stored in a PostgreSQL database.
    """

    def __init__(self):
        """
        Initializes the QueueManager.
        A connection test is performed, but connections are typically short-lived per method.
        """
        # Test connection on init, but each method will get its own connection
        # for better resilience and to avoid stale connections.
        conn = get_db_connection()
        if conn:
            conn.close()
        else:
            # This is not a fatal error for the constructor itself,
            # as methods will try to connect again. But it's a warning.
            logger.warning("QueueManager initialized but failed to connect to DB. Methods will attempt to reconnect.")


    def _map_row_to_task(self, row: Dict[str, Any]) -> Task:
        """
        Maps a database row (as a dict) to a Task Pydantic model.
        Handles status string conversion from DB to Python enum.
        """
        db_status = row.get('status')
        python_status_str = DB_TO_PYTHON_STATUS_MAP.get(db_status, db_status) # Fallback to db_status if not in map

        # Ensure the status string is a valid PythonTaskStatus member
        try:
            python_status_enum = PythonTaskStatus(python_status_str)
        except ValueError:
            logger.warning(f"DB status '{db_status}' (mapped to '{python_status_str}') is not a valid PythonTaskStatus. Defaulting to ERROR.")
            python_status_enum = PythonTaskStatus.ERROR
        
        return Task(
            task_id=row.get('task_id'),
            service_id=row.get('service_id'),
            zip=row.get('zip_code'), # DB uses zip_code
            city=row.get('city'),
            state=row.get('state'),
            status=python_status_enum,
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            error_message=row.get('error_message'),
            url=row.get('published_url') # DB uses published_url
        )

    def add_task(self, task_data: Dict[str, Any]) -> Optional[Task]:
        """
        Adds a new task to the database.
        Expects task_data to be a dictionary compatible with Task model fields.
        This method is an example of how new tasks could be added.
        The original QueueManager did not have an explicit add_task.
        """
        conn = get_db_connection()
        if not conn:
            return None

        # Convert Python status to DB status if provided
        python_status_value = task_data.get('status', PythonTaskStatus.PENDING.value)
        if isinstance(python_status_value, PythonTaskStatus):
            python_status_value = python_status_value.value
        
        db_status = PYTHON_TO_DB_STATUS_MAP.get(python_status_value, python_status_value)
        if python_status_value == PythonTaskStatus.PROCESSING.value:
            logger.warning(f"Attempting to save task with 'processing' status. This status is not in DB enum. Saving as 'in_progress'.")
            db_status = PythonTaskStatus.IN_PROGRESS.value


        sql = """
            INSERT INTO tasks (task_id, service_id, zip_code, city, state, status, error_message, published_url, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *;
        """
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                current_time = datetime.now()
                cur.execute(sql, (
                    task_data['task_id'],
                    task_data['service_id'],
                    task_data['zip_code'], # Expects zip_code for DB
                    task_data.get('city'),
                    task_data.get('state'),
                    db_status,
                    task_data.get('error_message'),
                    task_data.get('published_url'), # Expects published_url for DB
                    task_data.get('created_at', current_time),
                    task_data.get('updated_at', current_time)
                ))
                inserted_row = cur.fetchone()
                conn.commit()
                if inserted_row:
                    logger.info(f"Task {inserted_row['task_id']} added to the database.")
                    return self._map_row_to_task(inserted_row)
                return None
        except psycopg2.Error as e:
            logger.error(f"Error adding task {task_data.get('task_id')} to database: {e}")
            conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    def get_tasks_by_status(self, status: PythonTaskStatus, limit: Optional[int] = None) -> List[Task]:
        """
        Retrieves tasks from the database by their status.
        Replaces the concept of 'load_queue' for a specific status.
        """
        conn = get_db_connection()
        if not conn:
            return []

        python_status_value = status.value
        db_status = PYTHON_TO_DB_STATUS_MAP.get(python_status_value, python_status_value)
        if python_status_value == PythonTaskStatus.PROCESSING.value:
             # Cannot query for 'processing' as it's not in DB.
             # This case should be handled by the caller or mapped to a valid DB status.
             # For now, returning empty list if 'processing' is requested.
            logger.warning("Querying for 'processing' status, which is not in DB enum. Returning empty list.")
            return []

        sql = "SELECT * FROM tasks WHERE status = %s"
        if limit:
            sql += f" LIMIT {limit}"
        
        tasks: List[Task] = []
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                cur.execute(sql, (db_status,))
                rows = cur.fetchall()
                for row in rows:
                    tasks.append(self._map_row_to_task(row))
            logger.info(f"Retrieved {len(tasks)} tasks with status '{db_status}'.")
        except psycopg2.Error as e:
            logger.error(f"Error retrieving tasks by status '{db_status}': {e}")
        finally:
            if conn:
                conn.close()
        return tasks

    def get_pending_tasks(self, limit: Optional[int] = None) -> List[Task]:
        """
        Retrieves all tasks with 'pending' status.
        """
        return self.get_tasks_by_status(PythonTaskStatus.PENDING, limit=limit)

    def mark_tasks_in_progress(self, tasks: List[Task]) -> List[Task]:
        """
        Updates the status of a list of tasks to 'in_progress'.
        """
        if not tasks:
            return []

        task_ids = [task.task_id for task in tasks]
        conn = get_db_connection()
        if not conn:
            return [] # Or raise exception

        # 'in_progress' is the same in PythonTaskStatus.value and DB enum
        db_status_in_progress = PythonTaskStatus.IN_PROGRESS.value 
        
        sql = """
            UPDATE tasks
            SET status = %s, updated_at = %s
            WHERE task_id = ANY(%s::varchar[]) AND status = %s
            RETURNING *;
        """
        updated_tasks: List[Task] = []
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                # We only mark pending tasks as in_progress
                cur.execute(sql, (db_status_in_progress, datetime.now(), task_ids, PythonTaskStatus.PENDING.value))
                rows = cur.fetchall()
                conn.commit()
                for row in rows:
                    updated_tasks.append(self._map_row_to_task(row))
            logger.info(f"Marked {len(updated_tasks)} tasks as '{db_status_in_progress}'.")
        except psycopg2.Error as e:
            logger.error(f"Error marking tasks in progress: {e}")
            conn.rollback()
        finally:
            if conn:
                conn.close()
        return updated_tasks

    def update_task_status(self, task_id: str, status: PythonTaskStatus, error_message: Optional[str] = None, url: Optional[str] = None) -> Optional[Task]:
        """
        Updates the status of a single task.
        Can also update error_message and published_url (url).
        """
        conn = get_db_connection()
        if not conn:
            return None

        python_status_value = status.value
        db_status = PYTHON_TO_DB_STATUS_MAP.get(python_status_value, python_status_value)

        if python_status_value == PythonTaskStatus.PROCESSING.value:
            logger.warning(f"Attempting to update task {task_id} to 'processing' status. This status is not in DB enum. Updating to 'in_progress'.")
            db_status = PythonTaskStatus.IN_PROGRESS.value
        
        fields_to_update = ["status = %s", "updated_at = %s"]
        values = [db_status, datetime.now()]

        if error_message is not None:
            fields_to_update.append("error_message = %s")
            values.append(error_message)
        
        if url is not None:
            fields_to_update.append("published_url = %s") # DB uses published_url
            values.append(url)
        
        values.append(task_id) # For WHERE clause

        sql = f"UPDATE tasks SET {', '.join(fields_to_update)} WHERE task_id = %s RETURNING *;"
        
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                cur.execute(sql, tuple(values))
                updated_row = cur.fetchone()
                conn.commit()
                if updated_row:
                    logger.info(f"Task {task_id} status updated to '{db_status}'.")
                    return self._map_row_to_task(updated_row)
                else:
                    logger.warning(f"Task {task_id} not found or not updated.")
                    return None
        except psycopg2.Error as e:
            logger.error(f"Error updating task {task_id} status: {e}")
            conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """
        Retrieves a specific task by its ID.
        """
        conn = get_db_connection()
        if not conn:
            return None
        
        sql = "SELECT * FROM tasks WHERE task_id = %s;"
        task: Optional[Task] = None
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                cur.execute(sql, (task_id,))
                row = cur.fetchone()
                if row:
                    task = self._map_row_to_task(row)
                    logger.info(f"Retrieved task {task_id}.")
                else:
                    logger.info(f"Task {task_id} not found.")
        except psycopg2.Error as e:
            logger.error(f"Error retrieving task {task_id}: {e}")
        finally:
            if conn:
                conn.close()
        return task

    def get_queue_stats(self) -> Dict[str, int]:
        """
        Retrieves statistics about the number of tasks in each status.
        """
        conn = get_db_connection()
        if not conn:
            return {} # Return empty dict if DB connection fails

        # Query to count tasks by status
        sql = "SELECT status, COUNT(*) as count FROM tasks GROUP BY status;"
        stats: Dict[str, int] = {}
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                for row in rows:
                    # Map DB status back to Python status string for consistency in stats keys if desired
                    db_status = row['status']
                    python_status_key = DB_TO_PYTHON_STATUS_MAP.get(db_status, db_status)
                    stats[python_status_key] = row['count']
            logger.info(f"Retrieved queue stats: {stats}")
        except psycopg2.Error as e:
            logger.error(f"Error retrieving queue stats: {e}")
        finally:
            if conn:
                conn.close()
        
        # Ensure all PythonTaskStatus values are in stats, with 0 if not present
        # This loop and the logic within it correctly rebuilds 'final_stats'
        # It should be outside the try-except-finally for DB ops, operating on 'stats' dict.
        
        final_stats = {py_status.value: 0 for py_status in PythonTaskStatus}
        for db_stat_key, count in stats.items(): # Iterate over what was actually fetched
            python_equivalent_status_str = DB_TO_PYTHON_STATUS_MAP.get(db_stat_key, db_stat_key)
            try:
                matching_py_enum = PythonTaskStatus(python_equivalent_status_str)
                final_stats[matching_py_enum.value] = count
            except ValueError:
                logger.warning(f"DB status '{db_stat_key}' (mapped to '{python_equivalent_status_str}') has no PythonTaskStatus enum value. Storing with original key if it's a direct python value, else as raw DB key.")
                # If python_equivalent_status_str is already a value in PythonTaskStatus, it's fine.
                # Otherwise, store with the key that came from DB if it's not already handled.
                if python_equivalent_status_str not in final_stats: # Avoid overwriting if it matched a Python enum value
                    final_stats[db_stat_key] = count # Store with original DB key
        
        # The loop for status_enum_member was to ensure all PythonTaskStatus keys exist.
        # The above logic correctly maps DB keys to Python enum values.
        # The final_stats dictionary is initialized with all PythonTaskStatus values set to 0.
        # So, any status not present in the DB query result will remain 0.
        return final_stats

    # save_queue is no longer needed as operations are transactional.
    # load_queue is conceptually replaced by get_tasks_by_status or get_pending_tasks.

# Example usage (for testing purposes, typically not here)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info("QueueManager script executed directly (minimal main block).")
    # Intentionally keeping it simple to avoid syntax issues.
    # Original example code has been removed/simplified to fix a suspected EOF syntax error.
    manager = QueueManager()
    
    # Basic test: Get queue stats
    stats = manager.get_queue_stats()
    logger.info(f"Example Queue stats: {stats}")

    # Basic test: Test connection directly
    db_conn = get_db_connection()
    if db_conn:
        logger.info("Direct DB connection test successful in main.")
        db_conn.close()
    else:
        logger.error("Direct DB connection test failed in main.")
```
