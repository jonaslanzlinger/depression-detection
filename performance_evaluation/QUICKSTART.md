# Quick Start Guide - Performance Evaluation

This guide helps you get started with performance evaluation in under 5 minutes.

## Prerequisites

```bash
# Install dependencies (optional - basic functionality works without)
pip install -r performance_evaluation/requirements.txt
```

If dependencies aren't available, you can still use the basic profiler (see below).

## Option 1: Quick Test (No Dependencies)

Run a simple performance test without installing any dependencies:

```bash
cd /path/to/audio-depression-detection
python performance_evaluation/test_simple.py
```

**Output:**
```
================================================================================
Testing Simple Performance Profiler (No Dependencies)
================================================================================

Simulating operations...

================================================================================
PERFORMANCE SUMMARY
================================================================================
Total Operations: 18

DATA_INGESTION
--------------------------------------------------------------------------------
  vad_filter:
    Count: 5
    Avg Duration: 72.99 ms
    Real-Time Factor: 0.0146 ✓

...
```

## Option 2: Full Pipeline Profiling

### Step 1: Run Performance Test

```bash
# Test with your own audio file
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/long_depressed_sample_nobreak.wav \
  --duration 60

# Or use synthetic audio (no audio file needed)
python performance_evaluation/pipeline_profiler.py \
  --mode batch \
  --duration 30
```

### Step 2: Analyze Results

```bash
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/pipeline_profile_live.csv
```

**This generates:**
- `performance_report.txt` - Detailed analysis with recommendations
- `timeline.png` - Performance over time
- `component_breakdown.png` - Component analysis
- `real_time_factor.png` - Real-time performance

### Step 3: Review Results

```bash
# View the text report
cat performance_evaluation/results/performance_report.txt

# View images (on local machine or download)
# - timeline.png
# - component_breakdown.png
# - real_time_factor.png
```

## Option 3: Analyze Existing Logs

The repository already has performance logs. Analyze them:

```bash
# Create a quick analysis script
python - << 'EOF'
import pandas as pd
import sys

# Load existing performance logs
try:
    ingestion = pd.read_csv('docs/performance_log_DATA_INGESTION_LAYER_save.csv')
    print("\n=== DATA INGESTION PERFORMANCE ===")
    print(f"Average VAD filter time: {ingestion['step_filter_duration'].mean():.4f}s")
    print(f"Average transport time: {ingestion['step_transport_duration'].mean():.4f}s")
    print(f"Real-time factor: {(ingestion['step_filter_duration'].sum() / ingestion['original_audio_duration'].sum()):.4f}")
    
    # Load metrics computation (no header)
    metrics = pd.read_csv('docs/performance_log_METRICS_COMPUTATION_save.csv', header=None)
    metrics.columns = ['timestamp', 'audio_duration', 'computation_duration']
    print("\n=== METRICS COMPUTATION PERFORMANCE ===")
    print(f"Average computation time: {metrics['computation_duration'].mean():.4f}s")
    print(f"Real-time factor: {(metrics['computation_duration'].sum() / metrics['audio_duration'].sum()):.4f}")
    
    # Load user profiling (no header)
    profiling = pd.read_csv('docs/performance_log_USER_PROFILING_save.csv', header=None)
    profiling.columns = ['timestamp', 'audio_duration', 'profiling_duration']
    print("\n=== USER PROFILING PERFORMANCE ===")
    print(f"First call: {profiling['profiling_duration'].iloc[0]:.4f}s (model loading)")
    print(f"Average (after warmup): {profiling['profiling_duration'].iloc[1:].mean():.4f}s")
    print(f"Real-time factor: {(profiling['profiling_duration'].sum() / profiling['audio_duration'].sum()):.4f}")
    
except Exception as e:
    print(f"Error: {e}")
    print("Make sure you're in the repository root directory")
    sys.exit(1)
EOF
```

**Expected Output:**
```
=== DATA INGESTION PERFORMANCE ===
Average VAD filter time: 0.0603s
Average transport time: 0.0037s
Real-time factor: 0.0089

=== METRICS COMPUTATION PERFORMANCE ===
Average computation time: 5.7373s
Real-time factor: 0.8869

=== USER PROFILING PERFORMANCE ===
First call: 9.6805s (model loading)
Average (after warmup): 0.3842s
Real-time factor: 0.0590
```

