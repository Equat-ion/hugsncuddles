def test_reader_returns_registry_payload(monkeypatch):
    from agent.nodes import reader

    monkeypatch.setattr(reader, "fetch_dep_diff", lambda *_: "diff")
    monkeypatch.setattr(reader, "fetch_migration_guide", lambda *_: "guide")

    from test.helpers.fakes import fake_state

    result = reader.run(fake_state())
    assert result["dep_diff"] == "diff"
    assert result["migration_guide"] == "guide"
    assert result["status"] == "running"


def test_reader_propagates_dep_diff_exception(monkeypatch):
    from agent.nodes import reader
    from test.helpers.fakes import fake_state

    def raise_err(*_):
        raise RuntimeError("dep fetch failed")

    monkeypatch.setattr(reader, "fetch_dep_diff", raise_err)
    monkeypatch.setattr(reader, "fetch_migration_guide", lambda *_: "guide")

    try:
        reader.run(fake_state())
    except RuntimeError as e:
        assert "dep fetch failed" in str(e)