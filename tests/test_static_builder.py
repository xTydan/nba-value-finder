import json

from scripts import build_site


def test_safe_call_keeps_provider_failure_visible():
    value, status = build_site.safe_call("sample", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert value is None
    assert status["available"] is False
    assert status["error"] == "offline"


def test_snapshot_has_empty_recent_form_board_when_sources_are_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "SITE", tmp_path / "site")
    monkeypatch.setattr(build_site, "ROOT", tmp_path)
    monkeypatch.setattr(build_site, "safe_call", lambda name, fn: (None, {"name": name, "available": False, "error": "offline"}))
    (tmp_path / "app" / "static").mkdir(parents=True)
    (tmp_path / "app" / "static" / "index.html").write_text("<html></html>")
    (tmp_path / "app" / "static" / "app.js").write_text("")
    (tmp_path / "app" / "static" / "style.css").write_text("")
    build_site.main()
    data = json.loads((tmp_path / "site" / "data" / "latest.json").read_text())
    assert data["props_board"] == []
    assert "odds" not in data
    assert all(not source["available"] for source in data["sources"])
