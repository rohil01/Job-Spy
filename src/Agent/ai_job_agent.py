"""
AI Job Agent — three cooperating agents over an OpenAI-compatible chat API.

Agent 1  ``filter_by_experience_years``: keep only jobs whose required years of
                                          experience overlap the candidate's
                                          target window (i.e. "does this role
                                          want the amount of experience I have?").
Agent 2  ``assess_suitability``         : score how well a resume fits a job.
Agent 3  ``tailor_resume``              : rewrite a resume for a specific job.

All three share one configured chat model (NVIDIA by default, reached through
the ``openai`` client). Configuration comes from the root ``config.py`` unless
an override dict is supplied to the constructor.
"""

import os
import json
import re
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import yaml


class AIJobAgent:
    """Filters jobs by experience, assesses resume suitability, and rewrites resumes."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the agent.

        If ``config`` is None the settings are loaded from the root
        ``config.py``. The API key is resolved from the config, then the
        ``NVIDIA_API_KEY`` env var, then ``{PROVIDER}_API_KEY``.
        """
        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / '.env')
        self.prompt_path = Path(__file__).resolve().parent / 'Prompt' / 'v1.yaml'
        self.config = config if config is not None else self._load_default_config()

        self.ai_provider = self.config.get('ai_provider')
        self.ai_model = self.config.get('ai_model')
        self.ai_base_url = self.config.get('ai_base_url') or self.config.get('base_url')

        # Resolve API key: explicit config -> NVIDIA_API_KEY -> {PROVIDER}_API_KEY.
        self.api_key = self.config.get('api_key')
        if self.api_key is None:
            self.api_key = os.environ.get('NVIDIA_API_KEY')
        if self.api_key is None and self.ai_provider:
            self.api_key = os.environ.get(f'{self.ai_provider.upper()}_API_KEY')

        self._prompts: Optional[Dict[str, str]] = None
        self._ai_client = None
        if self.ai_provider:
            self._initialize_ai_client()

    # ------------------------------------------------------------------ #
    # Setup helpers
    # ------------------------------------------------------------------ #
    def _load_default_config(self) -> Dict[str, Any]:
        """Load configuration from the root ``config.py``."""
        project_root = Path(__file__).resolve().parents[2]
        config_path = project_root / 'config.py'
        if not config_path.exists():
            return {}
        try:
            spec = importlib.util.spec_from_file_location('jobspy_config', config_path)
            if spec is None or spec.loader is None:
                return {}
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'load_config'):
                return module.load_config()
            return {
                'ai_provider': getattr(module, 'AI_PROVIDER', None),
                'ai_model': getattr(module, 'AI_MODEL', None),
                'ai_base_url': getattr(module, 'AI_BASE_URL', None),
            }
        except Exception:
            return {}

    def _initialize_ai_client(self):
        """Initialize the OpenAI-compatible client for the configured provider."""
        try:
            import openai
            if self.ai_provider == 'nvidia':
                base_url = self.ai_base_url or 'https://integrate.api.nvidia.com/v1'
                self._ai_client = openai.OpenAI(api_key=self.api_key, base_url=base_url)
            elif self.ai_provider == 'openai':
                if self.ai_base_url:
                    self._ai_client = openai.OpenAI(
                        api_key=self.api_key, base_url=self.ai_base_url
                    )
                else:
                    self._ai_client = openai.OpenAI(api_key=self.api_key)
            else:
                self._ai_client = None
        except Exception as exc:
            # If initialization fails we surface it later via _require_client.
            print(f"Warning: failed to initialize AI client for '{self.ai_provider}': {exc}")
            self._ai_client = None

    def _load_prompts(self) -> Dict[str, str]:
        """Load and cache the prompt templates from ``Prompt/v1.yaml``."""
        if self._prompts is None:
            with self.prompt_path.open(encoding='utf-8') as handle:
                self._prompts = yaml.safe_load(handle)
        return self._prompts

    def _require_client(self) -> None:
        if self._ai_client is None:
            raise RuntimeError(
                'An initialized AI client is required. Set AI_PROVIDER and the '
                'matching API key (e.g. NVIDIA_API_KEY) in your environment.'
            )

    def _chat(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a single-turn chat request and return the text content."""
        self._require_client()
        kwargs: Dict[str, Any] = {
            'model': self.ai_model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
        }
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        response = self._ai_client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or '').strip()

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object from model output, tolerating fences/prose."""
        cleaned = text.strip()
        # Strip a leading ```json / ``` fence if present.
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```[a-zA-Z]*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        raise ValueError(f'Could not parse JSON from model output: {text[:200]!r}')

    # ------------------------------------------------------------------ #
    # Agent 1 — experience-years filter
    # ------------------------------------------------------------------ #
    def _estimate_required_years(
        self, job: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Estimate the years of experience a job requires.

        Returns ``{"min": int, "max": int | None}`` (``max`` None means
        open-ended, e.g. "5+ years"), or ``None`` when the model output can't
        be parsed into a usable range.
        """
        prompt = self._load_prompts()['experience_years_prompt'].format(
            title=job.get('title', ''),
            description=job.get('description', ''),
        )
        raw = self._chat(prompt)
        try:
            data = self._extract_json(raw)
        except ValueError:
            return None

        job_min = data.get('min_years')
        if not isinstance(job_min, (int, float)) or isinstance(job_min, bool):
            return None
        job_max = data.get('max_years')
        if not isinstance(job_max, (int, float)) or isinstance(job_max, bool):
            job_max = None  # null / missing / non-numeric => open-ended
        min_i = max(0, int(job_min))
        max_i = None if job_max is None else max(min_i, int(job_max))
        return {'min': min_i, 'max': max_i}

    def filter_by_experience_years(
        self,
        jobs: List[Dict[str, Any]],
        min_years: Optional[int],
        max_years: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Keep jobs whose required experience overlaps ``[min_years, max_years]``.

        ``min_years`` / ``max_years`` describe the candidate's target window;
        ``max_years=None`` means open-ended ("min_years and up"). If BOTH are
        ``None`` the jobs are returned unfiltered. Each kept job is a shallow
        copy with a ``required_years`` = ``{"min", "max"}`` field attached.

        A job is kept when its estimated required range overlaps the window::

            keep  <=>  job_min <= user_max  AND  (job_max is None OR job_max >= user_min)

        Jobs whose required years can't be estimated are dropped (consistent
        with the previous level filter, which dropped non-matching jobs).
        """
        if min_years is None and max_years is None:
            return jobs
        self._require_client()

        user_min = 0 if min_years is None else max(0, int(min_years))
        user_max = None if max_years is None else max(user_min, int(max_years))

        filtered_jobs: List[Dict[str, Any]] = []
        for job in jobs:
            required = self._estimate_required_years(job)
            if required is None:
                continue
            job_min, job_max = required['min'], required['max']
            below = user_max is not None and job_min > user_max
            above = job_max is not None and job_max < user_min
            if below or above:
                continue
            kept = dict(job)
            kept['required_years'] = required
            filtered_jobs.append(kept)
        return filtered_jobs

    # ------------------------------------------------------------------ #
    # Agent 2 — resume suitability assessment
    # ------------------------------------------------------------------ #
    def assess_suitability(
        self, job: Dict[str, Any], resume_text: str
    ) -> Dict[str, Any]:
        """Assess how well ``resume_text`` fits ``job``.

        Returns a dict with ``score`` (0-100), ``verdict``, ``experience_match``,
        ``matched_skills``, ``missing_skills``, and ``reasoning``.
        """
        self._require_client()
        prompt = self._load_prompts()['suitability_prompt'].format(
            resume=resume_text,
            title=job.get('title', ''),
            company=job.get('company', ''),
            description=job.get('description', ''),
        )
        raw = self._chat(prompt, temperature=0.2, max_tokens=800)
        try:
            data = self._extract_json(raw)
        except ValueError:
            # Degrade gracefully rather than failing the whole request.
            return {
                'score': None,
                'verdict': 'unknown',
                'experience_match': None,
                'matched_skills': [],
                'missing_skills': [],
                'reasoning': raw,
            }
        return {
            'score': data.get('score'),
            'verdict': data.get('verdict', 'unknown'),
            'experience_match': data.get('experience_match'),
            'matched_skills': data.get('matched_skills') or [],
            'missing_skills': data.get('missing_skills') or [],
            'reasoning': data.get('reasoning', ''),
        }

    # ------------------------------------------------------------------ #
    # Agent 3 — resume rewrite / tailoring
    # ------------------------------------------------------------------ #
    def tailor_resume(
        self, resume_text: str, job: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rewrite ``resume_text`` to better target ``job``.

        Returns a structured resume dict (``name``, ``contact``, ``summary``,
        ``sections``) ready to render with ``resume_io.build_docx``.
        """
        self._require_client()
        prompt = self._load_prompts()['resume_tailor_prompt'].format(
            resume=resume_text,
            title=job.get('title', ''),
            company=job.get('company', ''),
            description=job.get('description', ''),
        )
        raw = self._chat(prompt, temperature=0.3, max_tokens=2000)
        try:
            data = self._extract_json(raw)
        except ValueError:
            # Preserve the model's text so the user still gets a document.
            return {
                'name': '',
                'contact': '',
                'summary': '',
                'sections': [{'heading': 'Tailored Resume', 'bullets': [raw]}],
            }
        return {
            'name': data.get('name', ''),
            'contact': data.get('contact', ''),
            'summary': data.get('summary', ''),
            'sections': data.get('sections') or [],
        }
