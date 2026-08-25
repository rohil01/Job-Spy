"""Unit tests for the job scraper module."""
from unittest.mock import Mock, patch
import pytest
import pandas as pd
from src.scraper.scraper import scrape_jobs_from_sites, scrape_jobs_simple


class TestScraper:
    """Test cases for the job scraper."""

    @patch('src.scraper.scraper.JOBSNIFFER_AVAILABLE', False)
    def test_scrape_jobs_from_sites_raises_import_error_when_jobsniffer_missing(self):
        """Test that scrape_jobs_from_sites raises ImportError when jobsniffer is not installed."""
        with pytest.raises(ImportError, match="jobsniffer is not installed"):
            scrape_jobs_from_sites(
                site_name="indeed",
                search_term="software engineer",
                location="Bengaluru"
            )

    @patch('src.scraper.scraper.scrape_jobs')
    def test_scrape_jobs_from_sites_returns_dataframe(self, mock_scrape_jobs):
        """Test that scrape_jobs_from_sites returns a pandas DataFrame."""
        # Mock the jobsniffer response
        mock_df = Mock(spec=pd.DataFrame)
        mock_df.empty = False
        mock_scrape_jobs.return_value = mock_df

        result = scrape_jobs_from_sites(
            site_name=["indeed", "linkedin"],
            search_term="AI Developer",
            location="Bengaluru",
            results_wanted=10
        )

        # Verify the function was called with correct parameters
        mock_scrape_jobs.assert_called_once()
        call_args = mock_scrape_jobs.call_args[1]  # Get keyword arguments

        assert call_args['site_name'] == ["indeed", "linkedin"]
        assert call_args['search_term'] == "AI Developer"
        assert call_args['location'] == "Bengaluru"
        assert call_args['results_wanted'] == 10

        # Verify we got a DataFrame back
        assert result == mock_df

    @patch('src.scraper.scraper.scrape_jobs')
    def test_scrape_jobs_from_sites_handles_optional_parameters(self, mock_scrape_jobs):
        """Test that scrape_jobs_from_sites correctly handles optional parameters."""
        mock_df = Mock(spec=pd.DataFrame)
        mock_df.empty = False
        mock_scrape_jobs.return_value = mock_df

        scrape_jobs_from_sites(
            site_name="indeed",
            search_term="data scientist",
            location="Remote",
            results_wanted=5,
            hours_old=24,
            country_indeed="india",
            linkedin_fetch_description=True,
            proxies=["http://proxy1:8080"],
            distance=25,
            is_remote=True,
            easy_apply=True,
            description_format="html",
            google_search_term="data scientist remote",
            employment_type="PERMANENT"
        )

        call_args = mock_scrape_jobs.call_args[1]

        assert call_args['hours_old'] == 24
        assert call_args['country_indeed'] == "india"
        assert call_args['linkedin_fetch_description'] is True
        assert call_args['proxies'] == ["http://proxy1:8080"]
        assert call_args['distance'] == 25
        assert call_args['is_remote'] is True
        assert call_args['easy_apply'] is True
        assert call_args['description_format'] == "html"
        assert call_args['google_search_term'] == "data scientist remote"
        assert call_args['employment_type'] == "PERMANENT"

    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_jobs_simple_calls_scrape_jobs_from_sites(self, mock_scrape_jobs_from_sites):
        """Test that scrape_jobs_simple calls scrape_jobs_from_sites with correct parameters."""
        mock_df = Mock(spec=pd.DataFrame)
        mock_df.empty = False
        mock_scrape_jobs_from_sites.return_value = mock_df

        result = scrape_jobs_simple(
            site_name=["indeed", "linkedin"],
            search_term="software engineer",
            location="Bengaluru",
            results_wanted=15
        )

        # Verify scrape_jobs_from_sites was called
        mock_scrape_jobs_from_sites.assert_called_once()
        call_args = mock_scrape_jobs_from_sites.call_args[1]

        # Verify the parameters passed to scrape_jobs_from_sites
        assert call_args['site_name'] == ["indeed", "linkedin"]
        assert call_args['search_term'] == "software engineer"
        assert call_args['location'] == "Bengaluru"
        assert call_args['results_wanted'] == 15
        assert call_args['hours_old'] == 24  # Default for simple interface
        assert call_args['linkedin_fetch_description'] is True  # Default for simple interface

        assert result == mock_df

    def test_scraper_functions_have_correct_signatures(self):
        """Test that scraper functions have the expected signatures."""
        import inspect

        # Check scrape_jobs_from_sites signature
        sig = inspect.signature(scrape_jobs_from_sites)
        params = sig.parameters
        assert 'site_name' in params
        assert 'search_term' in params
        assert 'location' in params
        assert 'results_wanted' in params
        assert params['results_wanted'].default == 15
        assert params['hours_old'].default == 72

        # Check scrape_jobs_simple signature
        sig = inspect.signature(scrape_jobs_simple)
        params = sig.parameters
        assert 'site_name' in params
        assert 'search_term' in params
        assert 'location' in params
        assert 'results_wanted' in params
        assert params['results_wanted'].default == 10