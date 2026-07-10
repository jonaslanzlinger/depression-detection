#!/usr/bin/env python3
"""
Synthetic Board Analytics Data Generator

Generates realistic test data for boards and analytics features including:
- Multiple boards with different configurations
- Audio quality metrics over time
- Board status and activity patterns
- Environment configurations

Usage:
    from tests.synthetic_board_data_generator import BoardDataGenerator
    
    generator = BoardDataGenerator(mongo_uri="mongodb://localhost:27017")
    generator.generate_test_data(num_boards=3, days=7)
    generator.cleanup()
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np
from pymongo import MongoClient


class BoardDataGenerator:
    """Generate synthetic test data for board analytics testing."""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", test_db: str = "iotsensing_test"):
        """
        Initialize the generator.
        
        Args:
            mongo_uri: MongoDB connection URI
            test_db: Test database name
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client[test_db]
        self.test_user_id = 9999  # Special user ID for testing
        self.generated_board_ids = []
        self.generated_env_ids = []
        
    def cleanup(self):
        """Remove all generated test data."""
        # Delete boards
        self.db["boards"].delete_many({"user_id": self.test_user_id})
        
        # Delete environments
        self.db["environments"].delete_many({"user_id": self.test_user_id})
        
        # Delete metrics
        self.db["raw_metrics"].delete_many({"user_id": self.test_user_id})
        self.db["audio_quality_metrics"].delete_many(
            {"board_id": {"$in": self.generated_board_ids}}
        )
        
        print(f"✓ Cleaned up test data for user {self.test_user_id}")
        
    def generate_environment(self, name: str, description: str = "") -> str:
        """
        Generate a test environment.
        
        Args:
            name: Environment name
            description: Environment description
            
        Returns:
            Generated environment ID
        """
        env_id = str(uuid.uuid4())
        env_doc = {
            "environment_id": env_id,
            "user_id": self.test_user_id,
            "name": name,
            "description": description,
            "created_at": datetime.utcnow(),
        }
        self.db["environments"].insert_one(env_doc)
        self.generated_env_ids.append(env_id)
        return env_id
        
    def generate_board(
        self,
        name: str,
        environment_id: str,
        is_active: bool = True,
        mac_prefix: str = "TEST"
    ) -> str:
        """
        Generate a test board.
        
        Args:
            name: Board name
            environment_id: Associated environment ID
            is_active: Whether the board is active
            mac_prefix: Prefix for MAC address
            
        Returns:
            Generated board ID
        """
        board_id = str(uuid.uuid4())
        # Generate valid MAC address with 6 octets
        mac_address = f"{mac_prefix}:{random.randint(10, 99):02X}:{random.randint(10, 99):02X}:{random.randint(10, 99):02X}:{random.randint(10, 99):02X}:{random.randint(10, 99):02X}"
        
        board_doc = {
            "board_id": board_id,
            "user_id": self.test_user_id,
            "mac_address": mac_address,
            "name": name,
            "environment_id": environment_id,
            "port": random.randint(8000, 9000),
            "is_active": is_active,
            "last_seen": datetime.utcnow() if is_active else datetime.utcnow() - timedelta(hours=24),
            "created_at": datetime.utcnow() - timedelta(days=30),
        }
        self.db["boards"].insert_one(board_doc)
        self.generated_board_ids.append(board_id)
        return board_id
        
    def generate_quality_metrics(
        self,
        board_id: str,
        start_time: datetime,
        end_time: datetime,
        pattern: str = "normal"
    ) -> List[Dict]:
        """
        Generate audio quality metrics for a board.
        
        Args:
            board_id: Board ID
            start_time: Start time for metrics
            end_time: End time for metrics
            pattern: Activity pattern ('normal', 'high_activity', 'low_activity', 'intermittent', 'clipping_issues')
            
        Returns:
            List of generated metric documents
        """
        metrics = []
        current_time = start_time
        
        # Configure pattern parameters
        if pattern == "normal":
            base_rms = 0.15
            rms_std = 0.05
            base_dbfs = -25
            clipping_prob = 0.01
            sample_interval = 5  # seconds
        elif pattern == "high_activity":
            base_rms = 0.30
            rms_std = 0.10
            base_dbfs = -15
            clipping_prob = 0.05
            sample_interval = 5
        elif pattern == "low_activity":
            base_rms = 0.05
            rms_std = 0.02
            base_dbfs = -40
            clipping_prob = 0.0
            sample_interval = 10
        elif pattern == "intermittent":
            # Randomly skip many samples
            base_rms = 0.20
            rms_std = 0.08
            base_dbfs = -20
            clipping_prob = 0.02
            sample_interval = 30  # Larger gaps
        elif pattern == "clipping_issues":
            base_rms = 0.40
            rms_std = 0.05
            base_dbfs = -10
            clipping_prob = 0.20  # High clipping
            sample_interval = 5
        else:
            # Default to normal
            base_rms = 0.15
            rms_std = 0.05
            base_dbfs = -25
            clipping_prob = 0.01
            sample_interval = 5
            
        while current_time < end_time:
            # Skip some samples for intermittent pattern
            if pattern == "intermittent" and random.random() < 0.5:
                current_time += timedelta(seconds=sample_interval * 2)
                continue
                
            # Generate metrics
            rms = max(0.001, base_rms + random.gauss(0, rms_std))
            peak_amplitude = min(1.0, rms * random.uniform(1.5, 3.0))
            
            # Calculate dBFS
            db_fs = 20 * np.log10(rms) if rms > 0 else -96
            db_fs = max(-96, min(0, base_dbfs + random.gauss(0, 5)))
            
            # Clipping
            clipping_count = 1 if random.random() < clipping_prob else 0
            if clipping_count > 0:
                clipping_count = random.randint(1, 10)
                
            # Dynamic range
            dynamic_range = abs(db_fs - (db_fs - random.uniform(10, 30)))
            
            # SNR (only sometimes available)
            snr = None
            if random.random() < 0.3:  # 30% of samples have SNR
                snr = random.uniform(10, 30)
                
            metric_doc = {
                "board_id": board_id,
                "timestamp": current_time,
                "rms": rms,
                "peak_amplitude": peak_amplitude,
                "db_fs": db_fs,
                "clipping_count": clipping_count,
                "dynamic_range": dynamic_range,
                "snr": snr,
            }
            metrics.append(metric_doc)
            current_time += timedelta(seconds=sample_interval)
            
        return metrics
        
    def generate_raw_metrics(
        self,
        board_id: str,
        start_time: datetime,
        end_time: datetime,
        metrics_per_interval: int = 3
    ) -> List[Dict]:
        """
        Generate raw metrics for testing data presence.
        
        Args:
            board_id: Board ID
            start_time: Start time
            end_time: End time
            metrics_per_interval: Number of metric samples per 5-second interval
            
        Returns:
            List of raw metric documents
        """
        raw_metrics = []
        current_time = start_time
        
        metric_names = ["mean_f0", "jitter", "shimmer", "hnr", "speech_rate"]
        
        while current_time < end_time:
            for _ in range(metrics_per_interval):
                for metric_name in metric_names:
                    raw_metrics.append({
                        "user_id": self.test_user_id,
                        "board_id": board_id,
                        "metric_name": metric_name,
                        "metric_value": random.uniform(50, 300),
                        "timestamp": current_time,
                    })
            current_time += timedelta(seconds=5)
            
        return raw_metrics
        
    def generate_test_scenario(
        self,
        scenario: str,
        duration_hours: int = 2
    ) -> Dict:
        """
        Generate a complete test scenario.
        
        Args:
            scenario: Scenario name ('multi_board_comparison', 'data_deletion', 'edge_cases', 'full_analytics')
            duration_hours: Duration of data in hours
            
        Returns:
            Dictionary with generated IDs and metadata
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=duration_hours)
        
        if scenario == "multi_board_comparison":
            # Create 3 boards in different environments with different patterns
            env1 = self.generate_environment("Living Room", "Main living area")
            env2 = self.generate_environment("Bedroom", "Primary bedroom")
            env3 = self.generate_environment("Kitchen", "Kitchen area")
            
            board1 = self.generate_board("Living Room Mic", env1, is_active=True)
            board2 = self.generate_board("Bedroom Mic", env2, is_active=True)
            board3 = self.generate_board("Kitchen Mic", env3, is_active=True)
            
            # Generate different activity patterns
            metrics1 = self.generate_quality_metrics(board1, start_time, end_time, "high_activity")
            metrics2 = self.generate_quality_metrics(board2, start_time, end_time, "normal")
            metrics3 = self.generate_quality_metrics(board3, start_time, end_time, "low_activity")
            
            # Insert metrics
            if metrics1:
                self.db["audio_quality_metrics"].insert_many(metrics1)
            if metrics2:
                self.db["audio_quality_metrics"].insert_many(metrics2)
            if metrics3:
                self.db["audio_quality_metrics"].insert_many(metrics3)
                
            # Generate raw metrics for streaming detection
            raw1 = self.generate_raw_metrics(board1, end_time - timedelta(minutes=10), end_time)
            raw2 = self.generate_raw_metrics(board2, end_time - timedelta(minutes=10), end_time)
            
            if raw1:
                self.db["raw_metrics"].insert_many(raw1)
            if raw2:
                self.db["raw_metrics"].insert_many(raw2)
                
            return {
                "scenario": scenario,
                "boards": [board1, board2, board3],
                "environments": [env1, env2, env3],
                "metrics_count": len(metrics1) + len(metrics2) + len(metrics3),
            }
            
        elif scenario == "data_deletion":
            # Create single board with recent data for deletion testing
            env = self.generate_environment("Test Room", "Room for deletion tests")
            board = self.generate_board("Test Mic", env, is_active=True)
            
            # Generate metrics in the last 30 seconds for easy deletion
            recent_start = end_time - timedelta(seconds=30)
            metrics = self.generate_quality_metrics(board, recent_start, end_time, "normal")
            raw_metrics = self.generate_raw_metrics(board, recent_start, end_time, 5)
            
            if metrics:
                self.db["audio_quality_metrics"].insert_many(metrics)
            if raw_metrics:
                self.db["raw_metrics"].insert_many(raw_metrics)
                
            return {
                "scenario": scenario,
                "board": board,
                "environment": env,
                "test_timestamp": (recent_start + timedelta(seconds=15)).timestamp(),
                "metrics_count": len(metrics),
            }
            
        elif scenario == "edge_cases":
            # Create boards with various edge cases
            env = self.generate_environment("Edge Case Room", "Testing edge cases")
            
            # Board 1: Active but no recent data
            board1 = self.generate_board("Idle Mic", env, is_active=True)
            old_start = end_time - timedelta(hours=48)
            old_end = end_time - timedelta(hours=24)
            old_metrics = self.generate_quality_metrics(board1, old_start, old_end, "normal")
            if old_metrics:
                self.db["audio_quality_metrics"].insert_many(old_metrics)
                
            # Board 2: Clipping issues
            board2 = self.generate_board("Clipping Mic", env, is_active=True)
            clip_metrics = self.generate_quality_metrics(board2, start_time, end_time, "clipping_issues")
            if clip_metrics:
                self.db["audio_quality_metrics"].insert_many(clip_metrics)
                
            # Board 3: Inactive
            board3 = self.generate_board("Offline Mic", env, is_active=False)
            
            return {
                "scenario": scenario,
                "boards": [board1, board2, board3],
                "environment": env,
                "metrics_count": len(old_metrics) + len(clip_metrics),
            }
            
        elif scenario == "full_analytics":
            # Complete scenario for full analytics testing
            env1 = self.generate_environment("Office", "Home office")
            env2 = self.generate_environment("Garage", "Garage workspace")
            
            board1 = self.generate_board("Office Mic 1", env1, is_active=True)
            board2 = self.generate_board("Office Mic 2", env1, is_active=True)
            board3 = self.generate_board("Garage Mic", env2, is_active=True)
            
            # Generate 6 hours of data with varying patterns
            metrics1 = self.generate_quality_metrics(
                board1, start_time, end_time, "high_activity"
            )
            metrics2 = self.generate_quality_metrics(
                board2, start_time, end_time, "normal"
            )
            metrics3 = self.generate_quality_metrics(
                board3, start_time, end_time, "intermittent"
            )
            
            all_metrics = metrics1 + metrics2 + metrics3
            if all_metrics:
                self.db["audio_quality_metrics"].insert_many(all_metrics)
                
            # Add recent raw metrics for streaming status
            for board in [board1, board2, board3]:
                raw = self.generate_raw_metrics(
                    board, end_time - timedelta(minutes=5), end_time, 10
                )
                if raw:
                    self.db["raw_metrics"].insert_many(raw)
                    
            return {
                "scenario": scenario,
                "boards": [board1, board2, board3],
                "environments": [env1, env2],
                "metrics_count": len(all_metrics),
                "duration_hours": duration_hours,
            }
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
            
    def generate_test_data(
        self,
        num_boards: int = 3,
        days: int = 1,
        pattern: str = "normal"
    ) -> Dict:
        """
        Generate generic test data with specified number of boards.
        
        Args:
            num_boards: Number of boards to create
            days: Number of days of historical data
            pattern: Activity pattern for all boards
            
        Returns:
            Dictionary with generated IDs
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Create environments
        environments = []
        for i in range((num_boards + 1) // 2):  # One env per 2 boards
            env_id = self.generate_environment(
                f"Test Environment {i+1}",
                f"Generated test environment {i+1}"
            )
            environments.append(env_id)
            
        # Create boards
        boards = []
        for i in range(num_boards):
            env_id = environments[i // 2]
            board_id = self.generate_board(
                f"Test Board {i+1}",
                env_id,
                is_active=(i < num_boards - 1)  # Last board is inactive
            )
            boards.append(board_id)
            
            # Generate metrics if active
            if i < num_boards - 1:
                metrics = self.generate_quality_metrics(
                    board_id, start_time, end_time, pattern
                )
                if metrics:
                    self.db["audio_quality_metrics"].insert_many(metrics)
                    
                # Add recent raw metrics
                raw = self.generate_raw_metrics(
                    board_id,
                    end_time - timedelta(minutes=5),
                    end_time
                )
                if raw:
                    self.db["raw_metrics"].insert_many(raw)
                    
        return {
            "user_id": self.test_user_id,
            "boards": boards,
            "environments": environments,
            "start_time": start_time,
            "end_time": end_time,
        }
        
    def get_test_user_id(self) -> int:
        """Get the test user ID for queries."""
        return self.test_user_id
        
    def close(self):
        """Close database connection."""
        self.client.close()
