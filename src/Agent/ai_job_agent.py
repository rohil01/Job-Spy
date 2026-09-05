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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import sleep
from typing import List, Dict, Any, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator
import yaml


class ExperienceYearsOutput(BaseModel):
    min_years: int = Field(ge=0)
    max_years: Optional[int] = Field(default=None, ge=0)

    @field_validator('max_years')
    @classmethod
    def max_cannot_be_below_min(cls, value: Optional[int], info):
        if value is not None and value < info.data['min_years']:
            raise ValueError('max_years cannot be below min_years')
        return value


class SuitabilityOutput(BaseModel):
    score: Optional[int] = Field(default=None, ge=0, le=100)
    verdict: str = 'unknown'
    experience_match: Optional[bool] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    reasoning: str = ''


class ScreenOutput(BaseModel):
    required_min_years: Optional[int] = Field(default=None, ge=0)
    required_max_years: Optional[int] = Field(default=None, ge=0)
    score: Optional[int] = Field(default=None, ge=0, le=100)
    verdict: Literal['strong', 'moderate', 'weak'] = 'moderate'
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    reasoning: str = ''


class ResumeSectionOutput(BaseModel):
    heading: str = ''
    bullets: List[str] = Field(default_factory=list)


class TailoredResumeOutput(BaseModel):
    name: str = ''
    contact: str = ''
    summary: str = ''
    sections: List[ResumeSectionOutput] = Field(default_factory=list)


