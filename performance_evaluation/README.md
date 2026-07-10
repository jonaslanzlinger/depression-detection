# Performance Evaluation Tools

This directory contains comprehensive performance profiling and analysis tools for the Audio Depression Detection System.

## Overview

The performance evaluation suite provides:

1. **System Profiler** - Low-level profiling library for tracking individual operations
2. **Pipeline Profiler** - End-to-end pipeline performance testing
3. **Performance Analyzer** - Analysis and visualization of profiling results
4. **Optimization Guide** - Comprehensive optimization recommendations

## Quick Start

### 1. Run a Performance Test

```bash
# Test with live mode simulation (recommended for production testing)
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/long_depressed_sample_nobreak.wav \
  --duration 60

# Test with batch mode (faster, for development)
python performance_evaluation/pipeline_profiler.py \
  --mode batch \
  --duration 30
```

### 2. Analyze Results

```bash
# Generate comprehensive analysis report
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/pipeline_profile_live.csv \
  --output-dir performance_evaluation/results
```

This will generate:
- `performance_report.txt` - Text report with bottleneck analysis and recommendations
- `timeline.png` - Performance timeline visualization
- `component_breakdown.png` - Component-level breakdown
- `real_time_factor.png` - Real-time performance analysis

### 3. Compare Performance

```bash
# Compare baseline vs optimized performance
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/baseline.csv \
  --compare performance_evaluation/results/optimized.csv \
  --output-dir performance_evaluation/results
```

## Tool Details

### System Profiler (`system_profiler.py`)

Low-level profiling library that tracks:
- Operation duration
- Memory usage
- CPU utilization
- Real-time factors
- Custom metadata

**Usage in Code**:

```python
from performance_evaluation.system_profiler import SystemProfiler

# Initialize profiler
profiler = SystemProfiler()

# Profile an operation
with profiler.start_operation('component_name', 'operation_name') as ctx:
    # Your code here
    result = process_audio(audio_data)
    
    # Add metadata
    ctx.set_audio_duration(5.2)
    ctx.set_metadata({'sample_rate': 16000})

# Get summary
summary = profiler.get_summary()
profiler.print_summary()

# Export results
profiler.export_csv('results.csv')
profiler.export_json('results.json')
```

### Pipeline Profiler (`pipeline_profiler.py`)

End-to-end pipeline testing that simulates:
- Data ingestion (audio collection + VAD filtering)
- Feature extraction (all voice metrics)
- User recognition (speaker identification)
- Data transport (MQTT)
- Database storage

**Command-Line Options**:

```bash
python pipeline_profiler.py [OPTIONS]

Options:
  --mode {live,batch}        Profiling mode (default: live)
  --audio-file PATH          Path to test audio file (optional)
  --duration SECONDS         Test duration in seconds (default: 60)
```

**Modes**:
- **live**: Simulates real-time processing with delays
- **batch**: Fast processing without delays

### Performance Analyzer (`analyze_performance.py`)

Analyzes profiling results and generates reports:

**Features**:
- Bottleneck identification
- Real-time factor analysis
- Component breakdown
- Optimization recommendations
- Visual reports

**Command-Line Options**:

```bash
python analyze_performance.py [OPTIONS]

Required:
  --input PATH               Input CSV/JSON file

Optional:
  --compare PATH [PATH ...]  Additional files to compare
  --output-dir PATH          Output directory (default: results/)
```

## Understanding the Results

### Real-Time Factor (RTF)

RTF = Processing Time / Audio Duration

- **RTF < 1.0**: ✅ Faster than real-time (good!)
- **RTF = 1.0**: Processing at exactly real-time speed
- **RTF > 1.0**: ⚠️ Slower than real-time (bottleneck!)

**Target Values**:
- Data Ingestion: RTF < 0.1
- Feature Extraction: RTF < 0.5
- Overall Pipeline: RTF < 0.5 (for safety margin)

### Performance Metrics

**Duration Metrics**:
- `avg_duration_ms`: Average operation duration
- `min_duration_ms`: Fastest operation
- `max_duration_ms`: Slowest operation
- `total_duration_ms`: Cumulative time

**Resource Metrics**:
- `avg_memory_mb`: Average memory usage
- `avg_cpu_percent`: Average CPU utilization

**Audio Metrics**:
- `audio_duration_s`: Duration of processed audio
- `real_time_factor`: Processing efficiency

## Performance Baseline

Based on existing system logs:

