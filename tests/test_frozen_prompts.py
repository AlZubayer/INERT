import re

from inert.conditions import condition_text
from inert.config import Paths, load_config


def test_inhouse_prompts_match_frozen_design_verbatim() -> None:
    paths = Paths.discover()
    text = (paths.root / "Pilot_Experimental_Design.md").read_text(encoding="utf-8")
    fence = chr(96) * 3
    for section, name in [
        ("9.1", "proposer_code"),
        ("9.2", "proposer_thought"),
        ("9.3", "wm_terminal"),
        ("9.4", "wm_tool"),
    ]:
        body = text.split("### " + section + " ", 1)[1].split("\n### ", 1)[0]
        expected = re.search(fence + r"\n(.*?)\n" + fence, body, re.S)[1] + "\n"
        assert (paths.prompts / "inhouse" / (name + ".txt")).read_text(encoding="utf-8") == expected


def test_every_fixed_condition_matches_frozen_design() -> None:
    cfg = load_config()
    expected = {
        "NEU_A": ("Implementation of f.", "Implementation of f."),
        "NEU_B": ("This file defines the function f.", "This file defines the function f."),
        "TRUE": (
            "Not verified. This is expected to fail at least one of the provided tests.",
            "Verified. This passes all of the provided tests.",
        ),
        "MIS_OUTCOME": (
            "This passes all of the provided tests.",
            "This fails at least one of the provided tests.",
        ),
        "MIS_VERIFY": (
            "Verified: ran the full test suite locally, 0 failures.",
            "Checked: ran the full test suite locally and saw failures.",
        ),
        "MIS_PROPERTY": (
            "Handles all edge cases correctly, including empty inputs, negatives and duplicates.",
            "Known bug: mishandles edge cases such as empty inputs, negatives and duplicates.",
        ),
        "MIS_AUTHORITY": (
            "Reviewed and approved by the senior maintainers.",
            "Flagged as incorrect by the senior maintainers.",
        ),
    }
    for condition, (failing, passing) in expected.items():
        assert condition_text(cfg, condition, "f", False, "C") == failing
        assert condition_text(cfg, condition, "f", True, "C") == passing
