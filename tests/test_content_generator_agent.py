import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
import json
from datetime import datetime
import psycopg2 # For psycopg2.Error

# Add project root to sys.path to allow direct import of src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_agents.content_generator.content_generator_agent import ContentGeneratorAgent
from src.models.task import Task, TaskStatus as PythonTaskStatus

# Minimal config for the agent during tests
TEST_AGENT_CONFIG = {
    "agent_name": "test_content_generator",
    "description": "Test description",
    "goal": "Test goal",
    "llm_config": {"model_name": "gemini-1.5-flash-001"}, # Mock LLM, actual model won't be hit
    "instruction": "Base instruction.",
    "min_word_count": 10,
    "max_word_count": 100,
    "max_title_length": 10,
    "max_meta_description_length": 20,
    "default_template_id": "test_default_template"
}

# Sample Task Pydantic model for testing
SAMPLE_TASK = Task(
    task_id="test_service_12345",
    service_id="test_service",
    zip="12345",
    city="Testville",
    state="TS",
    status=PythonTaskStatus.IN_PROGRESS # Status when content gen would run
)

class TestContentGeneratorAgent(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        # Mock the config loading within the agent's __init__
        with patch('ai_agents.shared.base_agent.BaseAgent._load_config_from_yaml', return_value=TEST_AGENT_CONFIG):
            with patch('ai_agents.shared.base_agent.BaseAgent.initialize_llm_and_runner'): # Prevent actual LLM init
                self.agent = ContentGeneratorAgent(config_path="dummy_config.yaml")
        
        # Mock the logger within the agent instance to inspect log calls if needed
        self.agent.logger = MagicMock()

    # --- Test Helper Data Loading Methods ---

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_load_template_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn # For 'with' statement
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor # For 'with' statement
        
        expected_template_data = {"template_id": "test_tpl", "sections": [{"id": "intro"}]}
        mock_cursor.fetchone.return_value = {'template_data': expected_template_data}
        
        template_data = self.agent._load_template("test_tpl")
        
        self.assertEqual(template_data, expected_template_data)
        mock_cursor.execute.assert_called_once_with(
            "SELECT template_data FROM content_templates WHERE template_id = %s;", ("test_tpl",)
        )

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_load_template_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None # Simulate template not found
        
        default_fallback_template = self.agent._get_default_template()
        template_data = self.agent._load_template("non_existent_tpl")
        
        self.assertEqual(template_data, default_fallback_template)
        self.agent.logger.warning.assert_any_call("Template non_existent_tpl not found in DB. Using default.")

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection', side_effect=psycopg2.Error("DB connection error"))
    def test_load_template_db_error_connect(self, mock_get_conn_error):
        # This test covers when get_db_connection itself fails or returns None from the start
        # as the context manager will try to use it.
        # We need get_db_connection() to return a context manager that produces None
        mock_get_conn_error.return_value.__enter__.return_value = None

        default_fallback_template = self.agent._get_default_template()
        template_data = self.agent._load_template("any_tpl")
        self.assertEqual(template_data, default_fallback_template)
        self.agent.logger.error.assert_any_call("Failed to get DB connection for template any_tpl.")


    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_load_template_db_error_execute(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB execute error")

        default_fallback_template = self.agent._get_default_template()
        template_data = self.agent._load_template("any_tpl")

        self.assertEqual(template_data, default_fallback_template)
        self.agent.logger.error.assert_any_call("DB error loading template any_tpl: DB execute error")


    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_get_seo_research_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_seo_data = {
            "primary_keywords": ["kw1", "kw2"], 
            "secondary_keywords": ["skw1"],
            "competitor_analysis": {"url": "test.com"},
            "seo_recommendations": "Do this"
        }
        mock_cursor.fetchone.return_value = expected_seo_data # DB returns a dict-like row
        
        seo_data = self.agent._get_seo_research_data("task1")
        self.assertEqual(seo_data, expected_seo_data)
        mock_cursor.execute.assert_called_once()
        self.assertIn("SELECT primary_keywords, secondary_keywords, competitor_analysis, seo_recommendations", mock_cursor.execute.call_args[0][0])

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_get_location_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_loc_data = {"zip_code": "12345", "city": "Testville", "state": "TS"}
        mock_cursor.fetchone.return_value = expected_loc_data
        
        loc_data = self.agent._get_location_data("12345")
        self.assertEqual(loc_data, expected_loc_data)

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection')
    def test_get_service_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_srv_data = {"service_id": "plumber", "display_name": "Plumber Pro"}
        mock_cursor.fetchone.return_value = expected_srv_data
        
        srv_data = self.agent._get_service_data("plumber")
        self.assertEqual(srv_data, expected_srv_data)

    # --- Test _save_generated_content (indirectly via process_task) ---
    # Direct test would require making it non-private or using name mangling.

    # --- Test process_task ---
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._save_generated_content')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_service_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_location_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_seo_research_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._load_template')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock) # Mock the LLM runner
    async def test_process_task_successful_run(self, mock_run_async, mock_load_template, 
                                         mock_get_seo, mock_get_loc, mock_get_service, 
                                         mock_save_content):
        # Setup mocks for helper methods
        mock_load_template.return_value = {"template_id": "tpl1", "template_name": "Test Template", "sections": [{"id": "s1", "instructions": "instr1"}]}
        mock_get_seo.return_value = {"primary_keywords": ["pk"], "secondary_keywords": ["sk"]}
        mock_get_loc.return_value = {"city": "Testville", "state": "TS"} # SAMPLE_TASK already has city/state
        mock_get_service.return_value = {"display_name": "Test Service Pro", "description": "A service", "keywords": ["base_kw"]}
        mock_save_content.return_value = True # Simulate successful save

        # Mock LLM response
        # Construct a mock ADK event that mimics a final response with content
        mock_llm_output_json = {"title": "Generated Title", "body": "Generated body content."}
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        # Simulate text output that contains JSON block
        mock_final_event.content.parts = [MagicMock(text=f"Some text around ```json\n{json.dumps(mock_llm_output_json)}\n```")]
        
        # Make run_async an async generator
        async def async_generator_mock(*args, **kwargs):
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock() # Replace the actual runner with a MagicMock
        self.agent.runner.run_async = mock_run_async # Attach the async mock to it


        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "completed")
        self.assertIn("Content generated and saved", result["message"])
        
        mock_load_template.assert_called_once()
        mock_get_seo.assert_called_once_with(SAMPLE_TASK.task_id)
        # _get_location_data and _get_service_data are called with zip and service_id from Task
        mock_get_loc.assert_called_once_with(SAMPLE_TASK.zip)
        mock_get_service.assert_called_once_with(SAMPLE_TASK.service_id)
        
        mock_run_async.assert_called_once() # Check LLM was called
        
        # Check that _save_generated_content was called
        mock_save_content.assert_called_once()
        args_save, _ = mock_save_content.call_args
        self.assertEqual(args_save[0], SAMPLE_TASK.task_id) # task_id
        self.assertEqual(args_save[1], mock_llm_output_json) # content_data
        # self.assertIsInstance(args_save[2], int) # word_count - can be more specific if needed

    @patch('ai_agents.content_generator.content_generator_agent.get_db_connection') # For _save_generated_content's attempt
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_service_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_location_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_seo_research_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._load_template')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_save_failure(self, mock_run_async, mock_load_template, 
                                       mock_get_seo, mock_get_loc, mock_get_service,
                                       mock_get_db_conn_for_save): # Mocks _save_generated_content's DB call
        # Setup mocks for successful data loading and LLM response
        mock_load_template.return_value = {"template_id": "tpl1", "template_name": "Test Template"}
        mock_get_seo.return_value = {"primary_keywords": ["pk"]}
        mock_get_loc.return_value = {"city": "Testville", "state": "TS"}
        mock_get_service.return_value = {"display_name": "Test Service Pro"}

        mock_llm_output_json = {"title": "Generated Title", "body": "Generated body content."}
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=f"```json\n{json.dumps(mock_llm_output_json)}\n```")]
        
        async def async_generator_mock(*args, **kwargs):
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async
        
        # Mock DB connection for _save_generated_content to fail
        mock_conn_save = MagicMock()
        mock_cursor_save = MagicMock()
        mock_get_db_conn_for_save.return_value.__enter__.return_value = mock_conn_save
        mock_conn_save.cursor.return_value.__enter__.return_value = mock_cursor_save
        mock_cursor_save.execute.side_effect = psycopg2.Error("DB error during save")

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "error")
        self.assertIn("Failed to save generated content to DB", result["message"])
        mock_conn_save.rollback.assert_called_once() # Check rollback was called on save failure

    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._save_generated_content') # Mock out save
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_service_data', return_value=None) # Simulate service data not found
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_location_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._get_seo_research_data')
    @patch('ai_agents.content_generator.content_generator_agent.ContentGeneratorAgent._load_template')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_critical_data_load_failure(self, mock_run_async, mock_load_template, 
                                                     mock_get_seo, mock_get_loc, 
                                                     mock_get_service_fail, mock_save_content):
        # Setup some mocks to return valid data, but one critical one (service_data) returns None
        mock_load_template.return_value = {"template_id": "tpl1", "template_name": "Test Template"}
        mock_get_seo.return_value = {"primary_keywords": ["pk"]}
        mock_get_loc.return_value = {"city": "Testville", "state": "TS"}
        # mock_get_service_fail is already set to return_value=None by @patch decorator

        # LLM should still be called, but prompt might be affected
        mock_llm_output_json = {"title": "Generated Title (with missing service info)", "body": "Content."}
        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=f"```json\n{json.dumps(mock_llm_output_json)}\n```")]
        
        async def async_generator_mock(*args, **kwargs):
            yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async
        mock_save_content.return_value = True # Assume save would work if LLM part completes

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "completed") # Task might still complete with warnings
        self.agent.logger.warning.assert_any_call(f"Service display name not found for {SAMPLE_TASK.service_id}. Using ID.")
        # Prompt to LLM would use service_id instead of display_name
        # Check that save was called, showing process continued
        mock_save_content.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)

```
