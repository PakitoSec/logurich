import time

import pytest
from rich.text import Text

from logurich.premarkup import (
    MAX_PREMARKUP_INPUT,
    premarkup_actions,
    process_premarkup,
    process_premarkup_to_text,
    register_premarkup,
    unregister_premarkup,
)


@pytest.fixture
def custom_action():
    register_premarkup("shout", str.upper, priority=50)
    yield "shout"
    unregister_premarkup("shout")


def test_unknown_tags_are_preserved():
    assert process_premarkup("[bold]a[/bold] [nope]b[/nope]") == (
        "[bold]a[/bold] [nope]b[/nope]"
    )


def test_text_without_brackets_is_returned_unchanged():
    assert process_premarkup("nothing to do here") == "nothing to do here"


def test_unclosed_tag_is_restored_literally():
    assert process_premarkup("[defang]evil.com") == "[defang]evil.com"


def test_malformed_closing_tag_stays_literal():
    assert process_premarkup("[/defang]x") == "[/defang]x"


def test_empty_tag_stays_literal():
    assert process_premarkup("[]x") == "[]x"


def test_defang_handles_url_email_and_domain():
    result = process_premarkup("[defang]http://evil.com/a and bob@evil.com[/defang]")
    assert result == r"http\[:]//evil\[.]com/a and bob\[@]evil\[.]com"


def test_defang_leaves_isolated_dot_untouched():
    assert process_premarkup("[defang]end . here[/defang]") == "end . here"


def test_truncate_url_shortens_long_paths():
    result = process_premarkup(
        "[truncate-url]http://x.test/very/long/path/here?q=1#f[/truncate-url]"
    )
    assert result == "http://x.test/.../here?...#..."


def test_truncate_url_keeps_short_urls():
    assert process_premarkup("[truncate-url]http://x.test[/truncate-url]") == (
        "http://x.test"
    )


def test_color_obs_wraps_observables():
    assert process_premarkup("[color-obs]see evil.com now[/color-obs]") == (
        "see [cyan]evil.com[/cyan] now"
    )


def test_combined_actions_respect_priority():
    source = "[truncate-url defang]http://x.test/a/b/c/d/e/f/g/h[/truncate-url defang]"
    result = process_premarkup(source)
    # truncate-url runs first, so the shortened form is what ends up defanged.
    assert "..." in result
    assert r"\[.]" in result


def test_nested_tags_apply_inner_first():
    result = process_premarkup("keep [defang]evil.com[/defang] keep")
    assert result == r"keep evil\[.]com keep"


def test_to_text_renders_markup():
    assert process_premarkup_to_text("[defang]evil.com[/defang]").plain == "evil[.]com"


def test_to_text_passes_non_strings_through():
    marker = Text("already rich")
    assert process_premarkup_to_text(marker) is marker


def test_oversized_input_is_returned_unchanged():
    source = "[defang]" + ("a.b " * MAX_PREMARKUP_INPUT) + "[/defang]"
    assert process_premarkup(source) is source


def test_register_and_use_custom_action(custom_action):
    assert process_premarkup("[shout]hello[/shout]") == "HELLO"


def test_register_rejects_duplicate(custom_action):
    with pytest.raises(ValueError):
        register_premarkup("shout", str.lower)


def test_register_replaces_when_asked(custom_action):
    register_premarkup("shout", str.lower, replace=True)
    assert process_premarkup("[shout]HELLO[/shout]") == "hello"


def test_register_rejects_invalid_name():
    with pytest.raises(ValueError):
        register_premarkup("two words", str.upper)


def test_unregister_reports_whether_action_existed(custom_action):
    assert unregister_premarkup("shout") is True
    assert unregister_premarkup("shout") is False
    assert process_premarkup("[shout]hello[/shout]") == "[shout]hello[/shout]"
    register_premarkup("shout", str.upper)


def test_builtin_actions_are_ordered_by_priority():
    names = [action.name for action in premarkup_actions()]
    assert names[:3] == ["truncate-url", "color-obs", "defang"]


def test_adversarial_dotted_input_stays_fast():
    source = "[defang]" + ("a." * 2000) + "1[/defang]"
    start = time.perf_counter()
    process_premarkup(source)
    assert time.perf_counter() - start < 0.5
