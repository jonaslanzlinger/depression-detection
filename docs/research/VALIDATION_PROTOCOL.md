# IHearYou Validation Protocol

**Document Version:** 1.0
**Date:** January 2026
**Status:** Draft - Pending PI Review

## 1. Overview

This document defines the validation protocol for the IHearYou depression detection system. The system is designed as a **screening and monitoring tool**, not a diagnostic device.

### 1.1 Scope

- Audio feature extraction validation
- Speaker verification accuracy
- Depression indicator correlation with PHQ-9
- System reliability and uptime

### 1.2 Key Principle

> "We are building a screening and monitoring tool, not a diagnostic device. Our outputs indicate features associated with depression, not depression itself."

## 2. Ground Truth Collection

### 2.1 PHQ-9 Administration Protocol

**Frequency:** Weekly during pilot study

**Collection Method:**
1. Participants complete PHQ-9 via secure web interface
2. Timestamp recorded for correlation with audio features
3. Data stored encrypted with participant ID only (no PII linkage)

**PHQ-9 Scoring:**
| Score Range | Severity |
|-------------|----------|
| 0-4 | Minimal |
| 5-9 | Mild |
| 10-14 | Moderate |
| 15-19 | Moderately Severe |
| 20-27 | Severe |

### 2.2 Enrollment Audio Samples

**Purpose:** Baseline feature extraction and speaker verification enrollment

**Requirements:**
- Minimum 5 minutes of continuous speech per participant
- Recorded in home environment (ecological validity)
- Reading passage + spontaneous speech
- Multiple sessions across different times of day

## 3. Feature Validation

### 3.1 Prosodic Features

| Feature | Extraction Method | Expected Depression Correlation | Validation Metric |
|---------|-------------------|--------------------------------|-------------------|
| Pitch (F0) Mean | RAPT algorithm | Negative | Pearson r |
| Pitch Variability | Standard deviation | Negative | Pearson r |
| Speech Rate | Syllables/second | Negative | Pearson r |
| Pause Duration | Energy threshold | Positive | Pearson r |
| Pause Frequency | Per utterance | Positive | Pearson r |

### 3.2 Voice Quality Features

| Feature | Extraction Method | Expected Depression Correlation | Validation Metric |
|---------|-------------------|--------------------------------|-------------------|
| Jitter | Period-to-period variation | Positive | Pearson r |
| Shimmer | Amplitude variation | Positive | Pearson r |
| HNR | Harmonics-to-noise ratio | Negative | Pearson r |
| Formant Energy | F1-F3 analysis | Variable | Pearson r |

### 3.3 Temporal Features

| Feature | Extraction Method | Expected Depression Correlation | Validation Metric |
|---------|-------------------|--------------------------------|-------------------|
| Utterance Duration | VAD segmentation | Negative | Pearson r |
| Response Latency | Turn-taking analysis | Positive | Pearson r |
| Talk Time | Total speech vs silence | Negative | Pearson r |

## 4. Validation Metrics

### 4.1 Statistical Requirements

**Minimum Sample Size:** 50 participants (power analysis for r=0.3, α=0.05, power=0.80)

**Required Correlations:**
- PHQ-9 correlation: r ≥ 0.3 for at least 3 core features
- Test-retest reliability: ICC ≥ 0.7 for extracted features
- Internal consistency: Cronbach's α ≥ 0.7 for composite score

### 4.2 Classification Performance (Screening Threshold)

**Target Performance for PHQ-9 ≥ 10 Detection:**
- Sensitivity: ≥ 80% (minimize false negatives)
- Specificity: ≥ 70% (acceptable false positive rate for screening)
- NPV: ≥ 90% (high confidence when screening negative)

**Interpretation:**
- This is a screening tool to identify individuals who may benefit from clinical assessment
- Not intended for diagnosis or treatment decisions

### 4.3 Speaker Verification

**Verification Metrics:**
- EER (Equal Error Rate): ≤ 5%
- False Acceptance Rate at 1% FRR: ≤ 2%
- Enrollment samples required: ≥ 30 seconds clean speech

## 5. Validation Phases

### 5.1 Phase 1: Technical Validation (Current)

**Duration:** 4 weeks

**Objectives:**
- [ ] Audio capture quality verification
- [ ] Feature extraction accuracy
- [ ] Speaker verification performance
- [ ] System reliability

**Success Criteria:**
- Audio SNR ≥ 20 dB
- Feature extraction success rate ≥ 95%
- Speaker verification EER ≤ 5%
- System uptime ≥ 99%

