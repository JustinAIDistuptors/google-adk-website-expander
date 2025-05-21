import unittest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
import os
import sys
import json
from datetime import datetime
import psycopg2 # For psycopg2.Error

# Add project root to sys.path to allow direct import of src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_agents.publisher.publisher_agent import PublisherAgent
from src.models.task import Task, TaskStatus as PythonTaskStatus
from src.utils.queue_manager import QueueManager # For type hinting QueueManager mock

# Minimal config for the agent during tests
TEST_AGENT_CONFIG = {
    "agent_name": "test_publisher",
    "description": "Test description",
    "goal": "Test goal",
    "llm_config": {"model_name": "gemini-1.5-flash-001"}, # Mock LLM
    "instruction": "Base instruction for publishing.",
    "dry_run": False, # Test with dry_run False by default
    "sitemap_output_dir": "data/test_sitemap" # For sitemap tool
}

TEST_PUBLISHING_CONFIG = { # Loaded by _load_publishing_config
    'website': {'base_url': "https://test.example.com"},
    'url_structure': {'pattern': "{service_slug}/{location_zip}"}
}


# Sample Task Pydantic model for testing
SAMPLE_TASK = Task(
    task_id="test_pub_srv_zip1",
    service_id="test_pub_srv",
    zip="zip1",
    city="PublishCity",
    state="PB",
    status=PythonTaskStatus.ASSEMBLY_COMPLETE # Status when publishing would run
)

SAMPLE_ASSEMBLED_PAGE_DB_ROW = {
    "html_content": "<!DOCTYPE html><html><body><h1>Test Page</h1></body></html>",
    "metadata": {"source_template_id": "tpl1"}
}


