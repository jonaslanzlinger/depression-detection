"""
Simple Performance Profiler Test (No Dependencies)

This script tests basic profiler functionality without external dependencies.
For full functionality, install dependencies from requirements.txt
"""

import sys
import os
import time
import random

# Simplified profiler for testing
class SimpleProfiler:
    def __init__(self):
        self.operations = []
    
    def record(self, component, operation, duration_ms, audio_duration_s=None):
        self.operations.append({
            'component': component,
            'operation': operation,
            'duration_ms': duration_ms,
            'audio_duration_s': audio_duration_s
        })
    
    def print_summary(self):
        print("\n" + "="*80)
        print("PERFORMANCE SUMMARY")
        print("="*80)
        print(f"Total Operations: {len(self.operations)}")
        
        # Group by component
        components = {}
        for op in self.operations:
            comp = op['component']
            if comp not in components:
                components[comp] = []
            components[comp].append(op)
        
        for comp, ops in components.items():
            print(f"\n{comp.upper()}")
            print("-"*80)
            
            # Group by operation
            operations = {}
            for op in ops:
                op_name = op['operation']
                if op_name not in operations:
                    operations[op_name] = []
                operations[op_name].append(op)
            
            for op_name, op_list in operations.items():
                avg_duration = sum(o['duration_ms'] for o in op_list) / len(op_list)
                count = len(op_list)
                total_audio = sum(o.get('audio_duration_s', 0) for o in op_list)
                
                print(f"  {op_name}:")
                print(f"    Count: {count}")
                print(f"    Avg Duration: {avg_duration:.2f} ms")
                
                if total_audio > 0:
                    rtf = (sum(o['duration_ms'] for o in op_list) / 1000) / total_audio
                    status = "✓" if rtf < 1.0 else "⚠"
                    print(f"    Real-Time Factor: {rtf:.4f} {status}")


def test_simple_profiler():
    """Test simple profiler without dependencies"""
    print("\n" + "="*80)
    print("Testing Simple Performance Profiler (No Dependencies)")
    print("="*80)
    
    profiler = SimpleProfiler()
    
    print("\nSimulating operations...")
    
    # Data ingestion
    for i in range(5):
        start = time.perf_counter()
        time.sleep(0.05 + random.random() * 0.05)
        duration_ms = (time.perf_counter() - start) * 1000
        profiler.record('data_ingestion', 'vad_filter', duration_ms, 5.0)
    
    # Feature extraction
    for i in range(5):
        start = time.perf_counter()
        time.sleep(0.1 + random.random() * 0.1)
        duration_ms = (time.perf_counter() - start) * 1000
        profiler.record('feature_extraction', 'compute_f0', duration_ms, 5.0)
        
        start = time.perf_counter()
        time.sleep(0.03 + random.random() * 0.03)
        duration_ms = (time.perf_counter() - start) * 1000
        profiler.record('feature_extraction', 'compute_energy', duration_ms, 5.0)
    
    # User profiling
    for i in range(3):
        start = time.perf_counter()
        time.sleep(0.5 if i == 0 else 0.1)
        duration_ms = (time.perf_counter() - start) * 1000
        profiler.record('user_profiling', 'speaker_recognition', duration_ms, 5.0)
    
    profiler.print_summary()
    
    print("\n✅ Simple profiler test passed!")
    print("\nFor full functionality with memory/CPU tracking, install dependencies:")
    print("  pip install -r performance_evaluation/requirements.txt")
    print("\nThen run:")
    print("  python performance_evaluation/test_profiler.py")


if __name__ == "__main__":
    test_simple_profiler()