### 5.2 Phase 2: Pilot Study

**Duration:** 8 weeks

**Participants:** 20-30 volunteers

**Objectives:**
- [ ] Collect baseline and longitudinal data
- [ ] Validate feature-PHQ9 correlations
- [ ] Refine speaker verification
- [ ] User experience feedback

**Success Criteria:**
- At least 3 features with r ≥ 0.3 correlation to PHQ-9
- Participant retention ≥ 80%
- Data collection compliance ≥ 70%

### 5.3 Phase 3: Validation Study

**Duration:** 12 weeks

**Participants:** 50-100 participants (stratified by PHQ-9 severity)

**Objectives:**
- [ ] Full feature validation
- [ ] Screening threshold optimization
- [ ] Multi-household differentiation
- [ ] Longitudinal tracking validation

**Success Criteria:**
- Sensitivity ≥ 80%, Specificity ≥ 70% for PHQ-9 ≥ 10
- Test-retest ICC ≥ 0.7
- Speaker verification in multi-occupant households

## 6. Data Collection Requirements

### 6.1 Per-Participant Data

| Data Type | Collection Frequency | Storage |
|-----------|---------------------|---------|
| Audio samples | Continuous (VAD-gated) | Encrypted, 30-day retention |
| Extracted features | Per audio chunk | Long-term (anonymized) |
| PHQ-9 scores | Weekly | Long-term (anonymized) |
| Speaker embeddings | Enrollment + periodic update | Encrypted |
| System telemetry | Continuous | 90-day retention |

### 6.2 Minimum Data Requirements

| Metric | Minimum | Target |
|--------|---------|--------|
| Audio per participant | 30 min/week | 60 min/week |
| Study duration | 4 weeks | 8 weeks |
| PHQ-9 assessments | 4 per participant | 8 per participant |

## 7. Quality Assurance

### 7.1 Audio Quality Checks

**Automated Checks (per chunk):**
- [ ] SNR ≥ 15 dB
- [ ] No clipping (< 0.1% samples)
- [ ] DC offset within bounds
- [ ] Speech presence (VAD positive)

**Manual Review (sample basis):**
- [ ] 5% of chunks reviewed for quality
- [ ] Speaker verification accuracy spot-check
- [ ] Environmental noise assessment

### 7.2 Feature Quality Checks

**Automated Checks:**
- [ ] Feature values within expected ranges
- [ ] No missing values in required features
- [ ] Temporal consistency (no sudden jumps)

### 7.3 Data Integrity

- [ ] Participant ID mapping verified
- [ ] Timestamp synchronization checked
- [ ] PHQ-9 completion validation

## 8. Analysis Plan

### 8.1 Primary Analyses

1. **Correlation Analysis**
   - Pearson correlation between features and PHQ-9 total score
   - Partial correlations controlling for age, gender, time of day

2. **Classification Analysis**
   - ROC curve for PHQ-9 ≥ 10 detection
   - Sensitivity/specificity at various thresholds
   - Optimal screening threshold selection (maximize NPV)

3. **Longitudinal Analysis**
   - Mixed-effects models for feature changes over time
   - Correlation between feature changes and PHQ-9 changes

### 8.2 Secondary Analyses

1. **Feature Selection**
   - LASSO regression for feature importance
   - Random forest feature ranking

2. **Subgroup Analysis**
   - By depression severity
   - By age group
   - By household composition

## 9. Reporting

### 9.1 Weekly Reports

- Audio collection statistics
- Feature extraction success rate
- Speaker verification performance
- System health metrics

### 9.2 Study Completion Report

- Full statistical analysis
- Validation metrics vs. targets
- Recommendations for production
- Limitations and future work

## 10. Ethical Considerations

See separate documents:
- `CONSENT_DISCLOSURE.md` - Participant consent requirements
- `INCIDENTAL_FINDINGS_PROTOCOL.md` - Safety procedures

## Appendices

### A. PHQ-9 Questionnaire

[Standard PHQ-9 instrument - not reproduced here for copyright]

### B. Feature Extraction Specifications

See `docs/research/FEATURE_EXTRACTION_SPECS.md`

### C. Statistical Power Analysis

| Effect Size (r) | α | Power | Required N |
|-----------------|---|-------|------------|
| 0.3 | 0.05 | 0.80 | 84 |
| 0.3 | 0.05 | 0.90 | 112 |
| 0.4 | 0.05 | 0.80 | 46 |
| 0.4 | 0.05 | 0.90 | 62 |
