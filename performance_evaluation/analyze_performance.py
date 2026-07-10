"""
Performance Analysis and Visualization Tool

This module analyzes performance metrics from CSV/JSON files and generates
comprehensive reports with visualizations to identify bottlenecks and optimization
opportunities.

Usage:
    python analyze_performance.py --input results/pipeline_profile_live.csv
    python analyze_performance.py --compare results/before.csv results/after.csv
"""

import argparse
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np


class PerformanceAnalyzer:
    """
    Analyze and visualize performance metrics from profiling runs.
    """
    
    def __init__(self, csv_file: str = None, json_file: str = None):
        """
        Initialize the analyzer with a metrics file.
        
        Args:
            csv_file: Path to CSV metrics file
            json_file: Path to JSON metrics file
        """
        self.csv_file = csv_file
        self.json_file = json_file
        self.df = None
        self.summary = None
        
        if csv_file:
            self.load_csv(csv_file)
        elif json_file:
            self.load_json(json_file)
    
    def load_csv(self, csv_file: str):
        """Load metrics from CSV file"""
        self.df = pd.read_csv(csv_file)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        print(f"Loaded {len(self.df)} metrics from {csv_file}")
    
    def load_json(self, json_file: str):
        """Load metrics from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        self.summary = data.get('summary', {})
        self.df = pd.DataFrame(data['metrics'])
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        print(f"Loaded {len(self.df)} metrics from {json_file}")
    
    def identify_bottlenecks(self, threshold_percentile: float = 90) -> pd.DataFrame:
        """
        Identify performance bottlenecks.
        
        Args:
            threshold_percentile: Percentile threshold for identifying slow operations
            
        Returns:
            DataFrame with bottleneck information
        """
        # Group by component and operation
        grouped = self.df.groupby(['component', 'operation']).agg({
            'duration_ms': ['mean', 'median', 'max', 'min', 'std', 'count'],
            'memory_mb': 'mean',
            'cpu_percent': 'mean',
            'audio_duration_s': 'sum'
        }).round(2)
        
        grouped.columns = ['_'.join(col).strip() for col in grouped.columns.values]
        grouped = grouped.reset_index()
        
        # Calculate real-time factor
        grouped['real_time_factor'] = (
            grouped['duration_ms_mean'] / 1000
        ) / grouped['audio_duration_s_sum'].replace(0, np.nan)
        
        # Identify bottlenecks based on duration
        threshold = self.df['duration_ms'].quantile(threshold_percentile / 100)
        grouped['is_bottleneck'] = grouped['duration_ms_max'] > threshold
        
        # Sort by average duration
        grouped = grouped.sort_values('duration_ms_mean', ascending=False)
        
        return grouped
    
    def generate_report(self, output_file: str = None) -> str:
        """
        Generate a comprehensive text report.
        
        Args:
            output_file: Optional file to save report to
            
        Returns:
            Report text
        """
        lines = []
        lines.append("="*80)
        lines.append("PERFORMANCE ANALYSIS REPORT")
        lines.append("="*80)
        lines.append("")
        
        # Overall statistics
        lines.append("OVERALL STATISTICS")
        lines.append("-"*80)
        lines.append(f"Total Operations: {len(self.df)}")
        lines.append(f"Total Duration: {self.df['duration_ms'].sum()/1000:.2f}s")
        lines.append(f"Average Duration per Operation: {self.df['duration_ms'].mean():.2f}ms")
        lines.append(f"Average Memory Usage: {self.df['memory_mb'].mean():.2f}MB")
        lines.append(f"Average CPU Usage: {self.df['cpu_percent'].mean():.2f}%")
        lines.append("")
        
        # Component breakdown
        lines.append("COMPONENT BREAKDOWN")
        lines.append("-"*80)
        
        component_stats = self.df.groupby('component').agg({
            'duration_ms': ['sum', 'mean', 'count'],
            'memory_mb': 'mean',
            'cpu_percent': 'mean'
        }).round(2)
        
        for component in component_stats.index:
            lines.append(f"\n{component}:")
            stats = component_stats.loc[component]
            lines.append(f"  Total Time: {stats[('duration_ms', 'sum')]:.2f}ms")
            lines.append(f"  Avg Time: {stats[('duration_ms', 'mean')]:.2f}ms")
            lines.append(f"  Operations: {stats[('duration_ms', 'count')]:.0f}")
            lines.append(f"  Avg Memory: {stats[('memory_mb', 'mean')]:.2f}MB")
            lines.append(f"  Avg CPU: {stats[('cpu_percent', 'mean')]:.2f}%")
        
        lines.append("")
        
        # Bottleneck analysis
        lines.append("BOTTLENECK ANALYSIS")
        lines.append("-"*80)
        
        bottlenecks = self.identify_bottlenecks()
        
        for idx, row in bottlenecks.head(10).iterrows():
            lines.append(f"\n{row['component']}/{row['operation']}:")
            lines.append(f"  Avg Duration: {row['duration_ms_mean']:.2f}ms")
            lines.append(f"  Max Duration: {row['duration_ms_max']:.2f}ms")
            lines.append(f"  Occurrences: {row['duration_ms_count']:.0f}")
            
            if not pd.isna(row['real_time_factor']):
                rtf = row['real_time_factor']
                status = "✓ Real-time capable" if rtf < 1.0 else "⚠ Slower than real-time"
                lines.append(f"  Real-Time Factor: {rtf:.4f} ({status})")
        
        lines.append("")
        
        # Optimization recommendations
        lines.append("OPTIMIZATION RECOMMENDATIONS")
        lines.append("-"*80)
        
        recommendations = self._generate_recommendations(bottlenecks)
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        
        lines.append("")
        lines.append("="*80)
        
        report = "\n".join(lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"Report saved to {output_file}")
        
        return report
    
    def _generate_recommendations(self, bottlenecks: pd.DataFrame) -> List[str]:
        """Generate optimization recommendations based on bottleneck analysis"""
        recommendations = []
        
        # Check for slow operations
        slow_ops = bottlenecks[bottlenecks['duration_ms_mean'] > 100].head(5)
        for idx, row in slow_ops.iterrows():
            if 'vad_filter' in row['operation']:
                recommendations.append(
                    f"VAD filtering ({row['duration_ms_mean']:.0f}ms avg): "
                    f"Consider batch processing or using a faster VAD model"
                )
            elif 'feature_extraction' in row['component']:
                recommendations.append(
                    f"{row['operation']} ({row['duration_ms_mean']:.0f}ms avg): "
                    f"Consider caching results or using optimized libraries"
                )
            elif 'speaker_recognition' in row['operation']:
                recommendations.append(
                    f"Speaker recognition ({row['duration_ms_mean']:.0f}ms avg): "
                    f"Consider caching embeddings or using a lighter model"
                )
        
        # Check for high memory usage
        high_memory = bottlenecks[bottlenecks['memory_mb_mean'] > 500].head(3)
        if not high_memory.empty:
            recommendations.append(
                "High memory usage detected: Consider implementing streaming processing "
                "or reducing buffer sizes"
            )
        
        # Check for non-real-time operations
        non_realtime = bottlenecks[bottlenecks['real_time_factor'] > 1.0]
        if not non_realtime.empty:
            recommendations.append(
                f"{len(non_realtime)} operations are slower than real-time: "
                f"Consider parallel processing or GPU acceleration"
            )
        
        # General recommendations
        if self.df['cpu_percent'].mean() < 50:
            recommendations.append(
                "Low CPU utilization: Consider parallel processing to utilize more cores"
            )
        
        if len(recommendations) == 0:
            recommendations.append("Performance looks good! No major bottlenecks detected.")
        
        return recommendations
    
    def plot_timeline(self, output_file: str = None):
        """
        Plot performance timeline showing duration of operations over time.
        
        Args:
            output_file: Optional file to save plot to
        """
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        # Duration over time
        ax = axes[0]
        for component in self.df['component'].unique():
            component_data = self.df[self.df['component'] == component]
            ax.plot(component_data['timestamp'], component_data['duration_ms'],
                   label=component, marker='o', alpha=0.7)
        ax.set_ylabel('Duration (ms)')
        ax.set_title('Operation Duration Over Time')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Memory over time
        ax = axes[1]
        ax.plot(self.df['timestamp'], self.df['memory_mb'], color='orange', marker='.')
        ax.set_ylabel('Memory (MB)')
        ax.set_title('Memory Usage Over Time')
        ax.grid(True, alpha=0.3)
        
        # CPU over time
        ax = axes[2]
        ax.plot(self.df['timestamp'], self.df['cpu_percent'], color='green', marker='.')
        ax.set_ylabel('CPU %')
        ax.set_xlabel('Timestamp')
        ax.set_title('CPU Usage Over Time')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"Timeline plot saved to {output_file}")
        else:
            plt.show()
    
    def plot_component_breakdown(self, output_file: str = None):
        """
        Plot component breakdown showing time spent in each component.
        
        Args:
            output_file: Optional file to save plot to
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Pie chart of total time by component
        ax = axes[0]
        component_time = self.df.groupby('component')['duration_ms'].sum()
        ax.pie(component_time, labels=component_time.index, autopct='%1.1f%%', startangle=90)
        ax.set_title('Total Time by Component')
        
        # Bar chart of average time by component/operation
        ax = axes[1]
        op_stats = self.df.groupby(['component', 'operation'])['duration_ms'].mean().sort_values(ascending=False).head(10)
        op_stats.plot(kind='barh', ax=ax)
        ax.set_xlabel('Average Duration (ms)')
        ax.set_title('Top 10 Operations by Average Duration')
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"Component breakdown plot saved to {output_file}")
        else:
            plt.show()
    
    def plot_real_time_factor(self, output_file: str = None):
        """
        Plot real-time factor analysis.
        
        Args:
            output_file: Optional file to save plot to
        """
        # Calculate real-time factor for each operation
        df_with_audio = self.df[self.df['audio_duration_s'].notna() & (self.df['audio_duration_s'] > 0)]
        
        if df_with_audio.empty:
            print("No audio duration data available for real-time factor analysis")
            return
        
        df_with_audio['real_time_factor'] = (df_with_audio['duration_ms'] / 1000) / df_with_audio['audio_duration_s']
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Box plot of real-time factor by component
        components = df_with_audio.groupby(['component', 'operation'])['real_time_factor'].median().sort_values()
        
        df_with_audio['comp_op'] = df_with_audio['component'] + '/' + df_with_audio['operation']
        
        sns.boxplot(data=df_with_audio, y='comp_op', x='real_time_factor', ax=ax, order=components.index)
        
        # Add vertical line at 1.0 (real-time threshold)
        ax.axvline(x=1.0, color='red', linestyle='--', label='Real-time threshold')
        
        ax.set_xlabel('Real-Time Factor (lower is better)')
        ax.set_ylabel('Component/Operation')
        ax.set_title('Real-Time Performance Analysis\n(< 1.0 = faster than real-time)')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"Real-time factor plot saved to {output_file}")
        else:
            plt.show()