## Understanding the Results

### Real-Time Factor (RTF)

**RTF = Processing Time / Audio Duration**

| RTF | Meaning | Status |
|-----|---------|--------|
| < 0.5 | Much faster than real-time | ✅ Excellent |
| 0.5 - 1.0 | Near real-time | ⚠️ OK, but no safety margin |
| > 1.0 | Slower than real-time | 🔴 Bottleneck! |

### Current Performance Summary

Based on existing logs:

| Component | RTF | Status | Priority |
|-----------|-----|--------|----------|
| Data Ingestion | 0.009 | ✅ Excellent | Low |
| User Profiling | 0.059 | ✅ Excellent | Medium (init time) |
| Metrics Computation | 0.887 | ⚠️ Near real-time | 🔴 **HIGH** |
| **Overall** | **~0.95** | **⚠️ Near real-time** | **Optimize** |

### Key Findings

1. **Data Ingestion is fast** ✅
   - VAD filtering: ~60ms per segment
   - Already optimized, no action needed

2. **Metrics Computation is the bottleneck** ⚠️
   - ~5.7 seconds per segment
   - Sometimes exceeds real-time
   - **Action: Optimize feature extraction**

3. **User Profiling needs initialization** ⚠️
   - First call: 9.68 seconds
   - Subsequent: 0.38 seconds
   - **Action: Pre-load model on startup**

## Next Steps

### Immediate Actions

1. **Read the full analysis**
   ```bash
   cat performance_evaluation/PERFORMANCE_REPORT.md
   ```

2. **Review optimization strategies**
   ```bash
   cat performance_evaluation/OPTIMIZATION_GUIDE.md
   ```

3. **Understand the tools**
   ```bash
   cat performance_evaluation/README.md
   ```

### Implement Quick Wins

Top 3 optimizations for immediate impact:

1. **Pre-load models** (5 min implementation)
   - Eliminates 30s cold start
   - See OPTIMIZATION_GUIDE.md, Strategy 3.2

2. **Parallel feature extraction** (2 hours implementation)
   - 30-50% speedup expected
   - See OPTIMIZATION_GUIDE.md, Strategy 1.1

3. **OpenSMILE optimization** (1 hour implementation)
   - 20-40% speedup expected
   - See OPTIMIZATION_GUIDE.md, Strategy 1.2

### Continuous Monitoring

Set up performance monitoring:

```python
# Add to your service
from performance_evaluation.system_profiler import SystemProfiler

class MyService:
    def __init__(self):
        self.profiler = SystemProfiler()
    
    def process(self, data):
        with self.profiler.start_operation('my_service', 'process') as ctx:
            result = self._do_work(data)
            ctx.set_audio_duration(len(data) / 16000)
        return result
```

## Troubleshooting

### "Module not found" errors

```bash
# Option A: Install dependencies
pip install -r performance_evaluation/requirements.txt

# Option B: Use simple profiler (no dependencies)
python performance_evaluation/test_simple.py
```

### "File not found" errors

```bash
# Make sure you're in the repository root
cd /path/to/audio-depression-detection
pwd  # Should end in: audio-depression-detection

# Run from root directory
python performance_evaluation/...
```

### No audio file available

```bash
# Use batch mode with synthetic audio
python performance_evaluation/pipeline_profiler.py \
  --mode batch \
  --duration 30
```

## Support

- **Documentation**: See `performance_evaluation/README.md`
- **Optimization Guide**: See `performance_evaluation/OPTIMIZATION_GUIDE.md`
- **Performance Report**: See `performance_evaluation/PERFORMANCE_REPORT.md`

## Summary

✅ **What we know:**
- System is near real-time capable (RTF ~0.95)
- Feature extraction is the bottleneck (96% of time)
- Clear optimization paths identified

✅ **What to do:**
1. Pre-load models → eliminate cold start
2. Parallelize features → 30-50% faster
3. Optimize OpenSMILE → 20-40% faster
4. **Target RTF: < 0.5** (production-ready)

✅ **Tools available:**
- Pipeline profiler for end-to-end testing
- Performance analyzer for bottleneck identification
- Comprehensive optimization guide
- Existing performance data already analyzed

**Get started now:**
```bash
python performance_evaluation/test_simple.py
```
