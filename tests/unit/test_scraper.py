"""Unit tests for the job scraper module."""
import json
from unittest.mock import Mock, patch
import pytest
import pandas as pd
from src.scraper.scraper import scrape_jobs_from_sites, scrape_jobs_simple, JobScraper


def _mock_df(records):
    df = Mock()
    df.empty = len(records) == 0
    df.to_dict.return_value = records
    return df


_SCRAPER_CONFIG = {
    "sites": ["indeed"],
    "search_terms": ["term-a", "term-b"],
    "location": "Bengaluru",
    "results_wanted": 5,
    "hours_old": 6,
    "country_indeed": "india",
    "linkedin_fetch_description": False,
    "scrape_cooldown_minutes": 0,
    "scraped_jobs_path": "data/scraped_jobs.json",
}


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


class TestJobScraper:
    """Tests for the config-driven JobScraper class."""

    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_iterates_terms_and_dedups(self, mock_scrape):
        # Both terms return the same job_url -> should dedupe to one.
        mock_scrape.side_effect = [
            _mock_df([{"job_url": "u1", "title": "A"}]),
            _mock_df([{"job_url": "u1", "title": "A"}, {"job_url": "u2", "title": "B"}]),
        ]
        scraper = JobScraper(config=dict(_SCRAPER_CONFIG))
        jobs = scraper.scrape()

        assert mock_scrape.call_count == 2
        # Forwarded params come from config.
        _, kwargs = mock_scrape.call_args_list[0]
        assert kwargs["site_name"] == ["indeed"]
        assert kwargs["results_wanted"] == 5
        assert kwargs["hours_old"] == 6
        # u1 deduplicated across the two terms.
        assert len(jobs) == 2

    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_survives_a_failing_term(self, mock_scrape):
        mock_scrape.side_effect = [
            RuntimeError("boom"),
            _mock_df([{"job_url": "u2", "title": "B"}]),
        ]
        scraper = JobScraper(config=dict(_SCRAPER_CONFIG))
        jobs = scraper.scrape()
        assert len(jobs) == 1  # first term failed, second succeeded

    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_and_save_writes_json(self, mock_scrape, tmp_path):
        mock_scrape.side_effect = [
            _mock_df([{"job_url": "u1", "title": "A"}]),
            _mock_df([{"job_url": "u2", "title": "B"}]),
        ]
        out = tmp_path / "jobs.json"
        scraper = JobScraper(config=dict(_SCRAPER_CONFIG))
        jobs = scraper.scrape_and_save(output_path=out)

        assert out.exists()
        saved = json.loads(out.read_text(encoding="utf-8"))
        assert len(saved) == len(jobs) == 2

    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_reports_progress_per_term(self, mock_scrape):
        mock_scrape.side_effect = [
            _mock_df([{"job_url": "u1", "title": "A"}]),
            _mock_df([{"job_url": "u2", "title": "B"}]),
        ]
        calls = []
        scraper = JobScraper(config=dict(_SCRAPER_CONFIG))
        scraper.scrape(progress_callback=lambda done, total, msg: calls.append((done, total)))

        # total is always the number of search terms (2); completion reaches 2/2.
        assert all(total == 2 for _, total in calls)
        assert calls[-1] == (2, 2)
        assert (0, 2) in calls  # reported before the first term, too

    @patch('pipeline.utils.cooldown_sleep')
    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_cooldown_runs_between_terms_only(self, mock_scrape, mock_cooldown):
        mock_scrape.side_effect = [
            _mock_df([{"job_url": "u1"}]),
            _mock_df([{"job_url": "u2"}]),
        ]
        config = dict(_SCRAPER_CONFIG, scrape_cooldown_minutes=0.5)
        JobScraper(config=config).scrape()

        # Two terms -> exactly one cooldown (never after the last term).
        mock_cooldown.assert_called_once()
        assert mock_cooldown.call_args.args[0] == 0.5

    @patch('pipeline.utils.cooldown_sleep')
    @patch('src.scraper.scraper.scrape_jobs_from_sites')
    def test_scrape_zero_cooldown_never_sleeps(self, mock_scrape, mock_cooldown):
        mock_scrape.side_effect = [_mock_df([{"job_url": "u1"}]), _mock_df([{"job_url": "u2"}])]
        JobScraper(config=dict(_SCRAPER_CONFIG)).scrape()  # cooldown is 0
        mock_cooldown.assert_not_called()


class TestCooldownSleep:
    """The cooldown helper must accept fractional minutes (0.5 = 30s)."""

    @patch('pipeline.utils.time.sleep')
    def test_fractional_minutes_convert_to_seconds(self, mock_sleep):
        import logging
        from pipeline.utils import cooldown_sleep

        cooldown_sleep(0.5, logging.getLogger("test"))
        mock_sleep.assert_called_once_with(30.0)

    @patch('pipeline.utils.time.sleep')
    def test_zero_is_a_noop(self, mock_sleep):
        import logging
        from pipeline.utils import cooldown_sleep

        cooldown_sleep(0, logging.getLogger("test"))
        mock_sleep.assert_not_called()