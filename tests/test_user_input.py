from logurich import init_logger, shutdown_logger, user_input


def test_user_input_uses_explicit_logurich_adapter(monkeypatch, buffer):
    monkeypatch.setattr("builtins.input", lambda: "alice")
    init_logger("INFO", enqueue=False)

    result = user_input("Name")
    shutdown_logger()

    assert result == "alice"
    assert buffer.getvalue().endswith("Name: ")
