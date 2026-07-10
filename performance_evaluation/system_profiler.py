"""
System Performance Profiler for Audio Depression Detection System

This module provides comprehensive performance profiling capabilities for the entire
audio processing pipeline, including data ingestion, VAD filtering, feature extraction,
and storage operations.

Supports both file-based testing and live system monitoring.
"""

import time
import json
import csv
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import psutil
import threading


@dataclass
class PerformanceMetric:
    """Represents a single performance measurement"""
    timestamp: str
    component: str
    operation: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    audio_duration_s: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        d = asdict(self)
        if d['metadata'] is None:
            d['metadata'] = {}
        return d


class SystemProfiler:
    """
    Main profiler class for monitoring system performance across all components.
    
    Features:
    - Real-time performance tracking
    - Memory and CPU monitoring
    - Component-level breakdown
    - Live vs batch mode support
    - Export to CSV/JSON
    """
    
    def __init__(self, output_dir: str = "performance_evaluation/results"):
        """
        Initialize the system profiler.
        
        Args:
            output_dir: Directory to store performance results
        """
        self.output_dir = output_dir
        self.metrics: List[PerformanceMetric] = []
        self.process = psutil.Process()
        self._lock = threading.Lock()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Session metadata
        self.session_start = datetime.now(timezone.utc)
        self.session_id = self.session_start.strftime("%Y%m%d_%H%M%S")
        
    def start_operation(self, component: str, operation: str) -> 'OperationContext':
        """
        Start tracking a specific operation.
        
        Args:
            component: Component name (e.g., 'data_ingestion', 'vad_filter', 'feature_extraction')
            operation: Operation name (e.g., 'collect', 'filter', 'compute_metrics')
            
        Returns:
            OperationContext that should be used with 'with' statement
        """
        return OperationContext(self, component, operation)
    
    def record_metric(
        self,
        component: str,
        operation: str,
        duration_ms: float,
        audio_duration_s: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a performance metric.
        
        Args:
            component: Component name
            operation: Operation name
            duration_ms: Duration in milliseconds
            audio_duration_s: Duration of processed audio in seconds (if applicable)
            metadata: Additional metadata
        """
        with self._lock:
            try:
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                cpu_percent = self.process.cpu_percent(interval=None)
            except:
                memory_mb = 0
                cpu_percent = 0
                
            metric = PerformanceMetric(
                timestamp=datetime.now(timezone.utc).isoformat(),
                component=component,
                operation=operation,
                duration_ms=duration_ms,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                audio_duration_s=audio_duration_s,
                metadata=metadata or {}
            )
            self.metrics.append(metric)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of performance metrics.
        
        Returns:
            Dictionary containing performance summary statistics
        """
        if not self.metrics:
            return {
                "error": "No metrics recorded",
                "session_id": self.session_id
            }
        
        # Group metrics by component and operation
        component_stats = {}
        
        for metric in self.metrics:
            key = f"{metric.component}:{metric.operation}"
            if key not in component_stats:
                component_stats[key] = {
                    "count": 0,
                    "total_duration_ms": 0,
                    "min_duration_ms": float('inf'),
                    "max_duration_ms": 0,
                    "total_audio_duration_s": 0,
                    "memory_samples": [],
                    "cpu_samples": []
                }
            
            stats = component_stats[key]
            stats["count"] += 1
            stats["total_duration_ms"] += metric.duration_ms
            stats["min_duration_ms"] = min(stats["min_duration_ms"], metric.duration_ms)
            stats["max_duration_ms"] = max(stats["max_duration_ms"], metric.duration_ms)
            stats["memory_samples"].append(metric.memory_mb)
            stats["cpu_samples"].append(metric.cpu_percent)
            
            if metric.audio_duration_s:
                stats["total_audio_duration_s"] += metric.audio_duration_s
        
        # Calculate averages and real-time factors
        summary = {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "total_metrics": len(self.metrics),
            "components": {}
        }
        
        for key, stats in component_stats.items():
            component, operation = key.split(":", 1)
            
            avg_duration_ms = stats["total_duration_ms"] / stats["count"]
            avg_memory_mb = sum(stats["memory_samples"]) / len(stats["memory_samples"])
            avg_cpu = sum(stats["cpu_samples"]) / len(stats["cpu_samples"])
            
            # Calculate real-time factor (processing time / audio duration)
            # Values < 1.0 mean faster than real-time
            real_time_factor = None
            if stats["total_audio_duration_s"] > 0:
                real_time_factor = (stats["total_duration_ms"] / 1000) / stats["total_audio_duration_s"]
            
            if component not in summary["components"]:
                summary["components"][component] = {}
            
            summary["components"][component][operation] = {
                "count": stats["count"],
                "avg_duration_ms": round(avg_duration_ms, 2),
                "min_duration_ms": round(stats["min_duration_ms"], 2),
                "max_duration_ms": round(stats["max_duration_ms"], 2),
                "total_duration_ms": round(stats["total_duration_ms"], 2),
                "avg_memory_mb": round(avg_memory_mb, 2),
                "avg_cpu_percent": round(avg_cpu, 2),
                "total_audio_duration_s": round(stats["total_audio_duration_s"], 2),
                "real_time_factor": round(real_time_factor, 4) if real_time_factor else None
            }
        
        return summary
    
    def export_csv(self, filename: Optional[str] = None) -> str:
        """
        Export metrics to CSV file.
        
        Args:
            filename: Optional custom filename
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            filename = f"performance_metrics_{self.session_id}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', newline='') as f:
            if not self.metrics:
                return filepath
                
            # Get all possible metadata keys
            metadata_keys = set()
            for m in self.metrics:
                if m.metadata:
                    metadata_keys.update(m.metadata.keys())
            
            fieldnames = [
                'timestamp', 'component', 'operation', 'duration_ms',
                'memory_mb', 'cpu_percent', 'audio_duration_s'
            ] + sorted(metadata_keys)
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for metric in self.metrics:
                row = {
                    'timestamp': metric.timestamp,
                    'component': metric.component,
                    'operation': metric.operation,
                    'duration_ms': metric.duration_ms,
                    'memory_mb': metric.memory_mb,
                    'cpu_percent': metric.cpu_percent,
                    'audio_duration_s': metric.audio_duration_s or ''
                }
                
                # Add metadata fields
                if metric.metadata:
                    for key in metadata_keys:
                        row[key] = metric.metadata.get(key, '')
                
                writer.writerow(row)
        
        return filepath
    
    def export_json(self, filename: Optional[str] = None, include_summary: bool = True) -> str:
        """
        Export metrics to JSON file.
        
        Args:
            filename: Optional custom filename
            include_summary: Whether to include summary statistics
            
        Returns:
            Path to the exported file
        """
        if filename is None:
            filename = f"performance_metrics_{self.session_id}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        output = {
            "session_id": self.session_id,
            "session_start": self.session_start.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics]
        }
        
        if include_summary:
            output["summary"] = self.get_summary()
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        return filepath
    
    def print_summary(self):
        """Print a formatted summary to console"""
        summary = self.get_summary()
        
        print("\n" + "="*80)
        print("SYSTEM PERFORMANCE SUMMARY")
        print("="*80)
        print(f"Session ID: {summary['session_id']}")
        print(f"Session Start: {summary['session_start']}")
        print(f"Total Metrics: {summary['total_metrics']}")
        print("="*80)
        
        for component, operations in summary.get("components", {}).items():
            print(f"\n{component.upper()}")
            print("-"*80)
            
            for operation, stats in operations.items():
                print(f"\n  Operation: {operation}")
                print(f"    Count: {stats['count']}")
                print(f"    Avg Duration: {stats['avg_duration_ms']:.2f} ms")
                print(f"    Min Duration: {stats['min_duration_ms']:.2f} ms")
                print(f"    Max Duration: {stats['max_duration_ms']:.2f} ms")
                print(f"    Avg Memory: {stats['avg_memory_mb']:.2f} MB")
                print(f"    Avg CPU: {stats['avg_cpu_percent']:.2f}%")
                
                if stats['real_time_factor'] is not None:
                    rtf = stats['real_time_factor']
                    status = "✓ FASTER" if rtf < 1.0 else "⚠ SLOWER"
                    print(f"    Real-Time Factor: {rtf:.4f} {status}")
                    print(f"    Total Audio: {stats['total_audio_duration_s']:.2f}s")
        
        print("\n" + "="*80)


class OperationContext:
    """
    Context manager for tracking operation performance.
    
    Usage:
        with profiler.start_operation('data_ingestion', 'vad_filter') as ctx:
            # ... do work ...
            ctx.set_metadata({'audio_duration': 5.2})
    """
    
    def __init__(self, profiler: SystemProfiler, component: str, operation: str):
        self.profiler = profiler
        self.component = component
        self.operation = operation
        self.start_time = None
        self.metadata = {}
        self.audio_duration_s = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        self.profiler.record_metric(
            component=self.component,
            operation=self.operation,
            duration_ms=duration_ms,
            audio_duration_s=self.audio_duration_s,
            metadata=self.metadata
        )
        
        return False  # Don't suppress exceptions
    
    def set_audio_duration(self, duration_s: float):
        """Set the duration of processed audio"""
        self.audio_duration_s = duration_s
    
    def set_metadata(self, metadata: Dict[str, Any]):
        """Set additional metadata for this operation"""
        self.metadata.update(metadata)


if __name__ == "__main__":
    # Example usage
    profiler = SystemProfiler()
    
    # Simulate some operations
    with profiler.start_operation('data_ingestion', 'vad_filter') as ctx:
        time.sleep(0.1)
        ctx.set_audio_duration(5.2)
        ctx.set_metadata({'frames_processed': 100})
    
    with profiler.start_operation('feature_extraction', 'compute_f0') as ctx:
        time.sleep(0.05)
        ctx.set_audio_duration(5.2)
    
    # Print summary
    profiler.print_summary()
    
    # Export results
    csv_path = profiler.export_csv()
    json_path = profiler.export_json()
    
    print(f"\nResults exported to:")
    print(f"  CSV: {csv_path}")
    print(f"  JSON: {json_path}")
