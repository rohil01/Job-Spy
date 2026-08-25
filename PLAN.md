# JobSpy Project Enhancement Plan

## Overview
This plan outlines the implementation of:
1. A code review agent that runs on every code change
2. Comprehensive tests for the agent, scraper, and complete workflow
3. Adherence to development best practices

## Current State Analysis

### Project Structure
- `src/Agent/ai_job_agent.py`: AI agent for filtering jobs by experience level and resume matching
- `src/scraper/scraper.py`: Job scraper using jobsniffer
- `src/pipeline/`: Orchestrates scraping and AI filtering
- `main.py`: Entry point that runs the complete pipeline
- Limited existing tests in `tests/` and `test_ai_agent.py`
- No formal testing framework, linting, or CI/CD setup

### Key Components
1. **AIJobAgent**: 
   - `filter_by_experience_level()`: Uses AI to filter jobs by experience level
   - `match_resume()`: Matches jobs to resume skills (AI with fallback to string matching)
   - Falls back to string matching when AI unavailable

2. **Scraper**:
   - `scrape_jobs_from_sites()`: Main scraping function using jobsniffer
   - `scrape_jobs_simple()`: Simplified interface
   - Supports multiple job boards (LinkedIn, Indeed, etc.)

3. **Pipeline**:
   - `scraper_runner.py`: Scrapes jobs and saves to JSON
   - `ai_filter_step.py`: Applies AI filtering to scraped jobs
   - `utils.py`: Helper functions (JSON serialization, deduplication, logging)

## Implementation Plan

### 1. Code Review Agent Implementation

#### Approach
Create a pre-commit hook and GitHub Actions workflow to run code quality checks on every change.

#### Files to Create/Modify
- `.pre-commit-config.yaml`: Pre-commit hook configuration
- `.github/workflows/code-review.yml`: GitHub Actions workflow for CI
- `scripts/run_code_review.py`: Script to run all code review checks

#### Checks to Implement
- **Linting**: Flake8 for style issues
- **Formatting**: Black for code formatting
- **Type Checking**: MyPy for type safety
- **Security**: Bandit for security issues
- **Testing**: Run test suite to ensure no regressions

#### Implementation Details
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
        language_version: python3
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-bugbear]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML, types-requests]
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-ll, -x, tests/]  # Low level+, exclude tests
```

### 2. Test Creation Strategy

#### Approach
Create comprehensive test suite using pytest with fixtures and mocking.

#### Test Structure
```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── unit/
│   ├── test_ai_agent.py
│   └── test_scraper.py
├── integration/
│   └── test_pipeline.py
└── fixtures/
    ├── sample_jobs.json
    └── sample_resume_data.json
