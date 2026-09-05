"""Unit tests for the rewritten AIJobAgent (experience / suitability / tailor)."""
from unittest.mock import Mock, patch

import pytest

from Agent.ai_job_agent import AIJobAgent


def _make_response(content: str) -> Mock:
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = content
    return response


def _agent_with_replies(*contents: str) -> AIJobAgent:
    """Agent whose chat client returns the given contents in order."""
    agent = AIJobAgent({'ai_provider': None})  # no real client created
    agent.ai_model = 'test-model'
    client = Mock()
    client.chat.completions.create.side_effect = [_make_response(c) for c in contents]
    agent._ai_client = client
    return agent


class TestInit:
    def test_init_does_not_crash_without_ai(self):
        """Regression: __init__ used to read self.api_key before assigning it."""
        agent = AIJobAgent({'ai_provider': None})
        assert agent._ai_client is None

    def test_init_with_config(self):
        agent = AIJobAgent({'ai_provider': None, 'ai_model': 'gpt-4'})
        assert agent.ai_model == 'gpt-4'

    def test_load_default_config_returns_dict(self):
        agent = AIJobAgent({'ai_provider': None})
        result = agent._load_default_config()
        assert isinstance(result, dict)
        assert 'ai_model' in result  # comes from config.load_config()

    @patch('openai.OpenAI')
    def test_initialize_nvidia_client(self, mock_openai):
        mock_openai.return_value = Mock()
        agent = AIJobAgent({
            'ai_provider': 'nvidia',
            'ai_model': 'm',
            'api_key': 'key',
            'ai_base_url': 'https://custom/v1',
        })
        mock_openai.assert_called_once_with(api_key='key', base_url='https://custom/v1')
        assert agent._ai_client is not None

    def test_initialize_client_failure_falls_back_to_none(self):
        with patch('openai.OpenAI', side_effect=Exception('bad key')):
            agent = AIJobAgent({'ai_provider': 'openai', 'ai_model': 'm', 'api_key': 'x'})
            assert agent._ai_client is None


class TestExperienceFilter:
    def test_none_window_returns_all(self):
        agent = AIJobAgent({'ai_provider': None})
        jobs = [{'title': 'X', 'description': 'Y'}]
        assert agent.filter_by_experience_years(jobs, None, None) == jobs

    def test_requires_client_when_window_given(self):
        agent = AIJobAgent({'ai_provider': None})
        with pytest.raises(RuntimeError, match='AI client is required'):
            agent.filter_by_experience_years([{'title': 'X'}], 0, 3)

    def test_keeps_job_in_window(self):
        agent = _agent_with_replies('{"min_years": 1, "max_years": 3}')
        jobs = [{'title': 'Software Engineer', 'description': '2+ years'}]
        result = agent.filter_by_experience_years(jobs, 0, 3)
        assert len(result) == 1

    def test_excludes_job_above_window(self):
        agent = _agent_with_replies('{"min_years": 8, "max_years": 12}')
        jobs = [{'title': 'Principal Engineer', 'description': 'Senior leader'}]
        result = agent.filter_by_experience_years(jobs, 0, 3)
        assert result == []

    def test_open_ended_user_max_keeps_senior(self):
        # User window "5+" (max=None) keeps a role wanting 6-8 years.
        agent = _agent_with_replies('{"min_years": 6, "max_years": 8}')
        jobs = [{'title': 'Staff Engineer', 'description': 'Very senior'}]
        result = agent.filter_by_experience_years(jobs, 5, None)
        assert len(result) == 1

    def test_job_open_ended_max_kept_when_min_in_window(self):
        # Job wants "2+ years" (max=None); user window 0-3 => kept.
        agent = _agent_with_replies('{"min_years": 2, "max_years": null}')
        jobs = [{'title': 'Dev', 'description': '2+ years'}]
        result = agent.filter_by_experience_years(jobs, 0, 3)
        assert len(result) == 1
        assert result[0]['required_years'] == {'min': 2, 'max': None}

    def test_job_min_above_user_max_excluded(self):
        # Job wants "5+ years"; user window 0-3 => excluded.
        agent = _agent_with_replies('{"min_years": 5, "max_years": null}')
        jobs = [{'title': 'Senior', 'description': '5+ years'}]
        assert agent.filter_by_experience_years(jobs, 0, 3) == []

    def test_attaches_required_years_without_mutating_input(self):
        agent = _agent_with_replies('{"min_years": 2, "max_years": 4}')
        jobs = [{'id': '1', 'title': 'Dev', 'description': '...'}]
        result = agent.filter_by_experience_years(jobs, 0, 5)
        assert result[0]['required_years'] == {'min': 2, 'max': 4}
        assert 'required_years' not in jobs[0]  # original dict untouched

    def test_drops_unparseable_estimate(self):
        agent = _agent_with_replies('sorry, cannot tell')
        jobs = [{'title': 'Mystery', 'description': '...'}]
        assert agent.filter_by_experience_years(jobs, 0, 10) == []

    def test_drops_invalid_experience_range(self):
        agent = _agent_with_replies('{"min_years": 5, "max_years": 2}')
        jobs = [{'title': 'Invalid range', 'description': '...'}]
        assert agent.filter_by_experience_years(jobs, 0, 10) == []

    @patch('Agent.ai_job_agent.sleep')
    def test_retries_failed_estimate(self, mock_sleep):
        agent = AIJobAgent({'ai_provider': None})
        agent._ai_client = Mock()
        agent._estimate_required_years = Mock(
            side_effect=[RuntimeError('temporary failure'), {'min': 1, 'max': 3}]
        )

        result = agent.filter_by_experience_years([{'title': 'Dev'}], 0, 3)

        assert len(result) == 1
        assert agent._estimate_required_years.call_count == 2
        mock_sleep.assert_called_once_with(agent.FILTER_RETRY_DELAY_SECONDS)


