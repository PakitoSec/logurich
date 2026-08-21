"""Pre-processing of custom bracket tags before Rich interprets markup.

Pre-markup tags such as ``[defang]...[/defang]`` mutate the text they enclose
before Rich parses any styling markup. Unknown tags are left untouched so Rich
still sees them. Actions live in a registry, so applications can add their own
with :func:`register_premarkup`.

Security notes:

- The output of :func:`process_premarkup` is meant to be handed to
  ``Text.from_markup``. Untrusted content can therefore inject Rich styles; run
  it through ``rich.markup.escape`` before processing when that matters.
- Inputs longer than :data:`MAX_PREMARKUP_INPUT` are returned unchanged. The
  observable-matching patterns are bounded, but very large inputs still cost
  time that a caller may not expect.
"""

from __future__ import annotations

import re
import textwrap
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from rich.text import Text

MAX_PREMARKUP_INPUT = 10_000
MAX_URL_DISPLAY_LENGTH = 80
LAST_PATH_SEGMENT_LIMIT = 24

TAG_PATTERN = re.compile(r"\[(/?)([^\]]+)\]")

URL_PATTERN = re.compile(
    r"(?P<url>(?:(?:https?|ftp)://|www\.)[^\s\[\]<>()]+)(?P<suffix>[.,!?)]*)",
    re.IGNORECASE,
)

# Label counts are bounded so a dotted run cannot drive quadratic backtracking.
EMAIL_PATTERN = re.compile(
    r"(?P<email>[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.){1,10}[A-Za-z]{2,63})"
    r"(?P<suffix>[.,!?)]*)"
)
DOMAIN_PATTERN = re.compile(
    r"(?<!@)(?<!://)(?<![A-Za-z0-9-])"
    r"(?P<domain>(?:[A-Za-z0-9-]{1,63}\.){1,10}[A-Za-z]{2,63}(?::\d{2,5})?"
    r"(?:/[^\s\[\]<>()]*)?)(?P<suffix>[.,!?)]*)",
    re.IGNORECASE,
)

DEFANG_REPLACEMENTS = {
    ".": r"\[.]",
    ":": r"\[:]",
    "@": r"\[@]",
}


@dataclass(frozen=True)
class PremarkupAction:
    """A named text transformation applied inside a pre-markup tag."""

    name: str
    handler: Callable[[str], str]
    priority: int = 100


_REGISTRY: dict[str, PremarkupAction] = {}
_REGISTRY_LOCK = threading.Lock()


@dataclass
class _StackFrame:
    tokens: tuple[str, ...]
    buffer: list[str] = field(default_factory=list)


def register_premarkup(
    name: str,
    handler: Callable[[str], str],
    *,
    priority: int = 100,
    replace: bool = False,
) -> PremarkupAction:
    """Register a pre-markup action under ``name``.

    Args:
        name (str): Tag name, without brackets. Must not contain whitespace.
        handler (Callable[[str], str]): Transformation applied to the enclosed text.
        priority (int): Lower values run earlier when a tag combines actions.
        replace (bool): Allow overwriting an already registered name.

    Return:
        The registered :class:`PremarkupAction`.

    Raises:
        ValueError: If ``name`` is empty, contains whitespace, or is already
            registered while ``replace`` is ``False``.
    """

    if not name or name.split() != [name]:
        raise ValueError("premarkup action name must be a single non-empty token")
    action = PremarkupAction(name=name, handler=handler, priority=priority)
    with _REGISTRY_LOCK:
        if name in _REGISTRY and not replace:
            raise ValueError(f"premarkup action already registered: {name}")
        _REGISTRY[name] = action
    return action


def unregister_premarkup(name: str) -> bool:
    """Remove a registered action, returning whether it existed."""

    with _REGISTRY_LOCK:
        return _REGISTRY.pop(name, None) is not None


