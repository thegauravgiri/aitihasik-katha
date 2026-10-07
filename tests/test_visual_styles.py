import pytest

from aitihasik_katha.core.visual_styles import (
    DEFAULT_STYLE,
    VISUAL_STYLES,
    get_style,
    list_styles,
    style_names,
)


def test_default_style_is_realistic():
    assert DEFAULT_STYLE == "realistic"
    style = get_style()
    assert style.name == "realistic"
    assert "35mm" in style.label or "35mm" in style.house_look


@pytest.mark.parametrize(
    "name",
    [
        "realistic",
        "animated",
        "disney",
        "anime",
        "dark_fantasy",
        "oil_painting",
        "graphic_novel",
        "claymation",
        "vintage_documentary",
    ],
)
def test_all_defined_styles_have_complete_prompt_guidance(name):
    style = get_style(name)
    assert style.name == name
    assert style.label
    assert style.description
    assert "9:16" in style.frame_prefix
    assert len(style.house_look) > 20
    assert len(style.video_motion_prompt) > 20
    assert len(style.character_style_guidance) > 20


def test_get_style_handles_case_and_dashes():
    assert get_style("DISNEY").name == "disney"
    assert get_style("dark-fantasy").name == "dark_fantasy"
    assert get_style("Oil Painting").name == "oil_painting"
    assert get_style("nonexistent_style").name == "realistic"


def test_get_style_strict_raises_on_unknown():
    with pytest.raises(ValueError, match="Unknown visual style"):
        get_style("nonexistent_style", strict=True)



def test_list_and_names_contain_expected_styles():
    names = style_names()
    assert "animated" in names
    assert "realistic" in names
    assert "disney" in names
    assert "anime" in names
    assert "dark_fantasy" in names
    assert "oil_painting" in names
    assert "graphic_novel" in names
    assert "claymation" in names
    assert "vintage_documentary" in names

    styles = list_styles()
    assert len(styles) == len(names)


def test_realistic_and_documentary_enforce_ground_anchoring():
    realistic = get_style("realistic")
    doc = get_style("vintage_documentary")
    assert "Ground contact and physical gravity" in realistic.video_motion_prompt
    assert "realistic grounded period reenactment motion" in doc.video_motion_prompt