def compare_runs(csv_files: List[str], labels: List[str] = None, output_dir: str = 'performance_evaluation/results'):
    """
    Compare multiple profiling runs.
    
    Args:
        csv_files: List of CSV files to compare
        labels: Optional labels for each run
        output_dir: Directory to save comparison results
    """
    if labels is None:
        labels = [f"Run {i+1}" for i in range(len(csv_files))]
    
    # Load all runs
    runs = []
    for csv_file, label in zip(csv_files, labels):
        analyzer = PerformanceAnalyzer(csv_file=csv_file)
        runs.append({
            'label': label,
            'analyzer': analyzer,
            'df': analyzer.df
        })
    
    # Create comparison plots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Average duration by component
    ax = axes[0, 0]
    for run in runs:
        comp_time = run['df'].groupby('component')['duration_ms'].mean()
        comp_time.plot(kind='bar', ax=ax, label=run['label'], alpha=0.7)
    ax.set_ylabel('Average Duration (ms)')
    ax.set_title('Average Duration by Component')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Total time comparison
    ax = axes[0, 1]
    total_times = [run['df']['duration_ms'].sum() / 1000 for run in runs]
    ax.bar(labels, total_times)
    ax.set_ylabel('Total Time (seconds)')
    ax.set_title('Total Processing Time')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Memory usage comparison
    ax = axes[1, 0]
    memory_avgs = [run['df']['memory_mb'].mean() for run in runs]
    ax.bar(labels, memory_avgs, color='orange')
    ax.set_ylabel('Average Memory (MB)')
    ax.set_title('Average Memory Usage')
    ax.grid(True, alpha=0.3, axis='y')
    
    # CPU usage comparison
    ax = axes[1, 1]
    cpu_avgs = [run['df']['cpu_percent'].mean() for run in runs]
    ax.bar(labels, cpu_avgs, color='green')
    ax.set_ylabel('Average CPU %')
    ax.set_title('Average CPU Usage')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    output_file = f"{output_dir}/comparison_{len(csv_files)}_runs.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Comparison plot saved to {output_file}")


