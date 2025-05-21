import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
import json
from datetime import datetime
import psycopg2 # For psycopg2.Error

# Add project root to sys.path to allow direct import of src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_agents.page_assembler.page_assembler_agent import PageAssemblerAgent
from src.models.task import Task, TaskStatus as PythonTaskStatus

# Minimal config for the agent during tests
TEST_AGENT_CONFIG = {
    "agent_name": "test_page_assembler",
    "description": "Test description",
    "goal": "Test goal",
    "llm_config": {"model_name": "gemini-1.5-flash-001"}, # Mock LLM
    "instruction": "Base instruction for assembly.",
    "default_html_template_id": "test_default_html_template"
}

# Sample Task Pydantic model for testing
SAMPLE_TASK = Task(
    task_id="test_service_html_12345",
    service_id="test_service_html",
    zip="12345",
    city="HTMLCity",
    state="HT",
    status=PythonTaskStatus.ASSEMBLY_COMPLETE # Or whatever status precedes assembly
)

SAMPLE_CONTENT_DATA = {
    "title": "Test Page Title",
    "meta_title": "Meta Title for Test Page",
    "meta_description": "Meta description for test page.",
    "h1_title": "Main H1 Title",
    "main_content": "<p>This is the main content.</p>",
    "faq_title": "FAQs",
    "faq_content": "<div><p>Q: Question? A: Answer.</p></div>",
    "cta_title": "Call Now!",
    "cta_content": "<p>Contact us today.</p>",
    "service_details": {"name": "Test Service"} # Used by _generate_schema_markup
}

