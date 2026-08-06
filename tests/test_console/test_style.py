"""Colour rendering and the decision not to."""

from __future__ import annotations

import pytest

from sillo.console import PRIMARY, Palette, Style, strip_ansi


def enabled(**kwargs) -> Palette:
    """A palette that renders colour regardless of the stream."""
    return Palette(enabled=True, **kwargs)


# -- the on/off decision -----------------------------------------------


def test_a_disabled_palette_returns_the_text_untouched():
    palette = Palette(enabled=False)

    assert palette.render("hello", Style(fg="red", bold=True)) == "hello"


def test_no_style_returns_the_text_untouched():
    assert enabled().render("hello", None) == "hello"


def test_a_style_that_sets_nothing_returns_the_text_untouched():
    assert enabled().render("hello", Style()) == "hello"


def test_empty_text_is_never_wrapped():
    assert enabled().render("", Style(fg="red")) == ""


# -- colours -----------------------------------------------------------


def test_a_base_colour_uses_its_single_parameter_code():
    assert enabled().render("x", Style(fg="red")) == "\x1b[31mx\x1b[0m"


def test_a_bright_colour_uses_the_ninety_range():
    assert enabled().render("x", Style(fg="bright_red")) == "\x1b[91mx\x1b[0m"


def test_grey_is_an_alias_for_bright_black():
    palette = enabled()

    assert palette.render("x", Style(fg="grey")) == palette.render(
        "x", Style(fg="bright_black")
    )


def test_a_background_colour_uses_the_forty_range():
    assert enabled().render("x", Style(bg="blue")) == "\x1b[44mx\x1b[0m"


def test_hex_becomes_true_colour_when_the_terminal_advertises_it():
    palette = enabled(truecolor=True)

    assert palette.render("x", Style(fg="#fc0345")) == "\x1b[38;2;252;3;69mx\x1b[0m"


def test_hex_downsamples_to_the_cube_otherwise():
    rendered = enabled(truecolor=False).render("x", Style(fg="#fc0345"))

    assert rendered.startswith("\x1b[38;5;")
    assert rendered.endswith("x\x1b[0m")


def test_a_grey_hex_lands_on_the_grey_ramp_not_the_cube():
    # #111112 is nearly black. Routed through the colour cube it would round to
    # index 16, pure black, and the panel borders would vanish.
    rendered = enabled(truecolor=False).render("x", Style(fg="#111112"))
    index = int(rendered.split("38;5;")[1].split("m")[0])

    assert 232 <= index <= 255


def test_a_palette_index_is_passed_through():
    assert enabled().render("x", Style(fg="200")) == "\x1b[38;5;200mx\x1b[0m"


def test_an_unknown_colour_is_rejected():
    with pytest.raises(ValueError, match="not a colour"):
        enabled().render("x", Style(fg="octarine"))


# -- attributes --------------------------------------------------------


@pytest.mark.parametrize(
    "attribute,code",
    [
        ("bold", "1"),
        ("dim", "2"),
        ("italic", "3"),
        ("underline", "4"),
        ("strike", "9"),
    ],
)
def test_each_attribute_has_its_code(attribute, code):
    rendered = enabled().render("x", Style(**{attribute: True}))

    assert rendered == f"\x1b[{code}mx\x1b[0m"


def test_attributes_combine_in_one_sequence():
    rendered = enabled().render("x", Style(fg="red", bold=True, underline=True))

    assert rendered == "\x1b[1;4;31mx\x1b[0m"


# -- composition -------------------------------------------------------


def test_layering_lets_the_upper_style_win_on_colour():
    combined = Style(fg="red") | Style(fg="blue")

    assert combined.fg == "blue"


def test_layering_keeps_a_colour_the_upper_style_does_not_set():
    combined = Style(fg="red") | Style(bold=True)

    assert combined.fg == "red"
    assert combined.bold is True


def test_layering_accumulates_attributes():
    combined = Style(bold=True) | Style(italic=True)

    assert combined.bold is True
    assert combined.italic is True


def test_with_returns_a_modified_copy():
    original = Style(fg="red")
    modified = original.with_(bold=True)

    assert original.bold is False
    assert modified.bold is True
    assert modified.fg == "red"


# -- measuring ---------------------------------------------------------


def test_stripping_removes_the_sequences():
    assert strip_ansi(enabled().render("hello", PRIMARY)) == "hello"


def test_stripping_leaves_plain_text_alone():
    assert strip_ansi("hello") == "hello"


def test_a_styled_string_is_longer_than_it_looks():
    styled = enabled().render("hello", PRIMARY)

    assert len(styled) > len("hello")
    assert len(strip_ansi(styled)) == len("hello")
