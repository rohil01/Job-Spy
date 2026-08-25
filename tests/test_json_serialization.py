from datetime import date
import json


def test_json_dump_handles_date_values():
    data = [{"date_posted": date(2024, 1, 1), "title": "Engineer"}]

    serialized = json.dumps(data, default=lambda obj: obj.isoformat() if hasattr(obj, "isoformat") else str(obj))

    assert '"date_posted": "2024-01-01"' in serialized