def main():
    """Main entry point for performance analysis"""
    parser = argparse.ArgumentParser(
        description='Analyze performance metrics and generate reports'
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input CSV or JSON file with performance metrics'
    )
    parser.add_argument(
        '--compare',
        type=str,
        nargs='+',
        help='Additional CSV files to compare against'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='performance_evaluation/results',
        help='Output directory for reports and plots'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Analyze main input file
    print(f"\nAnalyzing {args.input}...")
    
    if args.input.endswith('.json'):
        analyzer = PerformanceAnalyzer(json_file=args.input)
    else:
        analyzer = PerformanceAnalyzer(csv_file=args.input)
    
    # Generate report
    report = analyzer.generate_report(f"{args.output_dir}/performance_report.txt")
    print(report)
    
    # Generate plots
    analyzer.plot_timeline(f"{args.output_dir}/timeline.png")
    analyzer.plot_component_breakdown(f"{args.output_dir}/component_breakdown.png")
    analyzer.plot_real_time_factor(f"{args.output_dir}/real_time_factor.png")
    
    # Compare runs if specified
    if args.compare:
        all_files = [args.input] + args.compare
        labels = ['Baseline'] + [f'Run {i}' for i in range(1, len(args.compare) + 1)]
        compare_runs(all_files, labels, args.output_dir)


if __name__ == "__main__":
    main()
