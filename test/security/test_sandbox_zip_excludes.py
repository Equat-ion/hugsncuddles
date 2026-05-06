def test_zip_excludes_env_file(tmp_path):
    from agent.tools.sandbox import _zip_repo

    (tmp_path / ".env").write_text("secret=1")
    (tmp_path / "app.py").write_text("print('ok')")

    zip_bytes = _zip_repo(str(tmp_path))
    assert b".env" not in zip_bytes


def test_zip_excludes_env_local(tmp_path):
    from agent.tools.sandbox import _zip_repo

    (tmp_path / ".env.local").write_text("secret=2")
    (tmp_path / "app.py").write_text("print('ok')")

    zip_bytes = _zip_repo(str(tmp_path))
    assert b".env.local" not in zip_bytes