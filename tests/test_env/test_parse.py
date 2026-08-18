"""Parsing .env text.

``parse_env`` is pure, so every case here is a string in and a dict out —
nothing touches the process environment.
"""

import pytest

from sillo.env import parse_env


def parse(text, **kwargs):
    """Parse against an empty environment unless a test says otherwise."""
    kwargs.setdefault("environ", {})
    return parse_env(text, **kwargs)


class TestBasics:
    """The shape of a line."""

    def test_simple_assignment(self):
        assert parse("KEY=value") == {"KEY": "value"}

    def test_several_lines(self):
        assert parse("A=1\nB=2\nC=3") == {"A": "1", "B": "2", "C": "3"}

    def test_surrounding_whitespace_is_dropped(self):
        assert parse("  KEY  =  value  ") == {"KEY": "value"}

    def test_export_prefix_is_dropped(self):
        assert parse("export KEY=value") == {"KEY": "value"}

    def test_empty_value(self):
        assert parse("KEY=") == {"KEY": ""}

    def test_value_containing_equals(self):
        assert parse("DSN=user=admin;pass=x") == {"DSN": "user=admin;pass=x"}

    def test_last_definition_wins(self):
        assert parse("KEY=first\nKEY=second") == {"KEY": "second"}

    def test_blank_lines_and_whitespace(self):
        assert parse("\n\n  \nKEY=value\n\n") == {"KEY": "value"}

    def test_no_trailing_newline(self):
        assert parse("A=1\nB=2") == {"A": "1", "B": "2"}

    def test_crlf_line_endings(self):
        assert parse("A=1\r\nB=2\r\n") == {"A": "1", "B": "2"}

    def test_byte_order_mark_is_ignored(self):
        assert parse("\ufeffKEY=value") == {"KEY": "value"}

    def test_empty_text(self):
        assert parse("") == {}


class TestComments:
    """What counts as a comment."""

    def test_whole_line_comment(self):
        assert parse("# nothing here\nKEY=value") == {"KEY": "value"}

    def test_indented_comment(self):
        assert parse("   # nothing here\nKEY=value") == {"KEY": "value"}

    def test_trailing_comment(self):
        assert parse("KEY=value # explain") == {"KEY": "value"}

    def test_hash_without_leading_space_stays(self):
        # The case that silently corrupts passwords when a parser is greedy.
        assert parse("PASSWORD=pa#ssword") == {"PASSWORD": "pa#ssword"}

    def test_hash_inside_quotes_stays(self):
        assert parse('URL="https://example.com/#anchor"') == {
            "URL": "https://example.com/#anchor"
        }

    def test_comment_after_quoted_value(self):
        assert parse('KEY="value" # explain') == {"KEY": "value"}


class TestQuoting:
    """Quotes, and what they turn off."""

    def test_double_quotes_are_stripped(self):
        assert parse('KEY="value"') == {"KEY": "value"}

    def test_single_quotes_are_stripped(self):
        assert parse("KEY='value'") == {"KEY": "value"}

    def test_quotes_preserve_spaces(self):
        assert parse('KEY="  spaced  "') == {"KEY": "  spaced  "}

    def test_escape_sequences_in_double_quotes(self):
        assert parse(r'KEY="line\nbreak\ttab"') == {"KEY": "line\nbreak\ttab"}

    def test_escaped_quote_in_double_quotes(self):
        assert parse(r'KEY="say \"hi\""') == {"KEY": 'say "hi"'}

    def test_single_quotes_take_the_text_literally(self):
        assert parse(r"KEY='line\nbreak'") == {"KEY": r"line\nbreak"}

    def test_unknown_escape_keeps_both_characters(self):
        # A Windows path in a quoted value stays the path it looks like.
        assert parse(r'KEY="C:\Users\demo"') == {"KEY": r"C:\Users\demo"}

    def test_double_quoted_value_spans_lines(self):
        assert parse('KEY="one\ntwo"\nNEXT=3') == {"KEY": "one\ntwo", "NEXT": "3"}

    def test_triple_double_quotes(self):
        text = 'KEY="""line one\nline two"""\nNEXT=3'
        assert parse(text) == {"KEY": "line one\nline two", "NEXT": "3"}

    def test_triple_single_quotes_are_literal(self):
        text = "KEY='''raw $VAR\\n'''\nNEXT=3"
        assert parse(text) == {"KEY": "raw $VAR\\n", "NEXT": "3"}

    def test_certificate_over_many_lines(self):
        text = 'CERT="""-----BEGIN KEY-----\nabc\ndef\n-----END KEY-----"""'
        assert parse(text)["CERT"].endswith("-----END KEY-----")

    def test_unterminated_quote_does_not_raise(self):
        assert parse('KEY="unclosed') == {"KEY": '"unclosed'}

    def test_unterminated_triple_quote_takes_the_rest(self):
        assert parse('KEY="""unclosed\nmore') == {"KEY": "unclosed\nmore"}


