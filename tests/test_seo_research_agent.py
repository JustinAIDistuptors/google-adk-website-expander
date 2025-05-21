import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
import json
from datetime import datetime
import psycopg2 # For psycopg2.Error

# Add project root to sys.path to allow direct import of src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_agents.seo_research.seo_research_agent import SeoResearchAgent
from src.models.task import Task, TaskStatus as PythonTaskStatus

# Minimal config for the agent during tests
TEST_AGENT_CONFIG = {
    "agent_name": "test_seo_research",
    "description": "Test SEO description",
    "goal": "Test SEO goal",
    "llm_config": {"model_name": "gemini-1.5-flash-001"}, # Mock LLM
    "instruction": "Base instruction for SEO research.", # Will be appended to in initialize_agent
    "max_competitor_pages": 3,
    "max_keywords_per_page": 10
}

TEST_SEO_PARAMS_CONFIG = { # Loaded by _load_seo_parameters
    'seo_targets': {'min_keyword_density': 1.0},
    'keyword_strategies': {'primary_keyword_count': 1}
}

# Sample Task Pydantic model for testing
SAMPLE_TASK = Task(
    task_id="test_seo_srv_zip1",
    service_id="test_seo_srv",
    zip="zip1",
    city="SEOCity",
    state="SO",
    status=PythonTaskStatus.PENDING # Status when SEO research would run
)

SAMPLE_LLM_SEO_RESPONSE_DICT = {
    "keywords": {
        "primary": ["seo keyword 1", "local seo"],
        "secondary": ["seo service city", "best seo company near me"],
        "long_tail": ["how to do local seo for small business"]
    },
    "competitor_analysis": {
        "top_competitors": [{"url": "competitor1.com", "title": "Competitor 1"}],
        "common_themes": ["Local presence", "Reviews"]
    },
    "content_strategy": {"recommended_headings": ["H1: SEO Service", "H2: Why Local SEO?"], "word_count_target": 600},
    "metadata_templates": {"title": "Best SEO Service in {city}", "meta_description": "Get top SEO services."},
    "local_relevance_factors": ["Mention landmarks"],
    "schema_markup_recommendations": ["LocalBusiness"],
    "seo_summary_text": "This is a comprehensive SEO strategy for the target."
}