class TestPublisherAgent(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        with patch('ai_agents.shared.base_agent.BaseAgent._load_config_from_yaml', return_value=TEST_AGENT_CONFIG):
            with patch('ai_agents.publisher.publisher_agent.PublisherAgent._load_publishing_config', return_value=TEST_PUBLISHING_CONFIG):
                with patch('ai_agents.shared.base_agent.BaseAgent.initialize_llm_and_runner'): # Prevent actual LLM init
                    # The tools are created in initialize_agent, which is called by super().__init__ if not careful
                    # For this agent, tools are complex, so we'll let initialize_agent run,
                    # but we'll test the *internal logic* of those tool functions separately.
                    self.agent = PublisherAgent(config_path="dummy_config.yaml")

        # Mock QueueManager instance for the agent
        self.mock_queue_manager = MagicMock(spec=QueueManager)
        self.agent.queue_manager = self.mock_queue_manager
        
        self.agent.logger = MagicMock()

        # The tools are created during __init__ via initialize_agent().
        # We can get references to their internal functions if needed, or test via ADK runner mock.
        # For direct testing of tool logic:
        self.publish_page_tool_logic = self.agent.tools[0] # publish_page_tool is first
        self.update_sitemap_tool_logic = self.agent.tools[1] # update_sitemap_tool is second


    # --- Test inner logic of publish_page_tool ---
    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    def test_publish_page_tool_logic_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = SAMPLE_ASSEMBLED_PAGE_DB_ROW
        
        result = self.publish_page_tool_logic(
            task_id=SAMPLE_TASK.task_id, 
            service_id=SAMPLE_TASK.service_id, 
            zip_code=SAMPLE_TASK.zip, 
            dry_run=False
        )
        
        self.assertEqual(result["status"], "success")
        self.assertIn("Page published successfully (simulated)", result["message"])
        expected_url = f"{TEST_PUBLISHING_CONFIG['website']['base_url']}/{SAMPLE_TASK.service_id.replace('_', '-')}/{SAMPLE_TASK.zip}/"
        self.assertEqual(result["url"], expected_url)
        mock_cursor.execute.assert_called_once_with(
            "SELECT html_content, metadata FROM assembled_pages WHERE task_id = %s;", (SAMPLE_TASK.task_id,)
        )

    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    def test_publish_page_tool_logic_dry_run(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = SAMPLE_ASSEMBLED_PAGE_DB_ROW
        
        result = self.publish_page_tool_logic(
            task_id=SAMPLE_TASK.task_id, service_id=SAMPLE_TASK.service_id, zip_code=SAMPLE_TASK.zip, dry_run=True
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("Page would have been published (dry run)", result["message"])

    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    def test_publish_page_tool_logic_page_not_found_in_db(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Simulate page not found
        
        result = self.publish_page_tool_logic(task_id="ghost_task", service_id="s", zip_code="z", dry_run=False)
        self.assertEqual(result["status"], "error")
        self.assertIn("Assembled page not found in DB for task_id ghost_task", result["error"])

    @patch('ai_agents.publisher.publisher_agent.get_db_connection', side_effect=psycopg2.Error("DB error"))
    def test_publish_page_tool_logic_db_error(self, mock_get_conn_error):
        # This test needs get_db_connection to return a context manager that then raises an error,
        # or for the connection attempt itself (if not using context manager directly in tool) to fail.
        # The tool uses 'with get_db_connection() as conn:'. If conn is None, it handles it.
        # If conn.cursor() raises, that's another path.
        mock_get_conn_error.return_value.__enter__.side_effect = psycopg2.Error("DB error during connect/cursor")

        result = self.publish_page_tool_logic(task_id="any", service_id="s", zip_code="z")
        self.assertEqual(result["status"], "error")
        self.assertIn("DB error", result["error"]) # Check if the error message indicates DB issue

    # --- Test inner logic of update_sitemap_tool ---
    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    @patch('builtins.open', new_callable=mock_open) # Mock file writing
    @patch('os.makedirs') # Mock directory creation
    def test_update_sitemap_tool_logic_success(self, mock_makedirs, mock_file_open, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        db_rows = [
            {'published_url': 'https://test.example.com/service1/zip1/'},
            {'published_url': 'https://test.example.com/service2/zip2/'}
        ]
        mock_cursor.fetchall.return_value = db_rows
        
        result = self.update_sitemap_tool_logic()
        
        self.assertEqual(result["status"], "success")
        self.assertIn("Sitemap updated with 2 pages", result["message"])
        
        mock_cursor.execute.assert_called_once_with(
            "SELECT published_url FROM tasks WHERE status = 'published' AND published_url IS NOT NULL;"
        )
        sitemap_path = os.path.join(TEST_AGENT_CONFIG["sitemap_output_dir"], "sitemap.xml")
        mock_makedirs.assert_called_with(TEST_AGENT_CONFIG["sitemap_output_dir"], exist_ok=True)
        mock_file_open.assert_called_once_with(sitemap_path, 'w')
        
        # Check content written to sitemap
        handle = mock_file_open()
        written_content = "".join(call_args[0][0] for call_args in handle.write.call_args_list)
        self.assertIn("<loc>https://test.example.com/service1/zip1/</loc>", written_content)
        self.assertIn("<loc>https://test.example.com/service2/zip2/</loc>", written_content)

    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_update_sitemap_tool_logic_no_published_pages(self, mock_makedirs, mock_file_open, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [] # No published pages
        
        result = self.update_sitemap_tool_logic()
        self.assertEqual(result["status"], "success")
        self.assertIn("Sitemap updated with 0 pages", result["message"])

    # --- Test _is_page_assembled ---
    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    async def test_is_page_assembled_exists(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (True,) # DB returns a tuple
        
        exists = await self.agent._is_page_assembled("task_exists")
        self.assertTrue(exists)
        mock_cursor.execute.assert_called_once_with(
            "SELECT EXISTS (SELECT 1 FROM assembled_pages WHERE task_id = %s);", ("task_exists",)
        )

    @patch('ai_agents.publisher.publisher_agent.get_db_connection')
    async def test_is_page_assembled_not_exists(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (False,)
        
        exists = await self.agent._is_page_assembled("task_not_exists")
        self.assertFalse(exists)

    # --- Test process_task ---
    @patch('ai_agents.publisher.publisher_agent.PublisherAgent._is_page_assembled', new_callable=AsyncMock)
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock) # Mock the LLM runner
    async def test_process_task_successful_publish(self, mock_run_async, mock_is_assembled):
        mock_is_assembled.return_value = True
        
        # Simulate ADK runner returning a tool response from publish_page_tool
        mock_publish_tool_response_part = MagicMock()
        mock_publish_tool_response_part.tool_response = MagicMock()
        mock_publish_tool_response_part.tool_response.response = { # This is what publish_page_tool returns
            "status": "success", 
            "url": "https://test.example.com/mock_service/mock_zip/",
            "message": "Page published successfully (simulated)"
        }
        
        # Simulate final LLM response after tool call
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text="LLM summary: Page published and sitemap updated.")]
        
        # Make run_async an async generator yielding tool response then final response
        async def async_generator_mock(*args, **kwargs):
            # First yield the tool response event
            tool_event = MagicMock()
            tool_event.is_tool_response.return_value = True
            tool_event.is_final_response.return_value = False
            tool_event.content = MagicMock()
            tool_event.content.parts = [mock_publish_tool_response_part]
            yield tool_event
            # Then yield the final LLM text response
            yield mock_final_event

        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock() 
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)
        
        self.assertEqual(result["status"], PythonTaskStatus.PUBLISHED.value)
        self.assertEqual(result["url"], "https://test.example.com/mock_service/mock_zip/")
        self.assertIn("Successfully published (mocked)", result["message"])
        
        mock_is_assembled.assert_called_once_with(SAMPLE_TASK.task_id)
        mock_run_async.assert_called_once() # Check LLM runner was called
        self.mock_queue_manager.update_task_status.assert_called_once_with(
            SAMPLE_TASK.task_id, PythonTaskStatus.PUBLISHED, url="https://test.example.com/mock_service/mock_zip/"
        )

    @patch('ai_agents.publisher.publisher_agent.PublisherAgent._is_page_assembled', new_callable=AsyncMock)
    async def test_process_task_assembled_page_not_found(self, mock_is_assembled):
        mock_is_assembled.return_value = False # Simulate page not assembled
        
        result = await self.agent.process_task(SAMPLE_TASK)
        
        self.assertEqual(result["status"], "error") # This is the process_result status
        self.assertIn(f"Assembled page not found in DB for task {SAMPLE_TASK.task_id}", result["message"])
        # Check that task status in DB is NOT updated to FAILED by this specific path,
        # as the error is before calling the LLM. The task remains in its current state.
        # If the orchestrator needs to know, it would check process_result["status"]
        self.mock_queue_manager.update_task_status.assert_not_called()


    @patch('ai_agents.publisher.publisher_agent.PublisherAgent._is_page_assembled', new_callable=AsyncMock)
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_publishing_tool_error(self, mock_run_async, mock_is_assembled):
        mock_is_assembled.return_value = True
        
        mock_publish_tool_error_response_part = MagicMock()
        mock_publish_tool_error_response_part.tool_response = MagicMock()
        mock_publish_tool_error_response_part.tool_response.response = {
            "status": "error", 
            "error": "CMS connection failed",
            "message": "Failed to publish page"
        }
        
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text="LLM summary: Publishing failed.")]

        async def async_generator_mock(*args, **kwargs):
            tool_event = MagicMock()
            tool_event.is_tool_response.return_value = True
            tool_event.is_final_response.return_value = False
            tool_event.content = MagicMock()
            tool_event.content.parts = [mock_publish_tool_error_response_part]
            yield tool_event
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)
        
        self.assertEqual(result["status"], PythonTaskStatus.FAILED.value) # process_result status
        self.assertIn("Publishing failed. Tool error: CMS connection failed", result["message"])
        
        self.mock_queue_manager.update_task_status.assert_called_once_with(
            SAMPLE_TASK.task_id, PythonTaskStatus.FAILED, error_message="CMS connection failed"
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)
```