| Component | Avg Duration | RTF | Status |
|-----------|--------------|-----|--------|
| Data Ingestion (VAD) | 40-170ms | 0.01-0.03 | ✅ Excellent |
| Feature Extraction | 4-20s | 0.7-3.0 | ⚠️ Needs optimization |
| User Recognition | 0.14-9.68s | 0.03-1.8 | ⚠️ Variable |
| MQTT Transport | 1-33ms | N/A | ✅ Good |
| Database Write | ~2ms | N/A | ✅ Good |

## Optimization Priorities

### High Priority (Critical)
1. **Feature Extraction Parallelization** - Target: 30-50% speedup
2. **OpenSMILE Optimization** - Target: 20-40% speedup
3. **Feature Caching** - Target: Near-instant recomputation

### Medium Priority (Important)
4. **Speaker Embedding Cache** - Target: Eliminate 9s initialization
5. **Batch VAD Processing** - Target: 20-30% speedup
6. **Selective Feature Computation** - Target: 40-60% speedup

### Low Priority (Nice to have)
7. **Bulk Database Writes** - Target: 50-70% speedup
8. **MQTT Message Batching** - Target: 30-40% speedup

See `OPTIMIZATION_GUIDE.md` for detailed implementation strategies.

## Example Workflow

### Complete Performance Evaluation

```bash
#!/bin/bash

# 1. Run baseline performance test
echo "Running baseline test..."
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/long_depressed_sample_nobreak.wav \
  --duration 120

# 2. Analyze baseline results
echo "Analyzing baseline..."
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/pipeline_profile_live.csv \
  --output-dir performance_evaluation/results/baseline

# 3. Review recommendations
echo "Review: performance_evaluation/results/baseline/performance_report.txt"
cat performance_evaluation/results/baseline/performance_report.txt

# 4. Implement optimizations
echo "Implement optimizations based on recommendations..."

# 5. Run optimized test
echo "Running optimized test..."
python performance_evaluation/pipeline_profiler.py \
  --mode live \
  --audio-file datasets/long_depressed_sample_nobreak.wav \
  --duration 120

# 6. Compare results
echo "Comparing results..."
python performance_evaluation/analyze_performance.py \
  --input performance_evaluation/results/baseline.csv \
  --compare performance_evaluation/results/pipeline_profile_live.csv \
  --output-dir performance_evaluation/results/comparison

echo "Done! Check performance_evaluation/results/comparison/ for comparison reports"
```

## Continuous Monitoring

For production deployments, integrate profiling into the system:

```python
# In your service initialization
from performance_evaluation.system_profiler import SystemProfiler

class VoiceMetricsService:
    def __init__(self):
        self.profiler = SystemProfiler(output_dir="logs/performance")
        
    def process(self, audio_bytes):
        with self.profiler.start_operation('metrics', 'compute') as ctx:
            result = self._compute_metrics(audio_bytes)
            ctx.set_audio_duration(len(audio_bytes) / 16000)
            
        # Periodically export metrics
        if len(self.profiler.metrics) > 100:
            self.profiler.export_json()
```

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Make sure you're in the repository root
cd /path/to/audio-depression-detection

# Install dependencies
pip install psutil pandas matplotlib seaborn librosa torch
```

**2. No Audio File Found**
```bash
# Use synthetic audio if test files aren't available
python pipeline_profiler.py --mode batch --duration 30
# (no --audio-file needed, will generate synthetic audio)
```

**3. Memory Errors**
```bash
# Reduce test duration
python pipeline_profiler.py --mode live --duration 30

# Or use batch mode
python pipeline_profiler.py --mode batch --duration 60
```

## Dependencies

Required Python packages:
- `psutil` - System resource monitoring
- `pandas` - Data analysis
- `matplotlib` - Visualization
- `seaborn` - Statistical visualization
- `numpy` - Numerical operations
- `librosa` - Audio loading (optional, for real audio files)
- `torch` - VAD model (optional, for VAD profiling)

Install all dependencies:
```bash
pip install psutil pandas matplotlib seaborn numpy librosa torch
```

## Contributing

To add new profiling capabilities:

1. Use `SystemProfiler` as the base
2. Add component-specific operations to `PipelineProfiler`
3. Update `PerformanceAnalyzer` for new visualizations
4. Document in `OPTIMIZATION_GUIDE.md`

## Support

For questions or issues:
1. Check `OPTIMIZATION_GUIDE.md` for detailed documentation
2. Review example outputs in `results/` directory
3. Examine the code comments in each tool

## License

Same as the parent project.
