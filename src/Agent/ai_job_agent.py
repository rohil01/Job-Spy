"""
AI Job Agent for filtering jobs by experience level and matching with resume.
Provides a configurable backend that can use AI services or fall back to string matching.
"""

import os
import importlib.util
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
import yaml

class AIJobAgent:
    """
    Agent that filters jobs by experience level and matches with resume.
    Can be configured to use different AI providers (Anthropic, OpenAI, NVIDIA, local) or
    fall back to rule-based string matching.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the agent with configuration.
        If config is None, attempts to load from root config.py.
        """
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / '.env')
        self.prompt_path = Path(__file__).resolve().parent / 'Prompt' / 'v1.yaml'
        self.config = config if config is not None else self._load_default_config()
        self.ai_provider = self.config.get('ai_provider', None)
        self.ai_model = self.config.get('ai_model', None)
        if self.api_key is None:
            self.api_key = os.environ.get('NVIDIA_API_KEY')
        if self.api_key is None and self.ai_provider:
            self.api_key = os.environ.get(f'{self.ai_provider.upper()}_API_KEY')

        self._ai_client = None
        if self.ai_provider:
            self._initialize_ai_client()


    def _load_default_config(self) -> Dict[str, Any]:
        """Load configuration from root config.py."""
        project_root = Path(__file__).resolve().parents[2]
        config_path = project_root / 'config.py'

        if not config_path.exists():
            return {}

        try:
            spec = importlib.util.spec_from_file_location('jobspy_config', config_path)
            if spec is None or spec.loader is None:
                return {}
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            return {
                key: value
                for key, value in {
                    'ai_provider': getattr(config_module, 'AI_PROVIDER', None),
                    'ai_model': getattr(config_module, 'AI_MODEL', None),
                }.items()
                if value is not None
            }
        except Exception:
            return {}

    def _initialize_ai_client(self):
        """Initialize the AI client based on provider."""
        try:
            if self.ai_provider == 'openai':
                import openai
                self._ai_client = openai.OpenAI(api_key=self.api_key)
            elif self.ai_provider == 'nvidia':
                import openai
                base_url = self.config.get('base_url', "https://integrate.api.nvidia.com/v1")
                self._ai_client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=base_url
                )
        except Exception as e:
            # If initialization fails, we fall back to string matching
            print(f"Warning: Failed to initialize AI client for provider {self.ai_provider}: {e}")
            self._ai_client = None


    def filter_by_experience_level(self, jobs: List[Dict[str, Any]], experience_levels: List[str]) -> List[Dict[str, Any]]:
        """
        Filter jobs by experience level using the configured AI chat model.
        """
        if not experience_levels:
            return jobs
        if self._ai_client is None:
            raise RuntimeError('An initialized AI client is required for experience filtering')

        with self.prompt_path.open(encoding='utf-8') as prompt_file:
            prompt_template = yaml.safe_load(prompt_file)['experience_level_filter_prompt']

        allowed_levels = {level.strip().casefold(): level for level in experience_levels}
        filtered_jobs = []
        for job in jobs:
            prompt = prompt_template.format(
                experience_levels=', '.join(experience_levels),
                title=job.get('title', ''),
                description=job.get('description', ''),
            )
            response = self._ai_client.chat.completions.create(
                model=self.ai_model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0,
            )
            answer = response.choices[0].message.content.strip().casefold()
            if answer in allowed_levels:
                filtered_jobs.append(job)

        return filtered_jobs

    def match_resume(self, jobs: List[Dict[str, Any]], resume_skills: List[str]) -> List[Dict[str, Any]]:
        """
        Match jobs against resume skills using AI if available, otherwise fall back to string matching.
        """
        if not resume_skills:
            return jobs
        if self._ai_client is not None and self._is_embedding_model():
            return self._match_resume_ai(jobs, resume_skills)
        # Fallback to string matching
        return self._match_resume_string(jobs, resume_skills)


    # --- AI-based implementations ---
    def _match_resume_ai(self, jobs: List[Dict[str, Any]], resume_skills: List[str]) -> List[Dict[str, Any]]:
        """Match jobs against resume skills using embeddings."""
        if not jobs:
            return []

        # Get threshold from config, default to 0.5
        threshold = self.config.get('ai_resume_match_threshold', 0.5)

        # Prepare resume text
        resume_text = " ".join(resume_skills)
        if not resume_text.strip():
            return jobs  # If no skills, return all jobs (should be caught earlier, but safe)

        try:
            # Get embedding for resume
            resume_embedding = self._get_embedding(resume_text)
            if resume_embedding is None:
                return self._match_resume_string(jobs, resume_skills)

            # Process jobs in batches to avoid too long requests
            batch_size = 16
            matched_jobs = []
            for i in range(0, len(jobs), batch_size):
                batch = jobs[i:i+batch_size]
                batch_texts = []
                valid_jobs = []  # jobs that have text to embed
                for job in batch:
                    desc = job.get('description', '')
                    title = job.get('title', '')
                    text = f"{title} {desc}".strip()
                    if text:
                        batch_texts.append(text)
                        valid_jobs.append(job)
                    else:
                        # If no text, we cannot compute embedding, so fall back to string matching for this job
                        # We'll check with string matching and add if matches
                        if self._match_resume_string([job], resume_skills):
                            matched_jobs.append(job)

                if not batch_texts:
                    continue

                # Get embeddings for the batch
                batch_embeddings = self._get_embeddings(batch_texts)
                if batch_embeddings is None or len(batch_embeddings) != len(batch_texts):
                    # Fall back to string matching for this batch
                    for job in batch:
                        if self._match_resume_string([job], resume_skills):
                            matched_jobs.append(job)
                    continue

                # Compute cosine similarity for each job in the batch
                for job, embedding in zip(valid_jobs, batch_embeddings):
                    similarity = self._cosine_similarity(resume_embedding, embedding)
                    if similarity >= threshold:
                        matched_jobs.append(job)

            return matched_jobs
        except Exception as e:
            print(f"Warning: AI-based resume matching failed: {e}. Falling back to string matching.")
            return self._match_resume_string(jobs, resume_skills)

