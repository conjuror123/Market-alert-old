"""tools/dashboard.py: the page and its history across changes."""
import json

from tools import dashboard


def _result(commit="abc1234", pushes=3.7):
    window = {"name": "year to 2026-10-01"}
    v = {"pushes_a_week": pushes, "rows_a_week": 10.4, "busiest_week": {"pushes": 14}}
    return {"meta": {"commit": commit, "subject": "a change", "measured_at": "2026-10-12 09:00 UTC",
                     "instruments": 58, "levels": [4.5, 6.4, 9.0, 12.7]},
            "windows": [window], "volume": {"bot": {window["name"]: v}}}


def test_a_measurement_adds_its_row_and_a_rerun_of_the_commit_replaces_it():
    history = dashboard.with_history([], _result("aaa"))
    history = dashboard.with_history(history, _result("bbb", 3.9))
    assert [h["commit"] for h in history] == ["aaa", "bbb"]
    history = dashboard.with_history(history, _result("bbb", 4.1))
    assert [h["commit"] for h in history] == ["aaa", "bbb"]
    assert history[-1]["pushes_a_week"] == 4.1


def test_the_page_carries_the_numbers_and_cannot_be_closed_early_by_them():
    result = _result()
    result["meta"]["subject"] = "</script><b>x</b>"
    page = dashboard.render(result, dashboard.with_history([], result))
    assert "__PAYLOAD__" not in page
    payload = page.split('<script id="payload" type="application/json">')[1].split("</script>")[0]
    assert json.loads(payload)["m"]["meta"]["subject"] == "</script><b>x</b>"
