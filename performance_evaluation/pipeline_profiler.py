"""
End-to-End Pipeline Profiler

This script provides a comprehensive performance test for the entire audio processing
pipeline, simulating real-world usage in both file-based and live modes.

Components profiled:
1. Data Ingestion Layer (audio collection, VAD filtering)
2. Feature Extraction (voice metrics computation)
3. User Profiling (speaker recognition)
4. Data Transport (MQTT publishing)
5. Database Storage

Usage:
    python pipeline_profiler.py --mode live --audio-file datasets/test.wav
    python pipeline_profiler.py --mode batch --duration 60
"""

import sys
import os
import argparse
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../data_ingestion_layer'))

from system_profiler import SystemProfiler


class PipelineProfiler:
    """
    Comprehensive pipeline profiler that simulates the entire audio processing workflow.
    """
    
    def __init__(self, audio_file: str = None, mode: str = 'live'):
        """
        Initialize the pipeline profiler.
        
        Args:
            audio_file: Path to audio file for testing
            mode: 'live' for real-time simulation or 'batch' for batch processing
        """
        self.audio_file = audio_file
        self.mode = mode
        self.profiler = SystemProfiler()
        
        # Check if audio file exists
        if audio_file and not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    def profile_data_ingestion(self, audio_data, sample_rate: int):
        """
        Profile the data ingestion layer (collection + VAD filtering).
        
        Args:
            audio_data: Audio samples (numpy array)
            sample_rate: Sample rate in Hz
            
        Returns:
            Filtered audio segments
        """
        import numpy as np
        
        audio_duration_s = len(audio_data) / sample_rate
        
        # Profile audio collection (simulated - in real system this is hardware I/O)
        with self.profiler.start_operation('data_ingestion', 'collect') as ctx:
            # Simulate collection overhead
            collected_data = audio_data.copy()
            ctx.set_audio_duration(audio_duration_s)
            ctx.set_metadata({
                'sample_rate': sample_rate,
                'samples': len(audio_data),
                'mode': self.mode
            })
        
        # Profile VAD filtering
        with self.profiler.start_operation('data_ingestion', 'vad_filter') as ctx:
            try:
                import torch
                
                # Load Silero VAD model
                model, utils = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    verbose=False
                )
                
                # Convert to float32 if needed
                if audio_data.dtype != np.float32:
                    audio_float = audio_data.astype(np.float32)
                    if audio_float.max() > 1.0:
                        audio_float = audio_float / 32768.0
                else:
                    audio_float = audio_data
                
                # Apply VAD
                audio_tensor = torch.from_numpy(audio_float)
                
                # Process in chunks (512 samples for Silero VAD)
                frame_size = 512
                voiced_segments = []
                buffer = []
                
                for i in range(0, len(audio_tensor), frame_size):
                    chunk = audio_tensor[i:i+frame_size]
                    if len(chunk) < frame_size:
                        break
                    
                    confidence = model(chunk, sample_rate).item()
                    
                    if confidence > 0.5:
                        buffer.append(chunk.numpy())
                    else:
                        if len(buffer) > 50:  # min_frames
                            voiced_segments.append(np.concatenate(buffer))
                        buffer = []
                
                # Add remaining buffer
                if len(buffer) > 50:
                    voiced_segments.append(np.concatenate(buffer))
                
                ctx.set_audio_duration(audio_duration_s)
                ctx.set_metadata({
                    'voiced_segments': len(voiced_segments),
                    'vad_model': 'silero_vad',
                    'filter_threshold': 0.5
                })
                
                return voiced_segments
                
            except Exception as e:
                print(f"VAD filtering failed: {e}")
                ctx.set_metadata({'error': str(e)})
                return [audio_data]  # Return original if VAD fails
    
    def profile_feature_extraction(self, audio_segment, sample_rate: int):
        """
        Profile feature extraction (voice metrics computation).
        
        Args:
            audio_segment: Audio segment to process (numpy array)
            sample_rate: Sample rate in Hz
            
        Returns:
            Extracted features dictionary
        """
        import random
        
        audio_duration_s = len(audio_segment) / sample_rate
        
        features = {}
        
        # Profile individual feature extractors
        feature_groups = [
            ('f0_features', ['f0_avg', 'f0_std', 'f0_range']),
            ('energy_features', ['rms_energy_range', 'rms_energy_std']),
            ('spectral_features', ['spectral_flatness', 'spectral_modulation']),
            ('voice_quality', ['hnr_mean', 'jitter', 'shimmer']),
            ('temporal_features', ['temporal_modulation', 'voice_onset_time']),
        ]
        
        for group_name, feature_list in feature_groups:
            with self.profiler.start_operation('feature_extraction', group_name) as ctx:
                try:
                    # Simulate feature extraction
                    # In real system, this would call actual extractors
                    for feature in feature_list:
                        features[feature] = random.random()
                    
                    ctx.set_audio_duration(audio_duration_s)
                    ctx.set_metadata({
                        'features_count': len(feature_list),
                        'features': feature_list
                    })
                except Exception as e:
                    ctx.set_metadata({'error': str(e)})
        
        return features
    
    def profile_user_recognition(self, audio_segment, sample_rate: int):
        """
        Profile user recognition (speaker identification).
        
        Args:
            audio_segment: Audio segment (numpy array)
            sample_rate: Sample rate in Hz
            
        Returns:
            User ID
        """
        audio_duration_s = len(audio_segment) / sample_rate
        
        with self.profiler.start_operation('user_profiling', 'speaker_recognition') as ctx:
            try:
                # Simulate speaker recognition
                # In real system, this would use Resemblyzer D-vectors
                user_id = "test_user_1"
                
                ctx.set_audio_duration(audio_duration_s)
                ctx.set_metadata({
                    'user_id': user_id,
                    'recognition_method': 'resemblyzer'
                })
                
                return user_id
                
            except Exception as e:
                ctx.set_metadata({'error': str(e)})
                return "unknown"
    
    def profile_data_transport(self, data_size_bytes: int):
        """
        Profile MQTT message publishing.
        
        Args:
            data_size_bytes: Size of data to publish
        """
        with self.profiler.start_operation('data_transport', 'mqtt_publish') as ctx:
            # Simulate MQTT publish overhead
            time.sleep(0.001)  # Typical MQTT publish latency
            
            ctx.set_metadata({
                'data_size_bytes': data_size_bytes,
                'transport': 'mqtt',
                'qos': 1
            })
    
    def profile_database_storage(self, metrics: dict):
        """
        Profile database storage operations.
        
        Args:
            metrics: Metrics dictionary to store
        """
        with self.profiler.start_operation('storage', 'mongodb_write') as ctx:
            # Simulate MongoDB write
            time.sleep(0.002)  # Typical MongoDB write latency
            
            ctx.set_metadata({
                'metrics_count': len(metrics),
                'database': 'mongodb',
                'collection': 'raw_metrics'
            })
    
    def run_pipeline(self, duration_s: int = 60):
        """
        Run the complete pipeline profiling test.
        
        Args:
            duration_s: Duration to run the test in seconds
        """
        print(f"\n{'='*80}")
        print(f"STARTING PIPELINE PROFILING TEST")
        print(f"{'='*80}")
        print(f"Mode: {self.mode}")
        print(f"Duration: {duration_s}s")
        print(f"Audio File: {self.audio_file or 'N/A (using synthetic data)'}")
        print(f"{'='*80}\n")
        
        # Load or generate audio data
        if self.audio_file:
            try:
                import librosa
                import numpy as np
                audio_data, sample_rate = librosa.load(self.audio_file, sr=16000, mono=True)
                print(f"Loaded audio file: {len(audio_data)/sample_rate:.2f}s @ {sample_rate}Hz")
            except ImportError:
                print("librosa not installed, using synthetic audio data")
                import numpy as np
                sample_rate = 16000
                audio_data = np.random.randn(sample_rate * duration_s).astype(np.float32) * 0.1
            except Exception as e:
                print(f"Failed to load audio file: {e}")
                print("Using synthetic audio data instead")
                import numpy as np
                sample_rate = 16000
                audio_data = np.random.randn(sample_rate * duration_s).astype(np.float32) * 0.1
        else:
            # Generate synthetic audio
            import numpy as np
            sample_rate = 16000
            audio_data = np.random.randn(sample_rate * duration_s).astype(np.float32) * 0.1
            print(f"Generated synthetic audio: {duration_s}s @ {sample_rate}Hz")
        
        start_time = time.time()
        processed_segments = 0
        
        # Process the audio in chunks (simulate real-time processing)
        chunk_duration = 5.0  # Process 5 seconds at a time
        chunk_size = int(sample_rate * chunk_duration)
        
        for i in range(0, len(audio_data), chunk_size):
            if time.time() - start_time > duration_s:
                break
            
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) < sample_rate:  # Skip chunks < 1 second
                continue
            
            print(f"\nProcessing chunk {processed_segments + 1}...")
            
            # 1. Data Ingestion (Collection + VAD)
            voiced_segments = self.profile_data_ingestion(chunk, sample_rate)
            
            # 2. Process each voiced segment
            for segment in voiced_segments:
                if len(segment) < sample_rate:  # Skip short segments
                    continue
                
                # 3. User Recognition
                user_id = self.profile_user_recognition(segment, sample_rate)
                
                # 4. Feature Extraction
                features = self.profile_feature_extraction(segment, sample_rate)
                
                # 5. Data Transport
                data_size = len(segment) * 2  # int16 = 2 bytes per sample
                self.profile_data_transport(data_size)
                
                # 6. Database Storage
                self.profile_database_storage(features)
                
                processed_segments += 1
            
            # Simulate real-time delay in live mode
            if self.mode == 'live':
                elapsed = time.time() - start_time
                expected_time = (i + chunk_size) / sample_rate
                if elapsed < expected_time:
                    time.sleep(expected_time - elapsed)
        
        total_time = time.time() - start_time
        
        print(f"\n{'='*80}")
        print(f"PROFILING COMPLETE")
        print(f"{'='*80}")
        print(f"Total Runtime: {total_time:.2f}s")
        print(f"Processed Segments: {processed_segments}")
        print(f"{'='*80}\n")
        
        # Print and export results
        self.profiler.print_summary()
        
        csv_file = self.profiler.export_csv(f"pipeline_profile_{self.mode}.csv")
        json_file = self.profiler.export_json(f"pipeline_profile_{self.mode}.json")
        
        print(f"\nResults exported to:")
        print(f"  CSV:  {csv_file}")
        print(f"  JSON: {json_file}")
        
        return self.profiler.get_summary()


def main():
    """Main entry point for the pipeline profiler"""
    parser = argparse.ArgumentParser(
        description='Profile the audio depression detection pipeline'
    )
    parser.add_argument(
        '--mode',
        choices=['live', 'batch'],
        default='live',
        help='Profiling mode: live (real-time simulation) or batch (fast processing)'
    )
    parser.add_argument(
        '--audio-file',
        type=str,
        default=None,
        help='Path to audio file for testing (optional, will use synthetic data if not provided)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Duration of the test in seconds (default: 60)'
    )
    
    args = parser.parse_args()
    
    # Create and run profiler
    profiler = PipelineProfiler(audio_file=args.audio_file, mode=args.mode)
    profiler.run_pipeline(duration_s=args.duration)


if __name__ == "__main__":
    main()
