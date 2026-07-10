"""
AppTest verification for the label-reframe task.
Checks that:
  - at.exception == [] on all three main pages
  - New pattern-indication labels appear (spot check)
  - Disclaimer renders on each page
Runs: live/bruno and demo/Alice
"""

import sys
import os
import pytest

# Ensure the dashboard root is on the path (for utils imports)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from streamlit.testing.v1 import AppTest

PAGES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "views", "00_Home.py")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "views", "2_Indicators.py")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "views", "3_Trends.py")),
]

DISCLAIMER_FRAGMENT = "acoustic and behavioral speech patterns"


def _run_page(page_path: str, mode: str, user_id: str) -> AppTest:
    at = AppTest.from_file(page_path, default_timeout=30)
    at.session_state["system_mode"] = mode
    at.session_state["user_id"] = user_id
    at.run()
    return at


class TestLiveBruno:
    """live mode, user=bruno"""

    @pytest.fixture(scope="class")
    def home(self):
        return _run_page(PAGES[0], "live", "bruno")

    @pytest.fixture(scope="class")
    def indicators(self):
        return _run_page(PAGES[1], "live", "bruno")

    @pytest.fixture(scope="class")
    def trends(self):
        return _run_page(PAGES[2], "live", "bruno")

    def test_home_no_exceptions(self, home):
        assert not home.exception, f"Home raised: {list(home.exception)}"

    def test_indicators_no_exceptions(self, indicators):
        assert not indicators.exception, f"Indicators raised: {list(indicators.exception)}"

    def test_trends_no_exceptions(self, trends):
        assert not trends.exception, f"Trends raised: {list(trends.exception)}"

    def test_home_disclaimer(self, home):
        full_text = " ".join(
            el.value for el in home.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Home info elements. Got: {full_text[:200]}"
        )

    def test_indicators_disclaimer(self, indicators):
        full_text = " ".join(
            el.value for el in indicators.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Indicators info elements. Got: {full_text[:200]}"
        )

    def test_trends_disclaimer(self, trends):
        full_text = " ".join(
            el.value for el in trends.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Trends info elements. Got: {full_text[:200]}"
        )

    def test_home_new_labels(self, home):
        # At least one of the new labels must appear in the page markdown
        page_text = " ".join(
            getattr(el, "value", "") or "" for el in home.markdown
        )
        new_labels = ["Elevated patterns", "Some elevated signals", "Within typical range"]
        found = [lbl for lbl in new_labels if lbl in page_text]
        # Also check subheader text
        sub_text = " ".join(getattr(el, "value", "") or "" for el in home.subheader)
        assert found or any(lbl in sub_text for lbl in new_labels), (
            f"No new status labels found in Home. page_text sample: {page_text[:300]}"
        )


class TestDemoAlice:
    """demo mode, user=Alice"""

    @pytest.fixture(scope="class")
    def home(self):
        return _run_page(PAGES[0], "demo", "Alice")

    @pytest.fixture(scope="class")
    def indicators(self):
        return _run_page(PAGES[1], "demo", "Alice")

    @pytest.fixture(scope="class")
    def trends(self):
        return _run_page(PAGES[2], "demo", "Alice")

    def test_home_no_exceptions(self, home):
        assert not home.exception, f"Home raised: {list(home.exception)}"

    def test_indicators_no_exceptions(self, indicators):
        assert not indicators.exception, f"Indicators raised: {list(indicators.exception)}"

    def test_trends_no_exceptions(self, trends):
        assert not trends.exception, f"Trends raised: {list(trends.exception)}"

    def test_home_disclaimer(self, home):
        full_text = " ".join(
            el.value for el in home.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Home info elements. Got: {full_text[:200]}"
        )

    def test_indicators_disclaimer(self, indicators):
        full_text = " ".join(
            el.value for el in indicators.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Indicators info elements. Got: {full_text[:200]}"
        )

    def test_trends_disclaimer(self, trends):
        full_text = " ".join(
            el.value for el in trends.info if hasattr(el, "value") and el.value
        )
        assert DISCLAIMER_FRAGMENT in full_text, (
            f"Disclaimer not found in Trends info elements. Got: {full_text[:200]}"
        )

    def test_indicators_no_clinical_status_hierarchy(self, indicators):
        # The old label "Clinical Status Hierarchy" must NOT appear
        all_subheaders = " ".join(getattr(el, "value", "") or "" for el in indicators.subheader)
        assert "Clinical Status" not in all_subheaders, (
            f"Old label 'Clinical Status' still present: {all_subheaders}"
        )

    def test_indicators_speech_pattern_overview(self, indicators):
        # The new label "Speech Pattern Overview" must appear in subheaders
        all_subheaders = " ".join(getattr(el, "value", "") or "" for el in indicators.subheader)
        # It may only appear if the Summary view is active (default), check presence
        # Alternatively check full page text
        all_text = (
            " ".join(getattr(el, "value", "") or "" for el in indicators.subheader)
            + " ".join(getattr(el, "value", "") or "" for el in indicators.markdown)
        )
        assert "Speech Pattern Overview" in all_text or "Pattern Analysis" in all_text, (
            f"New label not found. Subheaders: {all_subheaders[:300]}"
        )
