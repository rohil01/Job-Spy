"""
Test script for AIJobAgent
"""
import sys
from pathlib import Path

# Add the src directory to the path so we can import the agent
sys.path.insert(0, str(Path(__file__).parent / "src"))

from Agent.ai_job_agent import AIJobAgent

def test_string_matching_fallback():
    """Test that the agent falls back to string matching when AI is not available"""
    print("Testing string matching fallback...")

    # Create agent with no AI provider (should fall back to string matching)
    agent = AIJobAgent({'ai_provider': None})

    # Test data
    jobs = [
        {
            'title': 'Software Engineer',
            'description': 'Looking for a skilled Python developer with experience in Django and AWS',
            'experience_level': 'Mid-Senior level'
        },
        {
            'title': 'Data Scientist',
            'description': 'We need a data scientist familiar with machine learning, Python, and SQL',
            'experience_level': 'Entry level'
        },
        {
            'title': 'Product Manager',
            'description': 'Seeking a product manager with experience in agile methodologies',
            'experience_level': 'Director'
        }
    ]

    # Test experience level filtering
    experience_levels = ['Mid-Senior level', 'Entry level']
    filtered_jobs = agent.filter_by_experience_level(jobs, experience_levels)
    print(f"Filtered jobs by experience level: {len(filtered_jobs)} jobs")
    for job in filtered_jobs:
        print(f"  - {job['title']} ({job['experience_level']})")

    # Test resume matching
    resume_skills = ['Python', 'Django', 'AWS']
    matched_jobs = agent.match_resume(jobs, resume_skills)
    print(f"Matched jobs by resume skills: {len(matched_jobs)} jobs")
    for job in matched_jobs:
        print(f"  - {job['title']}")

    print("String matching fallback test completed.\n")

def test_with_nvidia_config():
    """Test the agent with NVIDIA configuration (will fall back to string matching if API fails)"""
    print("Testing with NVIDIA configuration...")

    # Create agent with NVIDIA provider (from config.py)
    agent = AIJobAgent()

    print(f"AI Provider: {agent.ai_provider}")
    print(f"AI Model: {agent.ai_model}")
    print(f"API Key set: {bool(agent.api_key)}")
    print(f"AI Client initialized: {agent._ai_client is not None}")

    # Test data
    jobs = [
        {
            'title': 'Software Engineer',
            'description': 'Looking for a skilled Python developer with experience in Django and AWS',
            'experience_level': 'Mid-Senior level'
        },
        {
            'title': 'Data Scientist',
            'description': 'We need a data scientist familiar with machine learning, Python, and SQL',
            'experience_level': 'Entry level'
        }
    ]

    # Test experience level filtering (should still use string matching)
    experience_levels = ['Mid-Senior level']
    filtered_jobs = agent.filter_by_experience_level(jobs, experience_levels)
    print(f"Filtered jobs by experience level: {len(filtered_jobs)} jobs")

    # Test resume matching (will fall back to string matching if AI fails)
    resume_skills = ['Python', 'Machine Learning']
    matched_jobs = agent.match_resume(jobs, resume_skills)
    print(f"Matched jobs by resume skills: {len(matched_jobs)} jobs")
    for job in matched_jobs:
        print(f"  - {job['title']}")

    print("NVIDIA configuration test completed.\n")

if __name__ == "__main__":
    test_string_matching_fallback()
    test_with_nvidia_config()
    print("All tests completed!")