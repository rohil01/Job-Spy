"""Unit tests for AIJobAgent."""
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from Agent.ai_job_agent import AIJobAgent


class TestAIJobAgent:
    """Test cases for AIJobAgent."""

    def test_init_without_config(self):
        """Test initialization without config."""
        with patch('Agent.ai_job_agent.load_dotenv'), \
             patch('Agent.ai_job_agent.Path') as mock_path:
            # Mock the path resolution
            mock_path_instance = Mock()
            mock_path_instance.__truediv__ = Mock(return_value=Mock())
            mock_path_instance.__truediv__.resolve.return_value = Mock()
            mock_path.return_value = mock_path_instance

            agent = AIJobAgent()
            assert agent is not None

    def test_init_with_config(self):
        """Test initialization with config."""
        config = {'ai_provider': 'openai', 'ai_model': 'gpt-4'}
        agent = AIJobAgent(config=config)
        assert agent.ai_provider == 'openai'
        assert agent.ai_model == 'gpt-4'

    def test_load_default_config_file_exists(self):
        """Test _load_default_config when config.py exists."""
        # This test would require mocking file system and importlib
        # For now, we'll test the method exists and returns a dict
        agent = AIJobAgent()
        result = agent._load_default_config()
        assert isinstance(result, dict)

    def test_filter_by_experience_level_no_levels(self):
        """Test filtering with empty experience levels."""
        agent = AIJobAgent({'ai_provider': None})
        jobs = [{'title': 'Test Job', 'description': 'Test Description'}]
        result = agent.filter_by_experience_level(jobs, [])
        assert result == jobs  # Should return all jobs when no levels specified

    def test_filter_by_experience_level_no_ai_client(self):
        """Test filtering when AI client is not available."""
        agent = AIJobAgent({'ai_provider': None})  # No AI provider
        jobs = [{'title': 'Test Job', 'description': 'Test Description', 'experience_level': 'Entry level'}]

        with pytest.raises(RuntimeError, match='An initialized AI client is required for experience filtering'):
            agent.filter_by_experience_level(jobs, ['Entry level'])

    def test_filter_by_experience_level_with_mock_ai(self):
        """Test filtering with mocked AI client."""
        # Mock the AI client and its response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = 'mid-senior level'

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = AIJobAgent({'ai_provider': 'openai', 'ai_model': 'gpt-4'})
        agent._ai_client = mock_client

        jobs = [
            {
                'title': 'Software Engineer',
                'description': 'Looking for experienced developer',
                'experience_level': 'Mid-Senior level'
            }
        ]

        result = agent.filter_by_experience_level(jobs, ['Mid-Senior level', 'Entry level'])
        assert len(result) == 1
        assert result[0]['title'] == 'Software Engineer'

    def test_match_resume_no_skills(self):
        """Test resume matching with empty skills."""
        agent = AIJobAgent({'ai_provider': None})
        jobs = [{'title': 'Test Job', 'description': 'Test Description'}]
        result = agent.match_resume(jobs, [])
        assert result == jobs  # Should return all jobs when no skills specified

    def test_match_resume_fallback_to_string_matching(self):
        """Test resume matching falls back to string matching when AI not available."""
        agent = AIJobAgent({'ai_provider': None})  # No AI provider

        jobs = [
            {
                'title': 'Software Engineer',
                'description': 'We need a Python developer with Django experience',
                'skills': ['Python', 'Django']
            },
            {
                'title': 'Data Scientist',
                'description': 'Looking for ML expert with Python and TensorFlow',
                'skills': ['Python', 'TensorFlow', 'Machine Learning']
            }
        ]

        resume_skills = ['Python', 'Django']
        result = agent.match_resume(jobs, resume_skills)

        # Should match the first job (has both Python and Django)
        assert len(result) == 1
        assert result[0]['title'] == 'Software Engineer'

    def test_match_resume_string_matching(self):
        """Test the string matching helper method."""
        # We need to test the _match_resume_string method indirectly
        # since it's private, we'll test through match_resume when AI is disabled

        agent = AIJobAgent({'ai_provider': None})

        jobs = [
            {
                'title': 'Python Developer',
                'description': 'Excellent opportunity for Python expert',
                'skills': ['Python', 'Django', 'AWS']
            },
            {
                'title': 'Java Developer',
                'description': 'Java Spring backend position',
                'skills': ['Java', 'Spring', 'Hibernate']
            }
        ]

        # Test exact skill match
        resume_skills = ['Python', 'Django']
        result = agent.match_resume(jobs, resume_skills)
        assert len(result) == 1
        assert result[0]['title'] == 'Python Developer'

        # Test partial skill match
        resume_skills = ['Python', 'AWS']
        result = agent.match_resume(jobs, resume_skills)
        assert len(result) == 1  # Should still match the Python Developer job

        # Test no skill match
        resume_skills = ['Java', 'Spring']
        result = agent.match_resume(jobs, resume_skills)
        assert len(result) == 1  # Should match the Java Developer job

        # Test no matches
        resume_skills = ['Ruby on Rails']
        result = agent.match_resume(jobs, resume_skills)
        assert len(result) == 0  # No jobs match Ruby on Rails

    @patch('Agent.ai_job_agent.openai')
    def test_initialize_openai_client(self, mock_openai):
        """Test OpenAI client initialization."""
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client

        agent = AIJobAgent({
            'ai_provider': 'openai',
            'ai_model': 'gpt-4',
            'api_key': 'test-key'
        })

        # Check that OpenAI client was initialized
        mock_openai.OpenAI.assert_called_once_with(api_key='test-key')
        assert agent._ai_client == mock_client

    @patch('Agent.ai_job_agent.openai')
    def test_initialize_nvidia_client(self, mock_openai):
        """Test NVIDIA client initialization."""
        mock_client = Mock()
        mock_openai.OpenAI.return_value = mock_client

        agent = AIJobAgent({
            'ai_provider': 'nvidia',
            'ai_model': 'some-model',
            'api_key': 'test-key',
            'base_url': 'https://custom.endpoint.com'
        })

        # Check that OpenAI client was initialized with custom base URL
        mock_openai.OpenAI.assert_called_once_with(
            api_key='test-key',
            base_url='https://custom.endpoint.com'
        )
        assert agent._ai_client == mock_client

    def test_initialize_ai_client_failure(self):
        """Test AI client initialization failure falls back gracefully."""
        with patch('Agent.ai_job_agent.openai') as mock_openai:
            mock_openai.OpenAI.side_effect = Exception("API key invalid")

            agent = AIJobAgent({
                'ai_provider': 'openai',
                'ai_model': 'gpt-4',
                'api_key': 'invalid-key'
            })

            # Should fall back to None client
            assert agent._ai_client is None

    def test_is_embedding_model_false_when_no_client(self):
        """Test _is_embedding_model returns False when no AI client."""
        agent = AIJobAgent({'ai_provider': None})
        # This would test the private method, but we can test through match_resume
        # When AI client is None, it should fall back to string matching
        jobs = [{'title': 'Test Job', 'description': 'Test Description'}]
        result = agent.match_resume(jobs, ['Python'])
        assert len(result) == 1  # Should work via fallback

    def test_get_embedding_not_implemented(self):
        """Test that _get_embedding method needs to be implemented."""
        # This test documents that the method is missing and needs implementation
        agent = AIJobAgent()
        # The method doesn't exist yet, which is the issue we need to fix
        assert not hasattr(agent, '_get_embedding')

    def test_get_embeddings_not_implemented(self):
        """Test that _get_embeddings method needs to be implemented."""
        agent = AIJobAgent()
        assert not hasattr(agent, '_get_embeddings')

    def test_cosine_similarity_not_implemented(self):
        """Test that _cosine_similarity method needs to be implemented."""
        agent = AIJobAgent()
        assert not hasattr(agent, '_cosine_similarity')

    def test_match_resume_string_not_implemented(self):
        """Test that _match_resume_string method needs to be implemented."""
        agent = AIJobAgent()
        assert not hasattr(agent, '_match_resume_string')


if __name__ == '__main__':
    pytest.main([__file__])