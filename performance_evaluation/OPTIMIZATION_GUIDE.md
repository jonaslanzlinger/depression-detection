# Audio Depression Detection System - Performance Optimization Guide

## Executive Summary

This document provides comprehensive performance evaluation results and optimization recommendations for the Audio Depression Detection System, with special focus on real-world deployment (live mode) performance.

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Performance Evaluation Results](#performance-evaluation-results)
3. [Bottleneck Analysis](#bottleneck-analysis)
4. [Optimization Strategies](#optimization-strategies)
5. [Live Mode Considerations](#live-mode-considerations)
6. [Implementation Roadmap](#implementation-roadmap)

---

## System Architecture Overview

### Data Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DATA INGESTION LAYER                                         │
│    - Audio collection (microphone/file)                         │
│    - VAD filtering (Silero VAD)                                 │
│    - Voice activity detection                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ MQTT
┌────────────────────────▼────────────────────────────────────────┐
│ 2. PROCESSING LAYER - User Profiling                            │
│    - Speaker recognition (Resemblyzer D-vectors)                │
│    - User identification                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 3. PROCESSING LAYER - Metrics Computation                       │
│    - OpenSMILE features (ComParE, GeMAPS)                       │
│    - Librosa features                                            │
│    - Praat/Parselmouth prosody                                  │
│    - Custom acoustic features (20+ metrics)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ MongoDB
┌────────────────────────▼────────────────────────────────────────┐
│ 4. TEMPORAL CONTEXT MODELING LAYER                              │
│    - Daily aggregation                                           │
│    - EMA smoothing                                              │
│    - Context windows (morning/evening/general)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 5. ANALYSIS LAYER                                                │
│    - Feature-to-indicator mapping (DSM-5)                       │
│    - Baseline normalization                                      │
│    - Depression indicator scoring                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 6. DASHBOARD LAYER                                               │
│    - Visualization (Streamlit)                                   │
│    - PHQ-9 calibration                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance Evaluation Results

### Current Performance Baseline

Based on analysis of existing performance logs (`docs/performance_log_*.csv`):

#### Data Ingestion Layer
- **Average processing time per segment**: ~50-100ms
- **VAD filtering overhead**: ~40-170ms per segment
- **Audio collection**: < 1ms (negligible)
- **MQTT transport**: ~1-33ms per message
- **Real-time factor**: ~0.01-0.03 (faster than real-time ✓)

#### Metrics Computation (Voice Metrics)
- **Average computation time**: 4-20 seconds per segment
- **Audio duration processed**: 5-12 seconds per segment
- **Real-time factor**: ~0.7-3.0 (varies, sometimes slower than real-time ⚠)
- **Peak computation time**: Up to 20 seconds for complex segments

#### User Profiling (Speaker Recognition)
- **Average recognition time**: 0.14-9.68 seconds per segment
- **Real-time factor**: ~0.03-1.8
- **First recognition**: ~9.68s (model loading)
- **Subsequent recognitions**: ~0.14-0.90s

### Key Findings

1. ✅ **Data Ingestion is highly optimized** - processes audio faster than real-time
2. ⚠️ **Metrics Computation is the main bottleneck** - can be slower than real-time
3. ⚠️ **User Profiling has initialization overhead** - first call is significantly slower
4. ✅ **Overall pipeline achieves near-real-time performance** with proper optimization

---

## Bottleneck Analysis

### Critical Bottlenecks (Ranked by Impact)

#### 1. Feature Extraction - Voice Metrics Computation (HIGH PRIORITY)
**Impact**: Can take 4-20 seconds per segment

**Root Causes**:
- Multiple heavy libraries (OpenSMILE, Librosa, Parselmouth)
- Sequential processing of 20+ acoustic features
- No caching or parallelization
- Three separate OpenSMILE extractions (LLD ComParE, LLD GeMAPS, HLD ComParE)

**Evidence from code**:
```python
# MetricsComputationService.py lines 42-58
# Initializes 3 separate OpenSMILE models
self.smile_LLD_ComParE_2016 = opensmile.Smile(...)
self.smile_LLD_GeMAPSv01b = opensmile.Smile(...)
self.smile_HLD_ComParE_2016 = opensmile.Smile(...)
```

#### 2. Speaker Recognition - Initial Model Loading (MEDIUM PRIORITY)
**Impact**: First call takes ~9.68s, subsequent calls ~0.14-0.90s

**Root Causes**:
- Resemblyzer model loaded on-demand
- D-vector computation for each segment
- No embedding cache

#### 3. VAD Processing - Silero VAD Model (MEDIUM PRIORITY)
**Impact**: 40-170ms per segment, variable performance

**Root Causes**:
- Per-chunk VAD inference (512 samples)
- PyTorch model overhead
- No batch processing

#### 4. MongoDB Write Operations (LOW PRIORITY)
**Impact**: ~2ms per write (acceptable)

**Root Causes**:
- Individual document writes
- No bulk operations

---

## Optimization Strategies

### 1. Voice Metrics Computation Optimizations

#### Strategy 1.1: Parallel Feature Extraction
**Expected Improvement**: 30-50% reduction in computation time

**Implementation**:
```python
# Use multiprocessing or threading for independent feature groups
from concurrent.futures import ThreadPoolExecutor

feature_groups = [
    ('f0_features', extract_f0_features),
    ('energy_features', extract_energy_features),
    ('spectral_features', extract_spectral_features),
    # ... more groups
]

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(fn, audio_data): name 
               for name, fn in feature_groups}
    results = {name: future.result() 
               for future, name in futures.items()}
```

**Trade-offs**:
- ✅ Significant speedup
- ⚠️ Increased memory usage
- ⚠️ Requires thread-safe feature extractors

#### Strategy 1.2: Reduce OpenSMILE Redundancy
**Expected Improvement**: 20-40% reduction in OpenSMILE processing

**Implementation**:
```python
# Combine feature sets or use only necessary features
# Instead of 3 separate extractions, use 1-2 optimized sets
self.smile_combined = opensmile.Smile(
    feature_set=opensmile.FeatureSet.eGeMAPSv02,
    feature_level=opensmile.FeatureLevel.Functionals
)
```

**Trade-offs**:
- ✅ Faster processing
- ⚠️ May need to verify feature completeness
- ⚠️ Requires revalidation of ML models

#### Strategy 1.3: Feature Computation Caching
**Expected Improvement**: Near-zero recomputation time for repeated audio

**Implementation**:
```python
import hashlib
from functools import lru_cache

class MetricsComputationService:
    def __init__(self):
        self.feature_cache = {}
    
    def compute(self, audio_bytes, user_id, metadata=None):
        # Hash audio for cache key
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        
        if audio_hash in self.feature_cache:
            return self.feature_cache[audio_hash]
        
        # Compute features...
        metrics = self._compute_features(audio_bytes)
        
        # Cache result
        self.feature_cache[audio_hash] = metrics
        return metrics
```

**Trade-offs**:
- ✅ Eliminates recomputation
- ⚠️ Increased memory usage
- ⚠️ Only beneficial for repeated audio

#### Strategy 1.4: Selective Feature Computation
**Expected Improvement**: 40-60% reduction by computing only necessary features

**Implementation**:
```python
# Add configuration for feature selection
ACTIVE_FEATURES = {
    'f0_avg': True,
    'f0_std': True,
    'hnr_mean': True,
    'jitter': True,
    'shimmer': True,
    # ... enable only features used by analysis layer
    'temporal_modulation': False,  # Disable if not used
    'spectral_modulation': False,  # Disable if not used
}

# Only compute enabled features
if ACTIVE_FEATURES.get('f0_avg', True):
    f0_avg = get_f0_avg(...)
```

**Trade-offs**:
- ✅ Significant speedup
- ✅ Reduced resource usage
- ⚠️ Requires analysis of feature importance
- ⚠️ May impact model accuracy

### 2. VAD Processing Optimizations

#### Strategy 2.1: Batch VAD Processing
**Expected Improvement**: 20-30% reduction in VAD overhead

**Implementation**:
```python
# Process multiple frames in batch
batch_size = 10
frames = []

for chunk in audio_chunks:
    frames.append(chunk)
    
    if len(frames) >= batch_size:
        # Batch inference
        batch_tensor = torch.stack(frames)
        confidences = self.vad_model(batch_tensor, sample_rate)
        
        # Process results
        for confidence in confidences:
            # ... handle each result
        
        frames = []
```

**Trade-offs**:
- ✅ Better GPU utilization
- ✅ Reduced per-frame overhead
- ⚠️ Increased latency
- ⚠️ Not suitable for strict real-time requirements

#### Strategy 2.2: Use Lightweight VAD Alternative
**Expected Improvement**: 50-70% reduction in VAD time

**Implementation**:
```python
# Replace Silero VAD with WebRTC VAD or energy-based VAD
import webrtcvad

vad = webrtcvad.Vad()
vad.set_mode(3)  # Aggressive mode

is_speech = vad.is_speech(audio_frame, sample_rate)
```

**Trade-offs**:
- ✅ Much faster
- ✅ Lower resource usage
- ⚠️ Lower accuracy
- ⚠️ May miss some speech segments

### 3. Speaker Recognition Optimizations

#### Strategy 3.1: Embedding Cache
**Expected Improvement**: Near-instant recognition for known users

**Implementation**:
```python
class UserProfilingService:
    def __init__(self):
        self.embedding_cache = {}
        self.model = None
    
    def recognize_user(self, audio_bytes):
        # Check cache first
        if user_id in self.embedding_cache:
            embedding = self.compute_embedding(audio_bytes)
            return self._match_embedding(embedding)
        
        # Otherwise compute and cache
        # ...
```

**Trade-offs**:
- ✅ Eliminates model loading per request
- ✅ Fast recognition
- ⚠️ Memory usage for cached embeddings
- ⚠️ Cache invalidation strategy needed

#### Strategy 3.2: Lazy Model Loading
**Expected Improvement**: Faster startup, on-demand resource allocation

**Implementation**:
```python
class UserProfilingService:
    def __init__(self):
        self._model = None
    
    @property
    def model(self):
        if self._model is None:
            self._model = self._load_model()
        return self._model
```

### 4. Database Optimizations

#### Strategy 4.1: Bulk Writes
**Expected Improvement**: 50-70% reduction in database overhead

**Implementation**:
```python
# Batch multiple metrics into single write
def save_metrics_bulk(self, metrics_list):
    if len(metrics_list) >= self.batch_size:
        self.collection.insert_many(metrics_list)
        metrics_list.clear()
```

**Trade-offs**:
- ✅ Reduced database load
- ✅ Better throughput
- ⚠️ Increased latency
- ⚠️ Risk of data loss on crash

#### Strategy 4.2: Asynchronous Writes
**Expected Improvement**: Non-blocking writes, better responsiveness

**Implementation**:
```python
import asyncio

async def save_metrics_async(self, metrics):
    await self.collection.insert_one(metrics)
```

### 5. MQTT Processing Optimizations

#### Strategy 5.1: Worker Thread Pool
**Current Implementation**: ✅ Already implemented (lines 14-15 in MqttConsumerAdapter.py)

```python
self.worker_thread = threading.Thread(target=self._worker, daemon=True)
```

**Recommendation**: Monitor queue depth and add multiple workers if needed

#### Strategy 5.2: Message Batching
**Expected Improvement**: 30-40% reduction in handler overhead

**Implementation**:
```python
def _worker(self):
    while self.is_running:
        messages = []
        
        # Collect batch of messages
        for _ in range(self.batch_size):
            try:
                msg = self.message_queue.get(timeout=0.1)
                messages.append(msg)
            except queue.Empty:
                break
        
        if messages:
            self._process_batch(messages)
```

---

## Live Mode Considerations

### Real-Time Requirements

For live deployment, the system must process audio **faster than real-time**:

**Real-Time Factor (RTF)** = Processing Time / Audio Duration

- **Target RTF**: < 0.5 (2x faster than real-time for safety margin)
- **Acceptable RTF**: < 1.0 (at least real-time)
- **Current RTF**: 0.7-3.0 (variable, sometimes exceeds real-time)

### Memory Management for Live Mode

#### Current Memory Usage
- Data Ingestion: ~50-100 MB
- Metrics Computation: ~500-2000 MB (2 GB limit set in docker-compose.yml)
- User Profiling: ~200-500 MB

#### Optimization Strategies

1. **Streaming Processing**: Process audio in small chunks, discard after processing
2. **Buffer Management**: Clear buffers after VAD segments are extracted
3. **Model Sharing**: Load models once globally, not per-request
4. **Garbage Collection**: Explicit cleanup of large numpy arrays

```python
import gc

def process_segment(self, audio_data):
    # Process
    results = self.extract_features(audio_data)
    
    # Cleanup
    del audio_data
    gc.collect()
    
    return results
```

### Network Latency Considerations

#### MQTT Communication
- **Current**: ~1-33ms per message (acceptable)
- **Optimization**: Use QoS 0 for non-critical messages
- **Monitoring**: Track message queue depth

#### MongoDB Operations
- **Current**: ~2ms per write (acceptable)
- **Optimization**: Use local MongoDB instance, enable connection pooling
- **Bulk writes**: For batch processing scenarios

### CPU/GPU Utilization

#### Current State
- CPU usage varies (based on logs)
- No GPU acceleration currently used

#### Recommendations

1. **GPU Acceleration**: Use CUDA for:
   - VAD model inference (Silero VAD)
   - Feature extraction (some operations)
   - Speaker recognition (Resemblyzer)

2. **Multi-core Processing**: Parallelize independent operations
   - Feature extraction groups
   - Multiple audio segments

3. **Process Priority**: Set higher priority for real-time components

```python
import os
os.nice(-10)  # Higher priority (requires privileges)
```

---

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1-2)
**Target**: 30-40% performance improvement

- [ ] Implement feature computation caching
- [ ] Add bulk database writes
- [ ] Optimize OpenSMILE feature sets (reduce redundancy)
- [ ] Implement speaker embedding cache
- [ ] Add performance monitoring to all components

### Phase 2: Architectural Improvements (Week 3-4)
**Target**: Additional 20-30% improvement

- [ ] Parallel feature extraction (threading/multiprocessing)
- [ ] Batch VAD processing
- [ ] Asynchronous database writes
- [ ] MQTT message batching
- [ ] Memory optimization (streaming processing)

### Phase 3: Advanced Optimizations (Week 5-6)
**Target**: Additional 10-20% improvement

- [ ] GPU acceleration for heavy operations
- [ ] Selective feature computation (based on importance analysis)
- [ ] Consider lightweight VAD alternative
- [ ] Profile-guided optimization
- [ ] Load testing and stress testing

### Phase 4: Production Hardening (Week 7-8)
**Target**: Stability and monitoring

- [ ] Comprehensive performance monitoring dashboard
- [ ] Alerting for performance degradation
- [ ] Automated performance regression testing
- [ ] Documentation and runbooks
- [ ] Capacity planning and scaling guidelines

---

## Monitoring and Measurement

### Key Performance Indicators (KPIs)

1. **Real-Time Factor (RTF)**: Processing time / Audio duration
   - Target: < 0.5
   - Alert threshold: > 0.8

2. **End-to-End Latency**: Time from audio input to metrics stored
   - Target: < 5 seconds
   - Alert threshold: > 10 seconds

3. **Memory Usage**: Per-component memory consumption
   - Target: < 1 GB per service
   - Alert threshold: > 1.5 GB

4. **CPU Usage**: Per-component CPU utilization
   - Target: 40-60% average
   - Alert threshold: > 80%

5. **Throughput**: Segments processed per minute
   - Target: > 10 segments/minute
   - Alert threshold: < 5 segments/minute

### Continuous Monitoring

Use the provided performance evaluation tools:

```bash
# Run pipeline profiler
python performance_evaluation/pipeline_profiler.py --mode live --duration 300

# Analyze results
python performance_evaluation/analyze_performance.py --input results/pipeline_profile_live.csv

# Compare before/after
python performance_evaluation/analyze_performance.py \
  --input results/baseline.csv \
  --compare results/optimized.csv
```

---

## Conclusion

The Audio Depression Detection System currently achieves near-real-time performance for most operations but has room for significant optimization, particularly in the feature extraction pipeline. By implementing the recommended optimizations in phases, the system can achieve:

- ✅ **2x faster processing** (RTF < 0.5)
- ✅ **50% reduction in memory usage**
- ✅ **Reliable real-time performance** for live deployment
- ✅ **Better resource utilization** (CPU, memory, network)

The provided performance evaluation tools enable continuous monitoring and measurement of optimization efforts, ensuring data-driven decision-making throughout the optimization process.

---

## Appendix: Performance Evaluation Tools

### Tool 1: System Profiler
**File**: `performance_evaluation/system_profiler.py`
**Usage**: Base profiling library for tracking operations

### Tool 2: Pipeline Profiler
**File**: `performance_evaluation/pipeline_profiler.py`
**Usage**: End-to-end pipeline performance testing

### Tool 3: Performance Analyzer
**File**: `performance_evaluation/analyze_performance.py`
**Usage**: Analyze and visualize performance metrics

### Example Workflow

```bash
# 1. Run baseline test
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/test_audio.wav \
  --duration 60

# 2. Analyze results
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/pipeline_profile_live.csv

# 3. Implement optimizations

# 4. Run comparison test
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/test_audio.wav \
  --duration 60

# 5. Compare results
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/pipeline_profile_live.csv \
  --compare performance_evaluation/results/optimized_profile.csv
```

---

*Document Version: 1.0*
*Last Updated: 2025-12-26*
