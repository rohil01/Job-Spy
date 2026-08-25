#!/usr/bin/env python3
"""
Script to run all code review checks locally.
This replicates what runs in the GitHub Actions workflow.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('='*60)

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FAILED: {description}")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def main():
    """Run all code review checks."""
    # Change to project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    print("Running comprehensive code review checks...")
    print(f"Working directory: {project_root}")

    checks = [
        # Black formatting check
        (["black", "--check", "--diff", "."], "Black code formatting"),

        # Flake8 linting
        (["flake8", "src", "tests", "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"],
         "Flake8 linting (critical issues)"),
        (["flake8", "src", "tests", "--count", "--exit-zero", "--max-complexity=10", "--max-line-length=127", "--statistics"],
         "Flake8 linting (style and complexity)"),

        # MyPy type checking
        (["mypy", "src", "--ignore-missing-imports", "--follow-imports=silent"],
         "MyPy type checking"),

        # Bandit security scan
        (["bandit", "-r", "src", "-ll", "-x", "tests/"],
         "Bandit security scan"),

        # Tests with coverage
        (["pytest", "tests/", "--cov=src", "--cov-report=xml", "--cov-report=term-missing"],
         "Test suite with coverage"),
    ]

    # Check if we're in a virtual environment, if not suggest installing dependencies
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a venv, good to go
        pass
    else:
        print("\nNote: Consider running this script in a virtual environment")
        print("You may need to install dependencies: pip install flake8-bugbear black mypy types-PyYAML types-requests bandit pytest pytest-cov")

    # Run all checks
    results = []
    for command, description in checks:
        success = run_command(command, description)
        results.append((description, success))

    # Summary
    print(f"\n{'='*60}")
    print("CODE REVIEW SUMMARY")
    print('='*60)

    all_passed = True
    for description, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{status:>4} | {description}")
        if not success:
            all_passed = False

    print('='*60)
    if all_passed:
        print("All checks passed! ✓")
        return 0
    else:
        print("Some checks failed! ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())