def premarkup_actions() -> tuple[PremarkupAction, ...]:
    """Return the registered actions, ordered by priority then name."""

    with _REGISTRY_LOCK:
        actions = list(_REGISTRY.values())
    return tuple(sorted(actions, key=lambda action: (action.priority, action.name)))


def _registry_snapshot() -> dict[str, PremarkupAction]:
    with _REGISTRY_LOCK:
        return dict(_REGISTRY)


def process_premarkup(source: str) -> str:
    """Evaluate pre-markup tags and return the processed markup string.

    The result still contains Rich markup, including backslash escapes produced
    by ``defang``; it is only correct once passed to ``Text.from_markup``. Use
    :func:`process_premarkup_to_text` to get a rendered :class:`Text` directly.
    """

    if "[" not in source or len(source) > MAX_PREMARKUP_INPUT:
        return source
    return _apply_known_actions(source, _registry_snapshot())


def process_premarkup_to_text(source: Any) -> Any:
    """Evaluate pre-markup tags and return a :class:`Text`.

    Non-string inputs, such as Rich renderables, are returned unchanged so
    callers can pipe mixed content through a single call.
    """

    if not isinstance(source, str):
        return source
    return Text.from_markup(process_premarkup(source))


def _apply_known_actions(markup: str, actions: dict[str, PremarkupAction]) -> str:
    """Evaluate known pre-markup tags and strip them from the output.

    Tags that are not registered are left untouched so Rich can process or
    display them later on.
    """

    stack: list[_StackFrame] = [_StackFrame(tokens=())]
    pos = 0

    for match in TAG_PATTERN.finditer(markup):
        start, end = match.span()
        if start > pos:
            stack[-1].buffer.append(markup[pos:start])

        raw_tokens = match.group(2).strip()
        if not raw_tokens:
            stack[-1].buffer.append(match.group(0))
            pos = end
            continue

        tokens = tuple(raw_tokens.split())
        is_closing = bool(match.group(1))

        if all(token in actions for token in tokens):
            if is_closing:
                if len(stack) > 1 and stack[-1].tokens == tokens:
                    opening = stack.pop()
                    content = "".join(opening.buffer)
                    stack[-1].buffer.append(_run_actions(content, tokens, actions))
                else:
                    # Malformed closing tag; keep it literal.
                    stack[-1].buffer.append(match.group(0))
            else:
                stack.append(_StackFrame(tokens=tokens))
        else:
            stack[-1].buffer.append(match.group(0))

        pos = end

    if pos < len(markup):
        stack[-1].buffer.append(markup[pos:])

    while len(stack) > 1:
        opening = stack.pop()
        start_tag = "[" + " ".join(opening.tokens) + "]"
        stack[-1].buffer.append(start_tag)
        stack[-1].buffer.append("".join(opening.buffer))

    return "".join(stack[0].buffer)


def _run_actions(
    content: str, tokens: Sequence[str], actions: dict[str, PremarkupAction]
) -> str:
    ordered = sorted(
        (actions[token] for token in tokens),
        key=lambda action: (action.priority, action.name),
    )
    result = content
    for action in ordered:
        result = action.handler(result)
    return result


def _truncate_urls(text: str) -> str:
    return _replace_matches(text, URL_PATTERN, _truncate_match)


def _truncate_match(match: re.Match[str]) -> str:
    suffix = match.group("suffix") or ""
    return _truncate_single_url(match.group("url")) + suffix


