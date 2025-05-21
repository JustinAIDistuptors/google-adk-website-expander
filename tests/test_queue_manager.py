import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime
import psycopg2 # For psycopg2.Error

# Add src to path for imports if tests are run from root
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.queue_manager import QueueManager, get_db_connection
from src.models.task import Task, TaskStatus as PythonTaskStatus

# Store original environment variables
ORIGINAL_ENV = os.environ.copy()

class TestQueueManager(unittest.TestCase):

    def setUp(self):
        """
        Set up for test methods.
        This method is called before each test function execution.
        """
        # It's good practice to ensure a clean environment for each test.
        # For QueueManager, the constructor itself tries to connect, so mock it here too.
        with patch('src.utils.queue_manager.psycopg2.connect') as mock_connect_init:
            mock_conn_init = MagicMock()
            mock_connect_init.return_value = mock_conn_init
            self.manager = QueueManager()
        
        # Default task data for reuse
        self.sample_task_data = {
            "task_id": "service1_12345",
            "service_id": "service1",
            "zip_code": "12345", # DB field name
            "city": "Testville",
            "state": "TS",
            "status": PythonTaskStatus.PENDING.value, # Python value
            "created_at": datetime(2023, 1, 1, 10, 0, 0),
            "updated_at": datetime(2023, 1, 1, 10, 0, 0),
            "error_message": None,
            "published_url": None # DB field name
        }
        self.sample_task_obj = Task(
            task_id="service1_12345",
            service_id="service1",
            zip="12345", # Model field name
            city="Testville",
            state="TS",
            status=PythonTaskStatus.PENDING,
            created_at=datetime(2023, 1, 1, 10, 0, 0),
            updated_at=datetime(2023, 1, 1, 10, 0, 0),
            error_message=None,
            url=None # Model field name
        )

    def tearDown(self):
        """
        Clean up after test methods.
        This method is called after each test function execution.
        """
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(ORIGINAL_ENV)

    # --- Tests for get_db_connection ---
    @patch('src.utils.queue_manager.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        # Set dummy env vars for the test
        os.environ["DB_HOST"] = "test_host"
        os.environ["DB_PORT"] = "1234"
        os.environ["DB_NAME"] = "test_db"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_pass"

        conn = get_db_connection()
        self.assertIsNotNone(conn)
        self.assertEqual(conn, mock_conn)
        mock_connect.assert_called_once_with(
            host="test_host",
            port="1234",
            dbname="test_db",
            user="test_user",
            password="test_pass"
        )

    @patch('src.utils.queue_manager.psycopg2.connect', side_effect=psycopg2.Error("Connection failed"))
    def test_get_db_connection_failure(self, mock_connect):
        conn = get_db_connection()
        self.assertIsNone(conn)
        mock_connect.assert_called_once() # Check it was called

    # --- Tests for QueueManager._map_row_to_task ---
    def test_map_row_to_task_direct_all_fields(self):
        # Test the private helper directly for clarity on mapping
        row_data = {
            "task_id": "s1_z1", "service_id": "s1", "zip_code": "z1", "city": "CityA", "state": "ST",
            "status": "pending", "created_at": datetime(2023,1,1), "updated_at": datetime(2023,1,2),
            "error_message": "An error", "published_url": "http://example.com/page"
        }
        task = self.manager._map_row_to_task(row_data)
        self.assertIsInstance(task, Task)
        self.assertEqual(task.task_id, "s1_z1")
        self.assertEqual(task.service_id, "s1")
        self.assertEqual(task.zip, "z1") # zip_code -> zip
        self.assertEqual(task.city, "CityA")
        self.assertEqual(task.state, "ST")
        self.assertEqual(task.status, PythonTaskStatus.PENDING)
        self.assertEqual(task.created_at, datetime(2023,1,1))
        self.assertEqual(task.updated_at, datetime(2023,1,2))
        self.assertEqual(task.error_message, "An error")
        self.assertEqual(task.url, "http://example.com/page") # published_url -> url

    def test_map_row_to_task_status_mappings(self):
        status_pairs = [
            ("pending", PythonTaskStatus.PENDING),
            ("in_progress", PythonTaskStatus.IN_PROGRESS),
            ("seo_research_complete", PythonTaskStatus.SEO_COMPLETE), # DB to Python
            ("content_generation_complete", PythonTaskStatus.CONTENT_COMPLETE), # DB to Python
            ("page_assembly_complete", PythonTaskStatus.ASSEMBLY_COMPLETE), # DB to Python
            ("published", PythonTaskStatus.PUBLISHED),
            ("failed", PythonTaskStatus.FAILED),
            ("error", PythonTaskStatus.ERROR),
            ("unknown_db_status", PythonTaskStatus.ERROR) # Fallback for unknown status
        ]
        base_row = {"task_id": "t1", "service_id": "s1", "zip_code": "z1"}
        for db_status_str, expected_py_status in status_pairs:
            row = {**base_row, "status": db_status_str}
            with self.subTest(db_status=db_status_str):
                task = self.manager._map_row_to_task(row)
                self.assertEqual(task.status, expected_py_status)

    # --- Tests for QueueManager.add_task ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_add_task_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        db_row_after_insert = {**self.sample_task_data} # In DB format
        mock_cursor.fetchone.return_value = db_row_after_insert

        task_to_add = { # Data as might be passed to add_task
            "task_id": "service1_12345",
            "service_id": "service1",
            "zip_code": "12345", 
            "city": "Testville",
            "state": "TS",
            # status will default to PENDING if not provided
        }
        
        # Expected SQL status: 'pending'
        expected_db_status = PythonTaskStatus.PENDING.value 

        added_task = self.manager.add_task(task_to_add)
        
        self.assertIsNotNone(added_task)
        self.assertEqual(added_task.task_id, task_to_add["task_id"])
        self.assertEqual(added_task.status, PythonTaskStatus.PENDING)
        mock_get_conn.assert_called_once()
        mock_conn.cursor.assert_called_once()
        
        # Check the SQL query and parameters
        args, _ = mock_cursor.execute.call_args
        self.assertIn("INSERT INTO tasks", args[0])
        # Order of values: task_id, service_id, zip_code, city, state, status, error_message, published_url, created_at, updated_at
        self.assertEqual(args[1][0], task_to_add["task_id"])
        self.assertEqual(args[1][1], task_to_add["service_id"])
        self.assertEqual(args[1][2], task_to_add["zip_code"])
        self.assertEqual(args[1][5], expected_db_status) # Status
        mock_conn.commit.assert_called_once()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_add_task_with_specific_status(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_data_for_db = {**self.sample_task_data, "status": "seo_research_complete"} # DB representation
        mock_cursor.fetchone.return_value = task_data_for_db
        
        task_to_add = {
            "task_id": "service1_12345", "service_id": "service1", "zip_code": "12345",
            "status": PythonTaskStatus.SEO_COMPLETE # Python Enum
        }
        # Expected DB status after mapping PythonTaskStatus.SEO_COMPLETE
        expected_db_status = "seo_research_complete"

        added_task = self.manager.add_task(task_to_add)
        self.assertIsNotNone(added_task)
        self.assertEqual(added_task.status, PythonTaskStatus.SEO_COMPLETE) # Python model uses Python enum
        
        args, _ = mock_cursor.execute.call_args
        self.assertEqual(args[1][5], expected_db_status) # Check mapped status was used in SQL
        mock_conn.commit.assert_called_once()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_add_task_processing_status_maps_to_in_progress(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # DB will store 'in_progress', so mock fetchone to return that
        task_data_for_db = {**self.sample_task_data, "status": PythonTaskStatus.IN_PROGRESS.value}
        mock_cursor.fetchone.return_value = task_data_for_db

        task_to_add = {
            "task_id": "s1_z1_proc", "service_id": "s1", "zip_code": "z1",
            "status": PythonTaskStatus.PROCESSING # This should be mapped
        }
        expected_db_status = PythonTaskStatus.IN_PROGRESS.value # Mapped value

        added_task = self.manager.add_task(task_to_add)
        self.assertIsNotNone(added_task)
        # The returned Task object status should reflect what was intended if possible,
        # or what was actually stored if mapping is strict.
        # Current _map_row_to_task will map "in_progress" from DB back to PythonTaskStatus.IN_PROGRESS.
        self.assertEqual(added_task.status, PythonTaskStatus.IN_PROGRESS)
        
        args, _ = mock_cursor.execute.call_args
        self.assertEqual(args[1][5], expected_db_status) # Check 'in_progress' used in SQL
        mock_conn.commit.assert_called_once()


    @patch('src.utils.queue_manager.get_db_connection')
    def test_add_task_db_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB write error")

        task_to_add = {"task_id": "s1_z1", "service_id": "s1", "zip_code": "z1"}
        added_task = self.manager.add_task(task_to_add)
        
        self.assertIsNone(added_task)
        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()


    # --- Tests for QueueManager.get_tasks_by_status / get_pending_tasks ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_tasks_by_status_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # DB rows (e.g. 'seo_research_complete')
        db_rows = [
            {**self.sample_task_data, "task_id": "t1", "status": "seo_research_complete"},
            {**self.sample_task_data, "task_id": "t2", "status": "seo_research_complete"}
        ]
        mock_cursor.fetchall.return_value = db_rows

        # Query using Python enum (PythonTaskStatus.SEO_COMPLETE)
        tasks = self.manager.get_tasks_by_status(PythonTaskStatus.SEO_COMPLETE, limit=5)
        
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].task_id, "t1")
        self.assertEqual(tasks[0].status, PythonTaskStatus.SEO_COMPLETE) # Check Python enum in Task obj
        self.assertEqual(tasks[1].status, PythonTaskStatus.SEO_COMPLETE)
        
        args, _ = mock_cursor.execute.call_args
        self.assertIn("SELECT * FROM tasks WHERE status = %s LIMIT 5", args[0])
        # Check that the DB status string was used in the query
        self.assertEqual(args[1][0], "seo_research_complete") 

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_tasks_by_status_empty(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [] # No tasks found

        tasks = self.manager.get_tasks_by_status(PythonTaskStatus.PENDING)
        self.assertEqual(len(tasks), 0)

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_tasks_by_status_processing_query(self, mock_get_conn):
        # Querying for 'processing' status, which is not in DB enum, should return empty.
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn # Ensure connection is "successful"

        tasks = self.manager.get_tasks_by_status(PythonTaskStatus.PROCESSING)
        self.assertEqual(len(tasks), 0)
        # Verify no DB call was made for "processing" as it's handled internally
        mock_conn.cursor.assert_not_called()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_pending_tasks(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        db_rows = [{**self.sample_task_data, "status": "pending"}]
        mock_cursor.fetchall.return_value = db_rows

        # Patch the manager's own get_tasks_by_status to spy on it
        with patch.object(self.manager, 'get_tasks_by_status', wraps=self.manager.get_tasks_by_status) as spy_get_by_status:
            pending_tasks = self.manager.get_pending_tasks(limit=10)
            spy_get_by_status.assert_called_once_with(PythonTaskStatus.PENDING, limit=10)
            self.assertEqual(len(pending_tasks), 1)
            self.assertEqual(pending_tasks[0].status, PythonTaskStatus.PENDING)

            args, _ = mock_cursor.execute.call_args # from the wrapped call
            self.assertIn("SELECT * FROM tasks WHERE status = %s LIMIT 10", args[0])
            self.assertEqual(args[1][0], "pending")


    # --- Tests for QueueManager.mark_tasks_in_progress ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_mark_tasks_in_progress_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        tasks_to_mark = [
            Task(task_id="t1", service_id="s1", zip="z1", status=PythonTaskStatus.PENDING),
            Task(task_id="t2", service_id="s2", zip="z2", status=PythonTaskStatus.PENDING)
        ]
        # DB rows returned after update
        updated_db_rows = [
            {**self.sample_task_data, "task_id": "t1", "status": "in_progress"},
            {**self.sample_task_data, "task_id": "t2", "status": "in_progress"}
        ]
        mock_cursor.fetchall.return_value = updated_db_rows

        updated_tasks = self.manager.mark_tasks_in_progress(tasks_to_mark)
        self.assertEqual(len(updated_tasks), 2)
        self.assertTrue(all(t.status == PythonTaskStatus.IN_PROGRESS for t in updated_tasks))
        
        args, _ = mock_cursor.execute.call_args
        self.assertIn("UPDATE tasks", args[0])
        self.assertEqual(args[1][0], "in_progress") # Target status
        self.assertEqual(args[1][2], ["t1", "t2"])    # Task IDs
        self.assertEqual(args[1][3], "pending")       # Condition: current status must be pending
        mock_conn.commit.assert_called_once()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_mark_tasks_in_progress_not_pending(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Simulate DB returning no rows because condition (status='pending') wasn't met
        mock_cursor.fetchall.return_value = [] 

        tasks_to_mark = [Task(task_id="t1", service_id="s1", zip="z1", status=PythonTaskStatus.SEO_COMPLETE)]
        updated_tasks = self.manager.mark_tasks_in_progress(tasks_to_mark)
        
        self.assertEqual(len(updated_tasks), 0)
        mock_conn.commit.assert_called_once() # Commit is called even if no rows affected

    @patch('src.utils.queue_manager.get_db_connection')
    def test_mark_tasks_in_progress_db_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB update error")

        tasks_to_mark = [Task(task_id="t1", service_id="s1", zip="z1", status=PythonTaskStatus.PENDING)]
        updated_tasks = self.manager.mark_tasks_in_progress(tasks_to_mark)

        self.assertEqual(len(updated_tasks), 0)
        mock_conn.rollback.assert_called_once()


    # --- Tests for QueueManager.update_task_status ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_update_task_status_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_id_to_update = "task_abc"
        new_status_py = PythonTaskStatus.PUBLISHED
        new_status_db = "published" # DB value for 'published'
        new_url = "http://example.com/published_task_abc"

        # DB row returned after update
        updated_db_row = {
            **self.sample_task_data, 
            "task_id": task_id_to_update, 
            "status": new_status_db, 
            "published_url": new_url,
            "error_message": None
        }
        mock_cursor.fetchone.return_value = updated_db_row

        updated_task = self.manager.update_task_status(task_id_to_update, new_status_py, url=new_url)
        
        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task.task_id, task_id_to_update)
        self.assertEqual(updated_task.status, new_status_py)
        self.assertEqual(updated_task.url, new_url)
        self.assertIsNone(updated_task.error_message) # Check error message reset/not set

        args, _ = mock_cursor.execute.call_args
        self.assertIn(f"UPDATE tasks SET status = %s, updated_at = %s, published_url = %s WHERE task_id = %s RETURNING *;", args[0])
        self.assertEqual(args[1][0], new_status_db)
        self.assertEqual(args[1][2], new_url) # url
        self.assertEqual(args[1][3], task_id_to_update) # task_id for WHERE
        mock_conn.commit.assert_called_once()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_update_task_status_with_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_id_to_update = "task_fail"
        new_status_py = PythonTaskStatus.FAILED
        new_status_db = "failed"
        error_msg = "Something went wrong"
        
        updated_db_row = {
            **self.sample_task_data, "task_id": task_id_to_update, "status": new_status_db, "error_message": error_msg
        }
        mock_cursor.fetchone.return_value = updated_db_row

        updated_task = self.manager.update_task_status(task_id_to_update, new_status_py, error_message=error_msg)

        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task.status, new_status_py)
        self.assertEqual(updated_task.error_message, error_msg)

        args, _ = mock_cursor.execute.call_args
        self.assertIn(f"UPDATE tasks SET status = %s, updated_at = %s, error_message = %s WHERE task_id = %s RETURNING *;", args[0])
        self.assertEqual(args[1][0], new_status_db)
        self.assertEqual(args[1][2], error_msg)
        mock_conn.commit.assert_called_once()


    @patch('src.utils.queue_manager.get_db_connection')
    def test_update_task_status_mapping(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_id_to_update = "task_content_done"
        new_status_py = PythonTaskStatus.CONTENT_COMPLETE # Python "content_complete"
        expected_db_status = "content_generation_complete" # DB "content_generation_complete"

        updated_db_row = {**self.sample_task_data, "task_id": task_id_to_update, "status": expected_db_status}
        mock_cursor.fetchone.return_value = updated_db_row

        updated_task = self.manager.update_task_status(task_id_to_update, new_status_py)
        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task.status, new_status_py) # Python model gets Python enum

        args, _ = mock_cursor.execute.call_args
        self.assertEqual(args[1][0], expected_db_status) # Check DB status used in SQL
        mock_conn.commit.assert_called_once()

    @patch('src.utils.queue_manager.get_db_connection')
    def test_update_task_status_processing_maps_to_in_progress(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_id_to_update = "task_proc"
        new_status_py = PythonTaskStatus.PROCESSING # Python "processing"
        expected_db_status = "in_progress" # DB "in_progress"

        # DB returns 'in_progress'
        updated_db_row = {**self.sample_task_data, "task_id": task_id_to_update, "status": expected_db_status}
        mock_cursor.fetchone.return_value = updated_db_row
        
        updated_task = self.manager.update_task_status(task_id_to_update, new_status_py)
        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task.status, PythonTaskStatus.IN_PROGRESS) # Mapped back

        args, _ = mock_cursor.execute.call_args
        self.assertEqual(args[1][0], expected_db_status) # Check 'in_progress' used in SQL
        mock_conn.commit.assert_called_once()


    @patch('src.utils.queue_manager.get_db_connection')
    def test_update_task_status_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Task not found / not updated

        updated_task = self.manager.update_task_status("non_existent_task", PythonTaskStatus.PUBLISHED)
        self.assertIsNone(updated_task)
        mock_conn.commit.assert_called_once()


    # --- Tests for QueueManager.get_task_by_id ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_task_by_id_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        db_row = {**self.sample_task_data, "status": "pending"}
        mock_cursor.fetchone.return_value = db_row

        task = self.manager.get_task_by_id("service1_12345")
        self.assertIsNotNone(task)
        self.assertEqual(task.task_id, "service1_12345")
        self.assertEqual(task.status, PythonTaskStatus.PENDING)
        
        args, _ = mock_cursor.execute.call_args
        self.assertIn("SELECT * FROM tasks WHERE task_id = %s;", args[0])
        self.assertEqual(args[1][0], "service1_12345")

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_task_by_id_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        task = self.manager.get_task_by_id("non_existent")
        self.assertIsNone(task)

    # --- Tests for QueueManager.get_queue_stats ---
    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_queue_stats_various_data(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # DB rows: note DB status strings
        db_stats_rows = [
            {"status": "pending", "count": 5},
            {"status": "in_progress", "count": 3},
            {"status": "seo_research_complete", "count": 2}, # DB status
            {"status": "published", "count": 10}
        ]
        mock_cursor.fetchall.return_value = db_stats_rows

        stats = self.manager.get_queue_stats()
        
        # Expected stats, keys are PythonTaskStatus values
        expected_stats = {
            PythonTaskStatus.PENDING.value: 5,
            PythonTaskStatus.IN_PROGRESS.value: 3,
            PythonTaskStatus.PROCESSING.value: 0, # Should be initialized to 0
            PythonTaskStatus.SEO_COMPLETE.value: 2, # Python value
            PythonTaskStatus.CONTENT_COMPLETE.value: 0,
            PythonTaskStatus.ASSEMBLY_COMPLETE.value: 0,
            PythonTaskStatus.PUBLISHED.value: 10,
            PythonTaskStatus.FAILED.value: 0,
            PythonTaskStatus.ERROR.value: 0
        }
        self.assertEqual(stats, expected_stats)

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_queue_stats_empty_db(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [] # No stats from DB

        stats = self.manager.get_queue_stats()
        expected_stats_all_zero = {s.value: 0 for s in PythonTaskStatus}
        self.assertEqual(stats, expected_stats_all_zero)

    @patch('src.utils.queue_manager.get_db_connection')
    def test_get_queue_stats_db_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB stats error")

        stats = self.manager.get_queue_stats()
        self.assertEqual(stats, {}) # Returns empty dict on DB error


if __name__ == '__main__':
    unittest.main(verbosity=2)
```
