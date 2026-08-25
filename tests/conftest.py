"""Shared test fixtures for jobspy test suite."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return [
        {
            "id": "1",
            "site": "indeed",
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "Bengaluru, India",
            "date_posted": "2024-01-15",
            "job_type": "Full-time",
            "experience_level": "Mid-Senior level",
            "description": "Looking for a skilled Python developer with experience in Django and AWS",
            "skills": ["Python", "Django", "AWS"],
            "job_url": "https://indeed.com/viewjob?jk=12345"
        },
        {
            "id": "2",
            "site": "linkedin",
            "title": "Data Scientist",
            "company": "Data Inc",
            "location": "Remote",
            "date_posted": "2024-01-10",
            "job_type": "Full-time",
            "experience_level": "Entry level",
            "description": "We need a data scientist familiar with machine learning, Python, and SQL",
            "skills": ["Python", "Machine Learning", "SQL"],
            "job_url": "https://linkedin.com/jobs/view/67890"
        },
        {
            "id": "3",
            "site": "glassdoor",
            "title": "Product Manager",
            "company": "Product Co",
            "location": "New York, NY",
            "date_posted": "2024-01-05",
            "job_type": "Full-time",
            "experience_level": "Director",
            "description": "Seeking a product manager with experience in agile methodologies",
            "skills": ["Product Management", "Agile", "Scrum"],
            "job_url": "https://glassdoor.com/job listing/123"
        }
    ]


@pytest.fixture
def sample_resume_skills():
    """Sample resume skills for testing."""
    return ["Python", "Django", "AWS", "Machine Learning", "SQL"]


@pytest.fixture
def sample_experience_levels():
    """Sample experience levels for testing."""
    return ["Entry level", "Mid-Senior level"]


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary directory for test data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_jobs_file(temp_data_dir, sample_job_data):
    """Create a sample jobs JSON file."""
    jobs_file = temp_data_dir / "jobs.json"
    with open(jobs_file, "w") as f:
        json.dump(sample_job_data, f, indent=2)
    return jobs_file