class TestReferences:
    """``$VAR`` and ``${VAR}``."""

    def test_braced_reference_to_earlier_key(self):
        assert parse("HOST=example.com\nURL=https://${HOST}/api")["URL"] == (
            "https://example.com/api"
        )

    def test_bare_reference_to_earlier_key(self):
        assert parse("HOST=example.com\nURL=https://$HOST/api")["URL"] == (
            "https://example.com/api"
        )

    def test_reference_resolves_inside_double_quotes(self):
        assert parse('A=1\nB="value-$A"') == {"A": "1", "B": "value-1"}

    def test_reference_is_literal_inside_single_quotes(self):
        assert parse("A=1\nB='value-$A'") == {"A": "1", "B": "value-$A"}

    def test_unresolved_reference_is_empty(self):
        assert parse("URL=host-${NOPE}-end")["URL"] == "host--end"

    def test_falls_back_to_the_surrounding_environment(self):
        values = parse_env("URL=https://$HOST", environ={"HOST": "outside.test"})
        assert values["URL"] == "https://outside.test"

    def test_the_file_wins_over_the_surrounding_environment(self):
        values = parse_env("HOST=inside.test\nURL=https://$HOST", environ={"HOST": "outside.test"})
        assert values["URL"] == "https://inside.test"

    def test_default_when_unset(self):
        assert parse("PORT=${PORT:-8000}") == {"PORT": "8000"}

    def test_default_is_not_used_when_set(self):
        assert parse("A=5\nPORT=${A:-8000}")["PORT"] == "5"

    def test_colon_dash_default_covers_the_empty_string(self):
        assert parse("A=\nPORT=${A:-8000}")["PORT"] == "8000"

    def test_dash_default_keeps_the_empty_string(self):
        assert parse("A=\nPORT=${A-8000}")["PORT"] == ""

    def test_dash_default_applies_when_unset(self):
        assert parse("PORT=${NOPE-8000}")["PORT"] == "8000"

    def test_default_may_contain_dashes(self):
        assert parse("NAME=${NOPE:-a-b-c}")["NAME"] == "a-b-c"

    def test_escaped_dollar_is_literal(self):
        assert parse(r"PASSWORD=pa\$\$word") == {"PASSWORD": "pa$$word"}

    def test_escaped_dollar_is_literal_inside_quotes(self):
        assert parse(r'PASSWORD="pa\$word"') == {"PASSWORD": "pa$word"}

    def test_lone_dollar_survives(self):
        assert parse("KEY=100$") == {"KEY": "100$"}

    def test_dollar_before_punctuation_survives(self):
        assert parse("KEY=$-x") == {"KEY": "$-x"}

    def test_unclosed_brace_survives(self):
        assert parse("KEY=${UNCLOSED") == {"KEY": "${UNCLOSED"}


class TestMalformed:
    """A bad line is skipped, never raised."""

    @pytest.mark.parametrize(
        "line",
        [
            "no equals sign here",
            "9STARTS_WITH_DIGIT=x",
            "HAS SPACE=x",
            "HAS-DASH=x",
            "=novalue",
            "  ",
        ],
    )
    def test_bad_lines_are_skipped(self, line):
        assert parse(line) == {}

    def test_a_bad_line_does_not_stop_the_file(self):
        text = "GOOD=1\nthis line is nonsense\nALSO_GOOD=2"
        assert parse(text) == {"GOOD": "1", "ALSO_GOOD": "2"}

    def test_non_ascii_key_is_skipped(self):
        assert parse("CAFÉ=x\nOK=1") == {"OK": "1"}

    def test_unicode_values_are_kept(self):
        assert parse("GREETING=héllo → 世界") == {"GREETING": "héllo → 世界"}


class TestPurity:
    """``parse_env`` writes nothing."""

    def test_os_environ_is_untouched(self):
        import os

        assert "PARSE_ONLY_KEY" not in os.environ
        parse_env("PARSE_ONLY_KEY=value")
        assert "PARSE_ONLY_KEY" not in os.environ

    def test_defaults_to_os_environ_for_references(self, monkeypatch):
        monkeypatch.setenv("AMBIENT_HOST", "ambient.test")
        assert parse_env("URL=https://$AMBIENT_HOST")["URL"] == "https://ambient.test"