class AIJobAgent:
    """Filters jobs by experience, assesses resume suitability, and rewrites resumes."""

    FILTER_MAX_WORKERS = 5
    FILTER_MAX_ATTEMPTS = 3
    FILTER_RETRY_DELAY_SECONDS = 0.25
    INVALID_SCREENING_MESSAGE = 'The AI response did not contain a valid screening JSON object.'

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
        system: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a single-turn chat request and return the text content.

        All three agents expect a single JSON object back, so for NVIDIA
        Nemotron reasoning models we default to sending the documented
        ``detailed thinking off`` system prompt. Left on, those models emit a
        long chain-of-thought *into the content* that both burns the token
        budget before any JSON is produced and pollutes the parsed output.
        Pass ``system`` explicitly to override.
        """
        self._require_client()
        if system is None and self.ai_model and 'nemotron' in self.ai_model.lower():
            system = 'detailed thinking off'
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        kwargs: Dict[str, Any] = {
            'model': self.ai_model,
            'messages': messages,
            'temperature': temperature,
        }
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        # Native OpenAI supports this parameter consistently; NVIDIA NIM
        # compatibility varies by model and may reject the request outright.
        if json_mode and self.ai_provider == 'openai':
            kwargs['response_format'] = {'type': 'json_object'}
        response = self._ai_client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        content = (message.content or '').strip()
        # Some reasoning models leave content empty and put the answer in a
        # separate reasoning_content field; fall back to it only if needed.
        if not content:
            reasoning = getattr(message, 'reasoning_content', None)
            if isinstance(reasoning, str):
                content = reasoning.strip()
        return content

    @staticmethod
    def _find_last_json_object(text: str) -> Optional[Dict[str, Any]]:
        """Return the last balanced ``{...}`` object in ``text`` that parses.

        Reasoning models often emit prose (which may itself contain braces)
        before the final JSON answer, so a greedy first-brace-to-last-brace
        match is unreliable. This scans for balanced top-level objects
        (ignoring braces inside strings) and returns the last one that
        ``json.loads`` accepts — i.e. the final answer.
        """
        candidates: List[str] = []
        depth = 0
        start: Optional[int] = None
        in_str = False
        escape = False
        for i, ch in enumerate(text):
            if in_str:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}' and depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start:i + 1])
                    start = None
        for chunk in reversed(candidates):
            try:
                return json.loads(chunk)
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object from model output, tolerating fences/prose/reasoning."""
        cleaned = text.strip()
        # Drop a reasoning trace wrapped in <think>...</think>, if present, and
        # anything up to a stray closing tag (truncated/streamed reasoning).
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
        if '</think>' in cleaned:
            cleaned = cleaned.rsplit('</think>', 1)[-1].strip()
        # Strip a leading ```json / ``` fence if present.
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```[a-zA-Z]*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        obj = AIJobAgent._find_last_json_object(cleaned)
        if obj is not None:
            return obj
        raise ValueError(f'Could not parse JSON from model output: {text[:200]!r}')

    @staticmethod
    def _coerce_required_years(job_min: Any, job_max: Any) -> Optional[Dict[str, Any]]:
        """Coerce a raw model min/max pair into ``{"min", "max"}`` or None.

        Returns None when ``job_min`` isn't a usable number (so callers can drop
        the estimate). ``job_max`` degrades to None (open-ended) when missing or
        non-numeric, and is floored at ``min``. Booleans are rejected (``bool``
        is an ``int`` subclass, and ``True``/``False`` are never valid years).
        """
        if not isinstance(job_min, (int, float)) or isinstance(job_min, bool):
            return None
        if not isinstance(job_max, (int, float)) or isinstance(job_max, bool):
            job_max = None  # null / missing / non-numeric => open-ended
        min_i = max(0, int(job_min))
        max_i = None if job_max is None else max(min_i, int(job_max))
        return {'min': min_i, 'max': max_i}

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
            data = ExperienceYearsOutput.model_validate(self._extract_json(raw))
        except (ValueError, ValidationError):
            return None

        return self._coerce_required_years(data.min_years, data.max_years)

    def _estimate_required_years_with_retry(
        self, job: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Estimate one job's requirement, retrying transient call failures."""
        for attempt in range(self.FILTER_MAX_ATTEMPTS):
            try:
                return self._estimate_required_years(job)
            except Exception:
                if attempt == self.FILTER_MAX_ATTEMPTS - 1:
                    raise
                sleep(self.FILTER_RETRY_DELAY_SECONDS * (2 ** attempt))

        return None  # The loop either returns or raises on its final attempt.

    def estimate_required_years_parallel(
        self, jobs: List[Dict[str, Any]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Estimate requirements concurrently while retaining input order."""
        if not jobs:
            return []
        workers = min(self.FILTER_MAX_WORKERS, len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(self._estimate_required_years_with_retry, jobs))

    def _screen_job_with_retry(
        self,
        job: Dict[str, Any],
        resume_text: str,
        min_years: Optional[int],
        max_years: Optional[int],
    ) -> Dict[str, Any]:
        """Screen one job, retrying transient call failures."""
        for attempt in range(self.FILTER_MAX_ATTEMPTS):
            try:
                result = self.screen_job(job, resume_text, min_years, max_years)
                if result.get('reasoning') == self.INVALID_SCREENING_MESSAGE:
                    raise ValueError('Invalid screening response')
                return result
            except Exception:
                if attempt == self.FILTER_MAX_ATTEMPTS - 1:
                    return {
                        'required_years': None,
                        'experience_match': self.experience_matches(None, min_years, max_years),
                        'score': None,
                        'verdict': 'unknown',
                        'matched_skills': [],
                        'missing_skills': [],
                        'reasoning': self.INVALID_SCREENING_MESSAGE,
                    }
                sleep(self.FILTER_RETRY_DELAY_SECONDS * (2 ** attempt))

        raise RuntimeError('Screening failed unexpectedly.')

    def screen_jobs_parallel(
        self,
        jobs: List[Dict[str, Any]],
        resume_text: str,
        min_years: Optional[int],
        max_years: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Screen jobs concurrently while retaining input order."""
        if not jobs:
            return []
        workers = min(self.FILTER_MAX_WORKERS, len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(
                executor.map(
                    self._screen_job_with_retry,
                    jobs,
                    [resume_text] * len(jobs),
                    [min_years] * len(jobs),
                    [max_years] * len(jobs),
                )
            )

    def screen_jobs_parallel_stream(
        self,
        jobs: List[Dict[str, Any]],
        resume_text: str,
        min_years: Optional[int],
        max_years: Optional[int],
    ):
        """Yield completed screen results as workers finish."""
        if not jobs:
            return
        workers = min(self.FILTER_MAX_WORKERS, len(jobs))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._screen_job_with_retry,
                    job,
                    resume_text,
                    min_years,
                    max_years,
                ): (index, job)
                for index, job in enumerate(jobs)
            }
            for future in as_completed(futures):
                index, job = futures[future]
                yield index, job, future.result()

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

        A job is kept when its estimated required range overlaps the window
        (see :meth:`experience_matches`). Jobs whose required years can't be
        estimated are dropped (consistent with the previous level filter, which
        dropped non-matching jobs).
        """
        if min_years is None and max_years is None:
            return jobs
        self._require_client()

        filtered_jobs: List[Dict[str, Any]] = []
        estimates = self.estimate_required_years_parallel(jobs)
        for job, required in zip(jobs, estimates):
            if required is None:
                continue
            if not self.experience_matches(required, min_years, max_years):
                continue
            kept = dict(job)
            kept['required_years'] = required
            filtered_jobs.append(kept)
        return filtered_jobs

    @staticmethod
    def experience_matches(
        required: Optional[Dict[str, Any]],
        min_years: Optional[int],
        max_years: Optional[int],
    ) -> bool:
        """Whether a job's required-years range overlaps the target window.

        ``required`` is ``{"min", "max"}`` (``max`` None = open-ended) or None
        when the requirement couldn't be estimated. With both bounds None the
        window is unconstrained and everything matches; an unknown ``required``
        never matches a constrained window::

            keep  <=>  job_min <= user_max  AND  (job_max is None OR job_max >= user_min)
        """
        if min_years is None and max_years is None:
            return True
        if required is None:
            return False
        user_min = 0 if min_years is None else max(0, int(min_years))
        user_max = None if max_years is None else max(user_min, int(max_years))
        job_min, job_max = required['min'], required['max']
        below = user_max is not None and job_min > user_max
        above = job_max is not None and job_max < user_min
        return not (below or above)

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
        raw = self._chat(prompt, temperature=0.2, max_tokens=1500)
        try:
            data = SuitabilityOutput.model_validate(self._extract_json(raw))
        except (ValueError, ValidationError):
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
            'score': data.score,
            'verdict': data.verdict,
            'experience_match': data.experience_match,
            'matched_skills': data.matched_skills,
            'missing_skills': data.missing_skills,
            'reasoning': data.reasoning,
        }

    def screen_job(
        self,
        job: Dict[str, Any],
        resume_text: str,
        min_years: Optional[int],
        max_years: Optional[int],
    ) -> Dict[str, Any]:
        """Combined screen (Agents 1 + 2 in ONE call).

        A single LLM request both estimates the years of experience ``job``
        requires AND assesses how well ``resume_text`` fits it. This is cheaper
        and more consistent than calling the experience filter and the
        suitability assessor separately.

        ``experience_match`` is computed here from the model's required-years
        estimate versus the candidate's ``[min_years, max_years]`` window (see
        :meth:`experience_matches`) — it is NOT taken from the model, so the
        window and the verdict can never disagree. Returns ``required_years``
        (``{"min", "max"}`` or None), ``experience_match``, ``score``,
        ``verdict``, ``matched_skills``, ``missing_skills``, and ``reasoning``.
        """
        self._require_client()
        prompt = self._load_prompts()['screen_prompt'].format(
            resume=resume_text,
            title=job.get('title', ''),
            company=job.get('company', ''),
            description=job.get('description', ''),
        )
        raw = self._chat(
            prompt,
            temperature=0.0,
            max_tokens=1500,
            system='Return only the requested JSON object. Do not include reasoning outside JSON.',
            json_mode=True,
        )
        try:
            data = ScreenOutput.model_validate(self._extract_json(raw))
        except (ValueError, ValidationError):
            return {
                'required_years': None,
                'experience_match': self.experience_matches(None, min_years, max_years),
                'score': None,
                'verdict': 'unknown',
                'matched_skills': [],
                'missing_skills': [],
                'reasoning': self.INVALID_SCREENING_MESSAGE,
            }
        required = self._coerce_required_years(
            data.required_min_years, data.required_max_years
        )
        return {
            'required_years': required,
            'experience_match': self.experience_matches(required, min_years, max_years),
            'score': data.score,
            'verdict': data.verdict,
            'matched_skills': data.matched_skills,
            'missing_skills': data.missing_skills,
            'reasoning': data.reasoning,
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
            data = TailoredResumeOutput.model_validate(self._extract_json(raw))
        except (ValueError, ValidationError):
            # Preserve the model's text so the user still gets a document.
            return {
                'name': '',
                'contact': '',
                'summary': '',
                'sections': [{'heading': 'Tailored Resume', 'bullets': [raw]}],
            }
        return {
            'name': data.name,
            'contact': data.contact,
            'summary': data.summary,
            'sections': [section.model_dump() for section in data.sections],
        }