class TestSuitability:
    def test_parses_json(self):
        payload = (
            '{"score": 82, "verdict": "strong", "experience_match": true, '
            '"matched_skills": ["Python"], "missing_skills": ["Go"], '
            '"reasoning": "Good fit."}'
        )
        agent = _agent_with_replies(payload)
        result = agent.assess_suitability({'title': 'Dev', 'description': '...'}, 'resume')
        assert result['score'] == 82
        assert result['verdict'] == 'strong'
        assert result['experience_match'] is True
        assert result['matched_skills'] == ['Python']

    def test_parses_json_in_code_fence(self):
        payload = '```json\n{"score": 50, "verdict": "moderate"}\n```'
        agent = _agent_with_replies(payload)
        result = agent.assess_suitability({'title': 'Dev'}, 'resume')
        assert result['score'] == 50
        assert result['verdict'] == 'moderate'

    def test_degrades_on_non_json(self):
        agent = _agent_with_replies('Sorry, I cannot comply.')
        result = agent.assess_suitability({'title': 'Dev'}, 'resume')
        assert result['verdict'] == 'unknown'
        assert result['reasoning'] == 'Sorry, I cannot comply.'

    def test_degrades_on_invalid_score(self):
        agent = _agent_with_replies('{"score": 140, "verdict": "strong"}')
        result = agent.assess_suitability({'title': 'Dev'}, 'resume')
        assert result['score'] is None
        assert result['verdict'] == 'unknown'


class TestTailorResume:
    def test_parses_json(self):
        payload = (
            '{"name": "Ada", "contact": "ada@x.com", "summary": "Engineer", '
            '"sections": [{"heading": "Skills", "bullets": ["Python"]}]}'
        )
        agent = _agent_with_replies(payload)
        result = agent.tailor_resume('resume', {'title': 'Dev', 'description': '...'})
        assert result['name'] == 'Ada'
        assert result['sections'][0]['heading'] == 'Skills'

    def test_degrades_on_non_json(self):
        agent = _agent_with_replies('here is your resume, plain text')
        result = agent.tailor_resume('resume', {'title': 'Dev'})
        # Preserves model text in a section so a document can still be built.
        assert result['sections']
        assert 'plain text' in result['sections'][0]['bullets'][0]


class TestScreenJob:
    """Combined screen: one call returns required-years AND suitability."""

    def test_combines_years_and_suitability(self):
        payload = (
            '{"required_min_years": 2, "required_max_years": 4, "score": 80, '
            '"verdict": "strong", "matched_skills": ["Python"], '
            '"missing_skills": ["Go"], "reasoning": "Good fit."}'
        )
        agent = _agent_with_replies(payload)
        result = agent.screen_job({'title': 'Dev', 'description': '...'}, 'resume', 0, 3)
        assert result['required_years'] == {'min': 2, 'max': 4}
        assert result['experience_match'] is True  # [2,4] overlaps [0,3]
        assert result['score'] == 80
        assert result['verdict'] == 'strong'
        assert result['matched_skills'] == ['Python']
        assert result['missing_skills'] == ['Go']

    def test_experience_match_computed_not_trusted(self):
        # Job wants "6+ years" (open-ended); user window 0-3 => no match, even
        # though the model never sends an experience_match field.
        payload = '{"required_min_years": 6, "required_max_years": null, "score": 40, "verdict": "weak"}'
        agent = _agent_with_replies(payload)
        result = agent.screen_job({'title': 'Sr'}, 'resume', 0, 3)
        assert result['required_years'] == {'min': 6, 'max': None}
        assert result['experience_match'] is False

    def test_degrades_on_non_json(self):
        agent = _agent_with_replies('cannot help with that')
        result = agent.screen_job({'title': 'Dev'}, 'resume', 0, 3)
        assert result['required_years'] is None
        assert result['experience_match'] is False  # unknown never matches a set window
        assert result['verdict'] == 'unknown'
        assert 'valid screening JSON' in result['reasoning']


class TestExtractJson:
    def test_prose_wrapped(self):
        data = AIJobAgent._extract_json('Here you go: {"a": 1} thanks')
        assert data == {'a': 1}

    def test_raises_when_no_json(self):
        with pytest.raises(ValueError):
            AIJobAgent._extract_json('no json here')


if __name__ == '__main__':
    pytest.main([__file__])