```

#### Agent Tests (`tests/unit/test_ai_agent.py`)
- Test `filter_by_experience_level()` with various inputs
- Test `match_resume()` with AI enabled/disabled
- Test fallback to string matching when AI unavailable
- Test edge cases (empty inputs, invalid data)
- Mock AI client responses to avoid API calls

#### Scraper Tests (`tests/unit/test_scraper.py`)
- Test `scrape_jobs_from_sites()` with mocked jobsniffer
- Test `scrape_jobs_simple()` interface
- Test error handling (missing jobsniffer, invalid parameters)
- Test with various job site configurations

#### Pipeline Tests (`tests/integration/test_pipeline.py`)
- Test complete workflow from scraping to filtering
- Test configuration loading
- Test file I/O operations
- Test error propagation

#### Fixtures
- Sample job postings matching expected schema
- Sample resume skills data
- Mocked API responses for AI services

### 3. Best Practices Implementation

#### Testing Framework
- **Tool**: Pytest
- **Configuration**: `pyproject.toml` or `pytest.ini`
- **Features**:
  - Test discovery
  - Fixtures for reusable test data
  - Mocking capabilities
  - Coverage reporting
  - Parallel test execution

#### Code Quality Tools
- **Formatting**: Black (with pyproject.toml configuration)
- **Linting**: Flake8 with plugins (flake8-bugbear, flake8-comprehensions)
- **Type Checking**: MyPy with strict mode
- **Security**: Bandit for vulnerability scanning
- **Complexity**: Radon for cyclomatic complexity

#### CI/CD Setup
- **GitHub Actions** workflow that runs on push/pull_request:
  - Setup Python environment
  - Install dependencies
  - Run linting checks
  - Run type checking
  - Run security scans
  - Execute test suite
  - Generate coverage report
  - Fail on any issues

#### Development Workflow
1. **Pre-commit**: Run code quality checks before committing
2. **Pull Request**: CI runs full test suite and quality checks
3. **Code Review**: Require approvals based on CI passing
4. **Release**: Tag-based releases with changelog generation

#### Documentation Standards
- **Docstrings**: Google-style docstrings for all public functions
- **Type Hints**: Full type annotations for all functions
- **README**: Comprehensive setup and usage instructions
- **API Docs**: Generate sphinx documentation if needed

### 4. Implementation Phases

#### Phase 1: Foundation (Immediate)
- Set up pytest configuration
- Create basic test structure
- Implement pre-commit hooks
- Create GitHub Actions workflow

#### Phase 2: Test Coverage (Short-term)
- Write comprehensive unit tests for AIJobAgent
- Write unit tests for scraper
- Write integration tests for pipeline
- Achieve >80% code coverage

#### Phase 3: Quality Gates (Medium-term)
- Configure linting, formatting, type checking
- Set up security scanning
- Establish CI/CD pipeline
- Document development workflow

#### Phase 4: Best Practices (Ongoing)
- Regular dependency updates
- Code review process refinement
- Performance benchmarking
- Documentation maintenance

### 5. Verification Strategy

#### How to Test Changes
1. **Local Development**:
   ```bash
   # Run all checks locally
   pre-commit run --all-files
   
   # Run tests
   pytest tests/
   
   # Run with coverage
   pytest --cov=src tests/
   ```

2. **CI Verification**:
   - GitHub Actions will run on every push/pull_request
   - Status checks must pass before merging
   - Branch protection rules required

#### Success Metrics
- All new code has corresponding tests
- Pre-commit hooks pass on all commits
- CI pipeline passes on all PRs
- >80% code coverage maintained
- No critical security issues reported
- Code formatting consistent (Black)

### 6. Files to Reference/Reuse

#### Existing Patterns to Leverage
- `src/pipeline/utils.py`: JSON serialization helpers, logging setup
- `src/pipeline/config.yaml`: Configuration loading pattern
- `test_ai_agent.py`: Basic testing approach for AI agent
- `main.py`: Pipeline orchestration pattern

#### Utilities to Reuse
- `make_json_safe()`: For JSON serialization in tests
- `setup_logger()`: For consistent logging in tests
- `random_backoff()`: For testing retry logic
- `deduplicate_jobs()`: For testing data processing

### 7. Risk Mitigation

#### Technical Risks
- **AI API costs**: Mock AI responses in tests to avoid real API calls
- **External dependencies**: Mock jobsniffer in scraper tests
- **Flaky tests**: Use deterministic test data, avoid timing-dependent tests

#### Process Risks
- **Adoption resistance**: Start with opt-in pre-commit, gradually make mandatory
- **Performance impact**: Run heavy checks (security, type checking) in CI only
- **Maintenance overhead**: Document workflow clearly, automate where possible

### 8. Future Enhancements

#### Potential Improvements
- Add performance benchmarking suite
- Implement property-based testing with hypothesis
- Add database integration tests
- Create Docker images for consistent testing environments
- Add mutation testing for test quality assessment
- Implement continuous profiling

## Conclusion

This plan provides a comprehensive approach to:
1. Implementing automated code review on every change
2. Creating robust test coverage for all components
3. Establishing development best practices

The implementation will improve code quality, catch issues early, and provide a solid foundation for future development.

---
*Plan created: 2026-08-25*