class TestPageAssemblerAgent(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        with patch('ai_agents.shared.base_agent.BaseAgent._load_config_from_yaml', return_value=TEST_AGENT_CONFIG):
            with patch('ai_agents.shared.base_agent.BaseAgent.initialize_llm_and_runner'):
                self.agent = PageAssemblerAgent(config_path="dummy_config.yaml")
        self.agent.logger = MagicMock()

    # --- Test Helper Data Loading Methods ---

    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection')
    def test_get_content_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {'content_data': SAMPLE_CONTENT_DATA}
        
        content_data = self.agent._get_content_data("task1")
        
        self.assertEqual(content_data, SAMPLE_CONTENT_DATA)
        mock_cursor.execute.assert_called_once_with(
            "SELECT content_data FROM generated_content WHERE task_id = %s;", ("task1",)
        )

    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection')
    def test_get_content_data_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        
        content_data = self.agent._get_content_data("non_existent_task")
        self.assertIsNone(content_data)
        self.agent.logger.warning.assert_any_call("Content data not found for task non_existent_task.")

    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection', side_effect=psycopg2.Error("DB connection error"))
    def test_get_content_data_db_error_connect(self, mock_get_conn_error):
        mock_get_conn_error.return_value.__enter__.return_value = None # Simulate connection failure
        content_data = self.agent._get_content_data("any_task")
        self.assertIsNone(content_data)
        self.agent.logger.error.assert_any_call("Failed to get DB connection for content data (task any_task).")

    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection')
    def test_get_html_template_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_html_str = "<html><body>{body_content}</body></html>"
        # Simulate template_data being a dict with the HTML string
        mock_cursor.fetchone.return_value = {'template_data': {'html_body_template': expected_html_str}}
        
        html_template = self.agent._get_html_template("tpl1")
        self.assertEqual(html_template, expected_html_str)
        mock_cursor.execute.assert_called_once_with(
            "SELECT template_data FROM content_templates WHERE template_id = %s;", ("tpl1",)
        )

    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection')
    def test_get_html_template_not_found_or_wrong_format(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Test 1: Template ID not found in DB
        mock_cursor.fetchone.return_value = None
        default_template_str = self.agent._get_default_html_template_string()
        html_template = self.agent._get_html_template("non_existent_tpl")
        self.assertEqual(html_template, default_template_str)
        self.agent.logger.warning.assert_any_call("HTML template non_existent_tpl not found or not a dict in DB. Using default.")

        # Test 2: Template data is dict, but missing the expected key for HTML string
        mock_cursor.fetchone.return_value = {'template_data': {'some_other_key': 'value'}}
        html_template_2 = self.agent._get_html_template("tpl_no_html_key")
        self.assertEqual(html_template_2, default_template_str)
        self.agent.logger.warning.assert_any_call("HTML string not found in template_data for tpl_no_html_key (keys: dict_keys(['some_other_key'])). Using default.")

    # --- Test _generate_schema_markup (direct test) ---
    def test_generate_schema_markup(self):
        schema_dict = self.agent._generate_schema_markup(SAMPLE_CONTENT_DATA, SAMPLE_TASK)
        self.assertEqual(schema_dict["@context"], "https://schema.org")
        self.assertEqual(schema_dict["@type"], "LocalBusiness")
        self.assertEqual(schema_dict["name"], SAMPLE_CONTENT_DATA["meta_title"]) # Uses meta_title as fallback
        self.assertEqual(schema_dict["address"]["addressLocality"], SAMPLE_TASK.city)
        self.assertIn("itemOffered", schema_dict["hasOffer"]) # Check service part

    # --- Test _save_assembled_page (indirectly via process_task) ---

    # --- Test process_task ---
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._save_assembled_page')
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._generate_schema_markup')
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._get_html_template')
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._get_content_data')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock) # Mock the LLM runner
    async def test_process_task_successful_run(self, mock_run_async, mock_get_content, 
                                         mock_get_template, mock_gen_schema, mock_save_page):
        # Setup mocks for helper methods
        mock_get_content.return_value = SAMPLE_CONTENT_DATA
        mock_get_template.return_value = "<html><head>{schema_markup_script_tag}</head><body>{main_content}</body></html>"
        mock_schema_dict = {"@type": "LocalBusiness", "name": "Test Biz"}
        mock_gen_schema.return_value = mock_schema_dict
        mock_save_page.return_value = True # Simulate successful save

        # Mock LLM response (final assembled HTML)
        expected_final_html = "<!DOCTYPE html><html><head><script type=\"application/ld+json\">...</script></head><body><p>This is the main content.</p></body></html>"
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=expected_final_html)]
        
        async def async_generator_mock(*args, **kwargs):
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock() 
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "completed")
        self.assertIn("Page assembled and saved to DB.", result["message"])
        self.assertTrue(result["html_preview"].startswith("<!DOCTYPE html>"))
        
        mock_get_content.assert_called_once_with(SAMPLE_TASK.task_id)
        mock_get_template.assert_called_once() # Called with default or configured template ID
        mock_gen_schema.assert_called_once_with(SAMPLE_CONTENT_DATA, SAMPLE_TASK)
        mock_run_async.assert_called_once() # Check LLM was called
        
        # Check that _save_assembled_page was called correctly
        mock_save_page.assert_called_once()
        args_save, _ = mock_save_page.call_args
        self.assertEqual(args_save[0], SAMPLE_TASK.task_id)    # task_id
        self.assertEqual(args_save[1], expected_final_html)    # html_content
        self.assertEqual(args_save[2], mock_schema_dict)       # schema_markup (as dict)
        self.assertIsInstance(args_save[3], dict)              # metadata (should be a dict)
        self.assertIn("source_template_id", args_save[3])


    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._get_content_data', return_value=None)
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock) # Mock LLM runner
    async def test_process_task_content_load_failure(self, mock_run_async, mock_get_content_fail):
        # mock_get_content_fail is already set by @patch to return None
        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "error")
        self.assertIn(f"Content data not found for task {SAMPLE_TASK.task_id}", result["message"])
        mock_run_async.assert_not_called() # LLM should not be called if content is missing


    @patch('ai_agents.page_assembler.page_assembler_agent.get_db_connection') # For _save_assembled_page's attempt
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._generate_schema_markup')
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._get_html_template')
    @patch('ai_agents.page_assembler.page_assembler_agent.PageAssemblerAgent._get_content_data')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_db_save_failure(self, mock_run_async, mock_get_content, 
                                          mock_get_template, mock_gen_schema,
                                          mock_get_db_conn_for_save): # Mocks _save_assembled_page's DB call
        # Setup mocks for successful data loading and LLM response
        mock_get_content.return_value = SAMPLE_CONTENT_DATA
        mock_get_template.return_value = "<html><body>{main_content}</body></html>"
        mock_gen_schema.return_value = {"@type": "LocalBusiness"}

        expected_final_html = "<html><body><p>Content</p></body></html>"
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=expected_final_html)]
        
        async def async_generator_mock(*args, **kwargs):
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async
        
        # Mock DB connection for _save_assembled_page to fail
        mock_conn_save = MagicMock()
        mock_cursor_save = MagicMock()
        mock_get_db_conn_for_save.return_value.__enter__.return_value = mock_conn_save
        mock_conn_save.cursor.return_value.__enter__.return_value = mock_cursor_save
        mock_cursor_save.execute.side_effect = psycopg2.Error("DB error during save of assembled page")

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "error")
        self.assertIn("Failed to save assembled page to DB.", result["message"])
        mock_conn_save.rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
```
