"""Integration tests for jobspy pipeline."""
import json
from unittest.mock import Mock, patch
import pytest
from pipeline.scraper_runner import scrape_pipeline
from pipeline.ai_filter_step import run_ai_filter


class TestPipelineIntegration:
    """Integration tests for the pipeline components."""

    @patch('scraper.scraper.JobScraper')
    def test_scrape_pipeline_success(self, mock_scraper_class):
        """scrape_pipeline delegates to JobScraper().scrape_and_save()."""
        mock_scraper = Mock()
        mock_scraper.scrape_and_save.return_value = [
            {
                "id": "1",
                "title": "Software Engineer",
                "company": "Tech Corp",
                "location": "Bengaluru",
                "date_posted": "2024-01-15",
                "description": "Python developer role",
                "experience_level": "Mid-Senior level",
            }
        ]
        mock_scraper_class.return_value = mock_scraper

        result = scrape_pipeline()

        mock_scraper_class.assert_called_once()
        mock_scraper.scrape_and_save.assert_called_once()
        assert result == mock_scraper.scrape_and_save.return_value

    @patch('pipeline.ai_filter_step.AIJobAgent')
    def test_run_ai_filter_success(self, mock_ai_agent_class):
        """Test AI filter step with mocked agent."""
        # Mock AI agent
        mock_agent = Mock()
        mock_agent.filter_by_experience_years.return_value = [
            {"id": "1", "title": "Software Engineer", "required_years": {"min": 3, "max": 5}}
        ]
        mock_ai_agent_class.return_value = mock_agent

        # Test data
        jobs = [{"id": "1", "title": "Software Engineer"}]

        # Mock output path
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "filtered_jobs.json")

            # This would normally save a file, but we're testing the function call
            result = run_ai_filter(jobs, 0, 3, output_path)

            # Verify the AI agent was called correctly
            mock_ai_agent_class.assert_called_once()
            mock_agent.filter_by_experience_years.assert_called_once_with(jobs, 0, 3)
            assert isinstance(result, list)

    def test_pipeline_components_import(self):
        """Test that pipeline components can be imported."""
        from pipeline.scraper_runner import scrape_pipeline
        from pipeline.ai_filter_step import run_ai_filter
        from pipeline.utils import setup_logger, make_json_safe, deduplicate_jobs

        assert scrape_pipeline is not None
        assert run_ai_filter is not None
        assert setup_logger is not None
        assert make_json_safe is not None
        assert deduplicate_jobs is not None