class TestSeoResearchAgent(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        with patch('ai_agents.shared.base_agent.BaseAgent._load_config_from_yaml', return_value=TEST_AGENT_CONFIG):
            with patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._load_seo_parameters', return_value=TEST_SEO_PARAMS_CONFIG):
                with patch('ai_agents.shared.base_agent.BaseAgent.initialize_llm_and_runner'): 
                    with patch('ai_agents.seo_research.seo_research_agent.create_serp_analysis_tool') as mock_serp_tool, \
                         patch('ai_agents.seo_research.seo_research_agent.create_keyword_generation_tool') as mock_kw_tool, \
                         patch('ai_agents.seo_research.seo_research_agent.create_content_analysis_tool') as mock_content_tool:
                        
                        mock_serp_tool.return_value = MagicMock()
                        mock_kw_tool.return_value = MagicMock()
                        mock_content_tool.return_value = MagicMock()
                        
                        self.agent = SeoResearchAgent(config_path="dummy_config.yaml")
        
        self.agent.logger = MagicMock()

    # --- Test Helper Data Loading Methods ---
    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection')
    def test_get_location_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_loc_data = {"city": "SEOCity", "state": "SO", "latitude": 1.0, "longitude": 1.0}
        mock_cursor.fetchone.return_value = expected_loc_data
        
        loc_data = self.agent._get_location_data(SAMPLE_TASK.zip)
        self.assertEqual(loc_data, expected_loc_data)
        mock_cursor.execute.assert_called_once_with(
            "SELECT city, state, latitude, longitude FROM locations WHERE zip_code = %s;", (SAMPLE_TASK.zip,)
        )

    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection')
    def test_get_location_data_not_found(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        
        loc_data = self.agent._get_location_data("unknown_zip")
        self.assertIsNone(loc_data)
        self.agent.logger.warning.assert_any_call("Location data not found for zip code unknown_zip.")

    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection', side_effect=psycopg2.Error("DB connection error"))
    def test_get_location_data_db_error_connect(self, mock_get_conn_error):
        mock_get_conn_error.return_value.__enter__.return_value = None 
        loc_data = self.agent._get_location_data("any_zip")
        self.assertIsNone(loc_data)
        self.agent.logger.error.assert_any_call("Failed to get DB connection for location data (zip any_zip).")

    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection')
    def test_get_service_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        expected_srv_data = {"display_name": "SEO Pro Service", "description": "Best SEO", "keywords": ["kw1", "kw2"]}
        mock_cursor.fetchone.return_value = expected_srv_data
        
        srv_data = self.agent._get_service_data(SAMPLE_TASK.service_id)
        self.assertEqual(srv_data, expected_srv_data)
        mock_cursor.execute.assert_called_once_with(
            "SELECT display_name, description, keywords FROM services WHERE service_id = %s;", (SAMPLE_TASK.service_id,)
        )

    # --- Test _save_seo_research_data (directly, as it's a critical part of the refactor) ---
    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection')
    def test_save_seo_research_data_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        task_id = "task123"
        pk = ["p_kw1"]
        sk = ["s_kw1"]
        ca = {"comp": "data"}
        sr = "recommendations text"

        success = self.agent._save_seo_research_data(task_id, pk, sk, ca, sr)

        self.assertTrue(success)
        mock_cursor.execute.assert_called_once()
        args, _ = mock_cursor.execute.call_args
        self.assertIn("INSERT INTO seo_research_data", args[0]) # Check query type
        # Check parameters passed to execute matches expected values and order
        self.assertEqual(args[1][0], task_id)
        self.assertEqual(args[1][1], pk)
        self.assertEqual(args[1][2], sk)
        self.assertEqual(args[1][3], json.dumps(ca)) # Competitor analysis as JSON string
        self.assertEqual(args[1][4], sr)
        self.assertIsInstance(args[1][5], datetime) # created_at
        self.assertIsInstance(args[1][6], datetime) # updated_at
        mock_conn.commit.assert_called_once()

    @patch('ai_agents.seo_research.seo_research_agent.get_db_connection')
    def test_save_seo_research_data_db_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.Error("DB save error")

        success = self.agent._save_seo_research_data("t1", [], [], {}, "")
        self.assertFalse(success)
        mock_conn.rollback.assert_called_once()


    # --- Test process_task ---
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._save_seo_research_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_service_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_location_data')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock) 
    async def test_process_task_successful_run(self, mock_run_async, mock_get_loc, 
                                         mock_get_service, mock_save_seo_data_method):
        mock_get_loc.return_value = {"city": "SEOCity", "state": "SO"} 
        mock_get_service.return_value = {"display_name": "SEO Pro", "description": "Desc", "keywords": ["base_kw"]}
        mock_save_seo_data_method.return_value = True

        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=f"```json\n{json.dumps(SAMPLE_LLM_SEO_RESPONSE_DICT)}\n```")]
        
        async def async_generator_mock(*args, **kwargs): yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock() 
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "completed")
        self.assertIn("SEO research completed and data saved to DB.", result["message"])
        mock_run_async.assert_called_once()
        
        mock_save_seo_data_method.assert_called_once_with(
            SAMPLE_TASK.task_id,
            SAMPLE_LLM_SEO_RESPONSE_DICT["keywords"]["primary"],
            SAMPLE_LLM_SEO_RESPONSE_DICT["keywords"]["secondary"],
            SAMPLE_LLM_SEO_RESPONSE_DICT["competitor_analysis"],
            SAMPLE_LLM_SEO_RESPONSE_DICT["seo_summary_text"]
        )

    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._save_seo_research_data', return_value=False) # Mock save to fail
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_service_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_location_data')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_save_failure_after_llm(self, mock_run_async, mock_get_loc, 
                                                 mock_get_service, mock_save_seo_data_fails):
        mock_get_loc.return_value = {"city": "SEOCity", "state": "SO"}
        mock_get_service.return_value = {"display_name": "SEO Pro"}

        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=f"```json\n{json.dumps(SAMPLE_LLM_SEO_RESPONSE_DICT)}\n```")]
        
        async def async_generator_mock(*args, **kwargs): yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "error")
        self.assertIn("SEO research completed but failed to save data to DB.", result["message"])
        mock_save_seo_data_fails.assert_called_once() # Ensure it was called

    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._save_seo_research_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_service_data', return_value=None) 
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_location_data', return_value=None)
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_data_load_failures(self, mock_run_async, mock_get_loc_fail, 
                                              mock_get_service_fail, mock_save_seo_data):
        # Both location and service data are None
        mock_save_seo_data.return_value = True # Assume save would work if LLM provides data

        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text=f"```json\n{json.dumps(SAMPLE_LLM_SEO_RESPONSE_DICT)}\n```")]
        
        async def async_generator_mock(*args, **kwargs): yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async
        
        result = await self.agent.process_task(SAMPLE_TASK)

        self.assertEqual(result["status"], "completed") # Still completes as LLM might work with defaults
        self.agent.logger.warning.assert_any_call(f"City/State information missing for task {SAMPLE_TASK.task_id}. SEO research might be less effective.")
        mock_save_seo_data.assert_called_once() # Check that it still tries to save

    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._save_seo_research_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_service_data')
    @patch('ai_agents.seo_research.seo_research_agent.SeoResearchAgent._get_location_data')
    @patch('google.adk. Obrigado.run_async', new_callable=AsyncMock)
    async def test_process_task_llm_returns_non_json(self, mock_run_async, mock_get_loc, 
                                               mock_get_service, mock_save_seo_data):
        mock_get_loc.return_value = {"city": "SEOCity"}
        mock_get_service.return_value = {"display_name": "SEO Pro"}
        mock_save_seo_data.return_value = True

        mock_final_event = MagicMock()
        mock_final_event.is_final_response.return_value = True
        mock_final_event.content = MagicMock()
        mock_final_event.content.parts = [MagicMock(text="This is just plain text, not JSON.")]
        
        async def async_generator_mock(*args, **kwargs): yield mock_final_event
        mock_run_async.side_effect = async_generator_mock
        self.agent.runner = MagicMock()
        self.agent.runner.run_async = mock_run_async

        result = await self.agent.process_task(SAMPLE_TASK)
        
        self.assertEqual(result["status"], "completed") # Completes by saving raw text
        self.agent.logger.error.assert_any_call(unittest.mock.ANY, exc_info=False) # JSON parsing error
        
        mock_save_seo_data.assert_called_once()
        args_save, _ = mock_save_seo_data.call_args
        self.assertEqual(args_save[4], "This is just plain text, not JSON.") # seo_recommendations gets raw text


if __name__ == '__main__':
    unittest.main(verbosity=2)
```
