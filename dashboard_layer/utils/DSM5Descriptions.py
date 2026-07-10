"""
DSM-5 criteria descriptions for Major Depressive Disorder indicators.
Based on the Diagnostic and Statistical Manual of Mental Disorders, 5th Edition.
"""

from typing import Optional


class DSM5Descriptions:
    """
    Provides DSM-5 diagnostic criteria descriptions for depression indicators.

    Note: These descriptions are for educational/research purposes and should not
    be used for clinical diagnosis without professional evaluation.
    """

    # Core symptoms (at least one required for MDD diagnosis)
    CORE_INDICATORS = ["1_depressed_mood", "2_loss_of_interest"]

    INDICATOR_DESCRIPTIONS = {
        "1_depressed_mood": {
            "name": "Depressed Mood",
            "criterion": "A1",
            "dsm5_text": (
                "Depressed mood most of the day, nearly every day, as indicated by "
                "either subjective report (e.g., feels sad, empty, hopeless) or "
                "observation made by others (e.g., appears tearful)."
            ),
            "patient_description": (
                "Feeling sad, empty, or hopeless for most of the day, nearly every day. "
                "Others might notice you seem down or tearful."
            ),
            "acoustic_rationale": (
                "Depression affects voice characteristics including lower pitch, "
                "reduced pitch variation, slower speech, and changes in voice quality. "
                "These acoustic markers reflect the psychomotor and emotional changes "
                "associated with depressed mood."
            ),
            "is_core": True,
        },
        "2_loss_of_interest": {
            "name": "Loss of Interest or Pleasure",
            "criterion": "A2",
            "dsm5_text": (
                "Markedly diminished interest or pleasure in all, or almost all, "
                "activities most of the day, nearly every day (as indicated by either "
                "subjective account or observation)."
            ),
            "patient_description": (
                "Losing interest in activities you used to enjoy, or not getting "
                "pleasure from things that normally make you happy."
            ),
            "acoustic_rationale": (
                "Reduced emotional engagement is reflected in flattened prosody - "
                "less variation in pitch, reduced energy dynamics, and decreased "
                "emotional expressiveness in voice patterns."
            ),
            "is_core": True,
        },
        "3_significant_weight_changes": {
            "name": "Significant Weight/Appetite Changes",
            "criterion": "A3",
            "dsm5_text": (
                "Significant weight loss when not dieting or weight gain "
                "(e.g., a change of more than 5% of body weight in a month), "
                "or decrease or increase in appetite nearly every day."
            ),
            "patient_description": (
                "Noticeable changes in appetite or weight without trying to diet. "
                "This might be eating much more or much less than usual."
            ),
            "acoustic_rationale": (
                "Weight changes cannot be measured through voice or speech analysis. "
                "This indicator requires direct measurement or self-reporting and is "
                "not populated from acoustic features in this system."
            ),
            "is_core": False,
        },
        "4_insomnia_hypersomnia": {
            "name": "Sleep Disturbance",
            "criterion": "A4",
            "dsm5_text": (
                "Insomnia or hypersomnia nearly every day."
            ),
            "patient_description": (
                "Trouble sleeping (insomnia) or sleeping too much (hypersomnia) "
                "almost every day. This includes difficulty falling asleep, staying "
                "asleep, or waking up too early."
            ),
            "acoustic_rationale": (
                "Sleep disturbances affect voice quality through fatigue-related "
                "changes. Poor sleep can result in reduced harmonics-to-noise ratio, "
                "altered speech rhythm, and changes in temporal modulation patterns."
            ),
            "is_core": False,
        },
        "5_psychomotor_retardation_agitation": {
            "name": "Psychomotor Changes",
            "criterion": "A5",
            "dsm5_text": (
                "Psychomotor agitation or retardation nearly every day "
                "(observable by others, not merely subjective feelings of "
                "restlessness or being slowed down)."
            ),
            "patient_description": (
                "Moving or speaking noticeably slower than usual (retardation), or "
                "feeling restless and unable to sit still (agitation). These changes "
                "are visible to others around you."
            ),
            "acoustic_rationale": (
                "Psychomotor changes are strongly reflected in speech: slower speech "
                "rate, longer pauses, reduced articulation speed, delayed voice onset, "
                "and changes in overall speech dynamics. These are among the most "
                "reliable acoustic markers of depression."
            ),
            "is_core": False,
        },
        "6_fatigue_loss_of_energy": {
            "name": "Fatigue or Loss of Energy",
            "criterion": "A6",
            "dsm5_text": (
                "Fatigue or loss of energy nearly every day."
            ),
            "patient_description": (
                "Feeling tired or having little energy almost every day, even when "
                "you haven't been physically active. Simple tasks may feel exhausting."
            ),
            "acoustic_rationale": (
                "Fatigue manifests in voice through altered speech rhythm patterns, "
                "reduced vocal energy, and changes in temporal and spectral modulation. "
                "The voice may sound more monotonous or lack its usual dynamism."
            ),
            "is_core": False,
        },
        "7_feelings_of_worthlessness_guilt": {
            "name": "Worthlessness or Excessive Guilt",
            "criterion": "A7",
            "dsm5_text": (
                "Feelings of worthlessness or excessive or inappropriate guilt "
                "(which may be delusional) nearly every day (not merely self-reproach "
                "or guilt about being sick)."
            ),
            "patient_description": (
                "Feeling worthless or excessively guilty about things, even when "
                "there's no real reason for these feelings. This goes beyond normal "
                "self-criticism."
            ),
            "acoustic_rationale": (
                "This indicator is primarily cognitive/emotional and has limited "
                "direct acoustic correlates. It is tracked through other assessment "
                "methods such as the PHQ-9 questionnaire."
            ),
            "is_core": False,
        },
        "8_diminished_ability_to_think_or_concentrate": {
            "name": "Concentration Difficulty",
            "criterion": "A8",
            "dsm5_text": (
                "Diminished ability to think or concentrate, or indecisiveness, "
                "nearly every day (either by subjective account or as observed by others)."
            ),
            "patient_description": (
                "Having trouble thinking clearly, concentrating on tasks, or making "
                "decisions. You might feel mentally foggy or find it hard to focus."
            ),
            "acoustic_rationale": (
                "Cognitive difficulties are reflected in speech through increased "
                "hesitations, longer and more frequent pauses, reduced pitch variation, "
                "and changes in speech fluency patterns. These indicate processing "
                "difficulties during speech production."
            ),
            "is_core": False,
        },
        "9_recurrent_thoughts_of_death_or_being_suicidal": {
            "name": "Thoughts of Death",
            "criterion": "A9",
            "dsm5_text": (
                "Recurrent thoughts of death (not just fear of dying), recurrent "
                "suicidal ideation without a specific plan, or a suicide attempt "
                "or a specific plan for committing suicide."
            ),
            "patient_description": (
                "Recurring thoughts about death or dying, or thoughts about suicide. "
                "This is a serious symptom that requires professional attention."
            ),
            "acoustic_rationale": (
                "Research has identified specific acoustic patterns associated with "
                "suicidal ideation, including changes in spectral characteristics "
                "and voiced segment patterns. These features require careful "
                "interpretation and research validation."
            ),
            "is_core": False,
            "is_sensitive": True,
        },
    }

    MDD_CRITERIA = {
        "description": (
            "Major Depressive Disorder (MDD) requires at least 5 of the 9 symptoms "
            "to be present during the same 2-week period, with at least one being "
            "either (1) depressed mood or (2) loss of interest/pleasure."
        ),
        "duration": "Symptoms must be present for at least 2 weeks",
        "core_requirement": (
            "At least one of the symptoms must be depressed mood (criterion A1) "
            "or loss of interest/pleasure (criterion A2)"
        ),
        "functional_impact": (
            "The symptoms cause clinically significant distress or impairment "
            "in social, occupational, or other important areas of functioning"
        ),
        "exclusions": (
            "The episode is not attributable to the physiological effects of a "
            "substance or another medical condition"
        ),
    }

    @classmethod
    def get_description(cls, indicator_key: str) -> Optional[dict]:
        """Get full description dictionary for an indicator."""
        return cls.INDICATOR_DESCRIPTIONS.get(indicator_key)

    @classmethod
    def get_dsm5_text(cls, indicator_key: str) -> str:
        """Get official DSM-5 criterion text."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key, {})
        return info.get("dsm5_text", "")

    @classmethod
    def get_patient_description(cls, indicator_key: str) -> str:
        """Get patient-friendly description."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key, {})
        return info.get("patient_description", "")

    @classmethod
    def get_acoustic_rationale(cls, indicator_key: str) -> str:
        """Get explanation of how acoustic features relate to this indicator."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key, {})
        return info.get("acoustic_rationale", "")

    @classmethod
    def get_criterion_code(cls, indicator_key: str) -> str:
        """Get DSM-5 criterion code (e.g., 'A1', 'A2')."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key, {})
        return info.get("criterion", "")

    @classmethod
    def is_core_symptom(cls, indicator_key: str) -> bool:
        """Check if this is a core symptom (depressed mood or loss of interest)."""
        return indicator_key in cls.CORE_INDICATORS

    @classmethod
    def is_sensitive_indicator(cls, indicator_key: str) -> bool:
        """Check if this indicator requires sensitive handling."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key, {})
        return info.get("is_sensitive", False)

    @classmethod
    def get_mdd_status_explanation(cls, active_count: int, has_core: bool) -> str:
        """Get explanation of MDD status based on active symptoms."""
        if active_count >= 5 and has_core:
            return (
                f"**{active_count} indicators elevated** including a core speech-pattern indicator. "
                "This pattern shows elevated acoustic signals across multiple research dimensions. "
                "This is a research pattern flag, not a diagnosis — only a licensed clinician can interpret these signals."
            )
        elif active_count >= 5:
            return (
                f"**{active_count} indicators elevated** but no core speech-pattern indicator (depressed mood or "
                "loss of interest). Acoustic signals are elevated in several dimensions. "
                "Continued monitoring is recommended (research signal, not a diagnosis)."
            )
        elif active_count >= 3:
            return (
                f"**{active_count} indicators elevated**. Some acoustic signals are above typical range. "
                "Consider completing a PHQ-9 self-report for additional context (research signal, not a diagnosis)."
            )
        else:
            return (
                f"**{active_count} indicators elevated**. Current acoustic patterns are within typical "
                "range. Continue regular monitoring to track any changes over time."
            )

    @classmethod
    def format_indicator_card(cls, indicator_key: str, include_acoustic: bool = True) -> str:
        """Format complete indicator information for display."""
        info = cls.INDICATOR_DESCRIPTIONS.get(indicator_key)
        if not info:
            return indicator_key

        parts = [
            f"### {info['name']} ({info['criterion']})",
            "",
            f"**DSM-5 Criterion:** {info['dsm5_text']}",
            "",
            f"**In simpler terms:** {info['patient_description']}",
        ]

        if include_acoustic and info.get("acoustic_rationale"):
            parts.extend([
                "",
                f"**How we measure this:** {info['acoustic_rationale']}"
            ])

        if info.get("is_core"):
            parts.extend([
                "",
                "*This is a core indicator associated with depressive behavioral patterns in research.*"
            ])

        return "\n".join(parts)

    @classmethod
    def get_all_indicators(cls) -> list[str]:
        """Get list of all indicator keys in order."""
        return list(cls.INDICATOR_DESCRIPTIONS.keys())
