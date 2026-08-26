"""API tests using FastAPI's TestClient with the service layer mocked.

No network or LLM calls: every ``service.*`` function that would hit the model
or the network is patched. A real (tiny) .docx is generated with resume_io so
the upload path and docx parsing are exercised for real.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from Agent.resume_io import build_docx
from src.api.app import app

client = TestClient(app)

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@pytest.fixture
def resume_bytes():
    return build_docx({
        "name": "Ada Lovelace",
        "contact": "ada@example.com",
        "summary": "Engineer.",
        "sections": [{"heading": "Skills", "bullets": ["Python", "FastAPI"]}],
    })


def _upload(resume_bytes):
    return {"resume": ("resume.docx", resume_bytes, DOCX_MEDIA_TYPE)}


def test_health():
    with patch("src.api.service.agent_status", return_value={
        "ai_provider": "nvidia", "ai_model": "m", "ai_client_ready": True,
    }):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["ai_client_ready"] is True


def test_get_jobs():
    with patch("src.api.service.load_latest_jobs", return_value=[
        {"id": "1", "title": "Dev"}, {"id": "2", "title": "SRE"},
    ]):
        resp = client.get("/jobs")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_filter_experience():
    jobs = [{"id": "1", "title": "Dev"}, {"id": "2", "title": "VP"}]
    with patch("src.api.service.filter_experience", return_value=[jobs[0]]) as mock_filter:
        resp = client.post("/filter/experience", json={
            "jobs": jobs, "min_years": 0, "max_years": 2,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["input_count"] == 2
    assert body["filtered_count"] == 1
    assert body["min_years"] == 0
    assert body["max_years"] == 2
    # window forwarded to the service exactly as requested
    mock_filter.assert_called_once_with(jobs, 0, 2)


def test_filter_experience_defaults_to_config_window():
    jobs = [{"id": "1", "title": "Dev"}]
    with patch("src.api.service.filter_experience", return_value=jobs) as mock_filter, \
         patch("src.api.service.load_config", return_value={
             "experience_min_years": 1, "experience_max_years": 4,
         }):
        resp = client.post("/filter/experience", json={"jobs": jobs})
    assert resp.status_code == 200
    body = resp.json()
    assert body["min_years"] == 1
    assert body["max_years"] == 4
    mock_filter.assert_called_once_with(jobs, 1, 4)


def test_filter_experience_open_ended_max():
    jobs = [{"id": "1", "title": "Staff Eng"}]
    with patch("src.api.service.filter_experience", return_value=jobs) as mock_filter:
        resp = client.post("/filter/experience", json={"jobs": jobs, "min_years": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["min_years"] == 5
    assert body["max_years"] is None
    mock_filter.assert_called_once_with(jobs, 5, None)


def test_scrape_accepts_custom_params():
    params = {
        "sites": ["indeed"],
        "search_terms": ["Rust Engineer"],
        "location": "Berlin",
        "results_wanted": 3,
        "hours_old": 24,
        "country_indeed": "germany",
        "linkedin_fetch_description": False,
        "scrape_cooldown_minutes": 0.5,
    }
    with patch("src.api.service.run_scrape_task") as mock_task:
        resp = client.post("/scrape", json=params)
    assert resp.status_code == 202
    assert "run_id" in resp.json()
    assert mock_task.called
    # overrides forwarded as the second positional arg: (run_id, overrides)
    assert mock_task.call_args.args[1] == params


def test_scrape_without_body_uses_defaults():
    with patch("src.api.service.run_scrape_task") as mock_task:
        resp = client.post("/scrape")
    assert resp.status_code == 202
    assert mock_task.called
    assert mock_task.call_args.args[1] == {}


def test_scrape_config_defaults():
    fake = {
        "sites": ["linkedin", "indeed"],
        "search_terms": ["AI Engineer"],
        "location": "Bengaluru",
        "results_wanted": 5,
        "hours_old": 6,
        "country_indeed": "india",
        "linkedin_fetch_description": True,
        "scrape_cooldown_minutes": 0.5,
    }
    with patch("src.api.service.scrape_defaults", return_value=fake):
        resp = client.get("/config/scrape")
    assert resp.status_code == 200
    assert resp.json() == fake


def test_suitability_with_job_json(resume_bytes):
    assessment = {
        "score": 77, "verdict": "strong", "experience_match": True,
        "matched_skills": ["Python"], "missing_skills": [], "reasoning": "ok",
    }
    with patch("src.api.service.assess", return_value=assessment):
        resp = client.post(
            "/suitability",
            files=_upload(resume_bytes),
            data={"job": '{"id": "1", "title": "Dev"}'},
        )
    assert resp.status_code == 200
    assert resp.json()["score"] == 77
    assert resp.json()["verdict"] == "strong"


def test_suitability_rejects_non_docx():
    resp = client.post(
        "/suitability",
        files={"resume": ("resume.txt", b"not a docx", "text/plain")},
        data={"job": '{"id": "1"}'},
    )
    assert resp.status_code == 400


def test_suitability_requires_job(resume_bytes):
    resp = client.post("/suitability", files=_upload(resume_bytes))
    assert resp.status_code == 400


def test_tailor_resume_returns_docx(resume_bytes):
    fake_docx = b"PK\x03\x04 fake docx bytes"
    with patch("src.api.service.tailor_to_docx", return_value=fake_docx):
        resp = client.post(
            "/tailor-resume",
            files=_upload(resume_bytes),
            data={"job": '{"id": "1", "title": "Dev"}'},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == DOCX_MEDIA_TYPE
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == fake_docx


def test_run_accepts_and_reports_status(resume_bytes):
    # Patch the background task so nothing heavy runs; just verify the handshake.
    with patch("src.api.service.run_full_task") as mock_task:
        resp = client.post("/run", files=_upload(resume_bytes), data={"min_score": 50})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert mock_task.called

    status = client.get(f"/run/{run_id}")
    assert status.status_code == 200
    assert status.json()["run_id"] == run_id


def test_run_status_unknown_id():
    assert client.get("/run/does-not-exist").status_code == 404


def test_download_missing_resume_404():
    assert client.get("/run/nope/resume/nope").status_code == 404