def _truncate_single_url(url: str) -> str:
    original = url
    parsed = urlsplit(url)

    # Attempt to recover host information when scheme is absent.
    if not parsed.netloc and not parsed.scheme:
        fallback_parsed = urlsplit("http://" + url)
        if fallback_parsed.netloc:
            parsed = parsed._replace(
                netloc=fallback_parsed.netloc, path=fallback_parsed.path
            )

    scheme_prefix = f"{parsed.scheme}://" if parsed.scheme else ""
    netloc = parsed.netloc
    path = parsed.path

    if not netloc:
        # Give up on structuring the URL; fall back to a shortened literal.
        return textwrap.shorten(
            original, width=MAX_URL_DISPLAY_LENGTH, placeholder="..."
        )

    display = scheme_prefix + netloc

    if path and path != "/":
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            display += "/"
        elif len(segments) == 1 and len(segments[0]) <= LAST_PATH_SEGMENT_LIMIT:
            display += f"/{segments[0]}"
        else:
            display += f"/.../{segments[-1][:LAST_PATH_SEGMENT_LIMIT]}"
    elif path == "/":
        display += "/"

    if parsed.query:
        display += "?..."

    if parsed.fragment:
        display += "#..."

    if len(display) > MAX_URL_DISPLAY_LENGTH:
        display = display[: MAX_URL_DISPLAY_LENGTH - 3] + "..."

    # Avoid returning a "truncated" URL that is no shorter or clearer.
    if len(display) >= len(original):
        return original

    return display


def _defang_content(text: str) -> str:
    if "." not in text and "@" not in text:
        return text
    text = _replace_matches(text, EMAIL_PATTERN, _defang_email_match)
    text = _replace_matches(text, URL_PATTERN, _defang_url_match)
    return _replace_matches(text, DOMAIN_PATTERN, _defang_domain_match)


def _defang_email_match(match: re.Match[str]) -> str:
    return _defang_token(match.group("email")) + (match.group("suffix") or "")


def _defang_url_match(match: re.Match[str]) -> str:
    return _defang_token(match.group("url")) + (match.group("suffix") or "")


def _defang_domain_match(match: re.Match[str]) -> str:
    return _defang_token(match.group("domain")) + (match.group("suffix") or "")


def _defang_token(token: str) -> str:
    result: list[str] = []
    length = len(token)
    for index, char in enumerate(token):
        replacement = DEFANG_REPLACEMENTS.get(char)
        if not replacement:
            result.append(char)
            continue

        if char == ".":
            prev_char = token[index - 1] if index > 0 else ""
            next_char = token[index + 1] if index + 1 < length else ""
            if not (prev_char.isalnum() or next_char.isalnum()):
                result.append(char)
                continue

        result.append(replacement)

    return "".join(result)


def _apply_color_obs(text: str) -> str:
    if "." not in text and "@" not in text:
        return text
    text = _replace_matches(text, EMAIL_PATTERN, _color_email_match)
    text = _replace_matches(text, URL_PATTERN, _color_url_match)
    return _replace_matches(text, DOMAIN_PATTERN, _color_domain_match)


def _color_email_match(match: re.Match[str]) -> str:
    return f"[cyan]{match.group('email')}[/cyan]{match.group('suffix') or ''}"


def _color_url_match(match: re.Match[str]) -> str:
    return f"[cyan]{match.group('url')}[/cyan]{match.group('suffix') or ''}"


def _color_domain_match(match: re.Match[str]) -> str:
    return f"[cyan]{match.group('domain')}[/cyan]{match.group('suffix') or ''}"


def _replace_matches(
    text: str,
    pattern: re.Pattern[str],
    replacer: Callable[[re.Match[str]], str],
) -> str:
    if not text:
        return text

    result: list[str] = []
    last_end = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start < last_end:
            continue
        result.append(text[last_end:start])
        result.append(replacer(match))
        last_end = end
    result.append(text[last_end:])
    return "".join(result)


def _register_builtins() -> None:
    register_premarkup("truncate-url", _truncate_urls, priority=0, replace=True)
    register_premarkup("color-obs", _apply_color_obs, priority=1, replace=True)
    register_premarkup("defang", _defang_content, priority=2, replace=True)


_register_builtins()

__all__ = [
    "MAX_PREMARKUP_INPUT",
    "PremarkupAction",
    "premarkup_actions",
    "process_premarkup",
    "process_premarkup_to_text",
    "register_premarkup",
    "unregister_premarkup",
]
