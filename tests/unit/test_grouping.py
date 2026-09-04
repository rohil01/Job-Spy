"""Unit tests for duplicate-posting grouping in pipeline.utils."""
from pipeline.utils import group_key, group_jobs, JobGrouper


class TestGroupKey:
    def test_normalizes_case_and_whitespace(self):
        a = {"company": "Tech  Corp", "title": "Software Engineer"}
        b = {"company": "tech corp", "title": "  software   engineer "}
        assert group_key(a) == group_key(b)

    def test_seniority_is_not_stripped(self):
        senior = {"company": "Acme", "title": "Senior Software Engineer"}
        plain = {"company": "Acme", "title": "Software Engineer"}
        assert group_key(senior) != group_key(plain)

    def test_missing_fields_default_to_empty(self):
        assert group_key({}) == ("", "")


class TestGroupJobs:
    def test_same_company_and_title_group_together(self):
        jobs = [
            {"job_url": "u1", "company": "Acme", "title": "Engineer"},
            {"job_url": "u2", "company": "acme", "title": "engineer"},
        ]
        groups = group_jobs(jobs)
        assert len(groups) == 1
        assert groups[0]["count"] == 2
        assert len(groups[0]["postings"]) == 2

    def test_different_titles_are_separate_groups(self):
        jobs = [
            {"job_url": "u1", "company": "Acme", "title": "Backend Engineer"},
            {"job_url": "u2", "company": "Acme", "title": "Frontend Engineer"},
        ]
        groups = group_jobs(jobs)
        assert len(groups) == 2

    def test_exact_duplicate_postings_collapse_within_group(self):
        jobs = [
            {"job_url": "u1", "company": "Acme", "title": "Engineer"},
            {"job_url": "u1", "company": "Acme", "title": "Engineer"},
        ]
        groups = group_jobs(jobs)
        assert len(groups) == 1
        assert groups[0]["count"] == 1

    def test_representative_preserves_original_casing(self):
        jobs = [{"job_url": "u1", "company": "Tech Corp", "title": "Data Scientist"}]
        groups = group_jobs(jobs)
        assert groups[0]["company"] == "Tech Corp"
        assert groups[0]["title"] == "Data Scientist"

    def test_first_seen_order_is_preserved(self):
        jobs = [
            {"job_url": "u1", "company": "B", "title": "Role"},
            {"job_url": "u2", "company": "A", "title": "Role"},
        ]
        groups = group_jobs(jobs)
        assert [g["company"] for g in groups] == ["B", "A"]


class TestJobGrouperIncremental:
    def test_role_across_two_batches_merges_into_one_group(self):
        grouper = JobGrouper()
        grouper.add_jobs([{"job_url": "u1", "company": "Acme", "title": "Engineer"}])
        grouper.add_jobs([{"job_url": "u2", "company": "Acme", "title": "Engineer"}])
        groups = grouper.ordered_groups()
        assert len(groups) == 1
        assert groups[0]["count"] == 2

    def test_add_jobs_returns_touched_group_deltas(self):
        grouper = JobGrouper()
        first = grouper.add_jobs([{"job_url": "u1", "company": "Acme", "title": "Engineer"}])
        assert len(first) == 1 and first[0]["count"] == 1
        # A new posting for the same role returns that same group, now count 2.
        second = grouper.add_jobs([{"job_url": "u2", "company": "Acme", "title": "Engineer"}])
        assert len(second) == 1
        assert second[0]["group_id"] == first[0]["group_id"]
        assert second[0]["count"] == 2

    def test_flat_annotated_tags_postings(self):
        grouper = JobGrouper()
        grouper.add_jobs(
            [
                {"job_url": "u1", "company": "Acme", "title": "Engineer"},
                {"job_url": "u2", "company": "Acme", "title": "Engineer"},
                {"job_url": "u3", "company": "Beta", "title": "Analyst"},
            ]
        )
        flat = grouper.flat_annotated()
        assert len(flat) == 3
        engineers = [j for j in flat if j["title"] == "Engineer"]
        assert all(j["group_count"] == 2 for j in engineers)
        assert len({j["group_id"] for j in engineers}) == 1
        assert grouper.num_groups() == 2
        assert grouper.num_jobs() == 3

    def test_duplicate_url_across_batches_is_ignored(self):
        grouper = JobGrouper()
        grouper.add_jobs([{"job_url": "u1", "company": "Acme", "title": "Engineer"}])
        delta = grouper.add_jobs([{"job_url": "u1", "company": "Acme", "title": "Engineer"}])
        assert delta == []
        assert grouper.num_jobs() == 1
