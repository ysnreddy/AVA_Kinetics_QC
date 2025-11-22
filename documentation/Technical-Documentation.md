# AVA_Kinetics_QC: Complete Technical Documentation

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Architecture Components](#architecture-components)
4. [Module Documentation](#module-documentation)
   - [Proposal Generation Pipeline](#proposal-generation-pipeline)
   - [Processing Pipeline](#processing-pipeline)
   - [Quality Control System](#quality-control-system)
   - [Metrics Logging](#metrics-logging)
   - [Deployment Configuration](#deployment-configuration)
5. [Database Architecture](#database-architecture)
6. [API Reference](#api-reference)
7. [Configuration Management](#configuration-management)
8. [Integration Points](#integration-points)
9. [Workflow Documentation](#workflow-documentation)
10. [Installation Guide](#installation-guide)
11. [Troubleshooting](#troubleshooting)
12. [Appendix](#appendix)

---

## Executive Summary

### Project Overview

AVA_Kinetics_QC is an enterprise-grade Quality Control and annotation management system designed for creating high-quality action recognition datasets at scale. It serves as the quality assurance layer between raw video processing and final machine learning dataset generation, ensuring annotation consistency through multi-annotator validation, rule-based checks, and statistical agreement metrics.

### Core Capabilities

- **Intelligent Pre-Annotation**: Automated keyframe selection and person detection using RF-DETR and YOLOX
- **Multi-Annotator Management**: Configurable overlap assignments with consensus generation
- **Quality Validation**: Rule-based validation engine with customizable constraints
- **Statistical Analysis**: Inter-annotator agreement metrics (IoU, Cohen's Kappa)
- **Cloud Integration**: AWS S3 support for large-scale data handling
- **Real-time Monitoring**: Comprehensive metrics tracking and dashboards
- **Dataset Generation**: AVA-format CSV export with consensus logic

### System Statistics

- **Code Volume**: ~15,000+ lines of Python code
- **Components**: 50+ Python modules across 5 major subsystems
- **API Endpoints**: 10+ RESTful endpoints
- **UI Dashboards**: 4 Streamlit applications
- **Database Tables**: 4 core tables with JSONB support
- **Supported Formats**: CVAT XML 1.1, AVA CSV, Pickle, JSON

---

## System Overview

### High-Level Architecture

The system follows a microservices architecture with distinct components for each stage of the annotation pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                    AVA_Kinetics_QC System                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input Layer          Processing Layer        Output Layer   │
│  ┌──────────┐        ┌──────────────┐       ┌──────────┐  │
│  │  Videos  │───────▶│   Proposal   │──────▶│ Pre-Anno │  │
│  └──────────┘        │  Generation  │       └──────────┘  │
│                      └──────────────┘             │        │
│                                                    ▼        │
│  ┌──────────┐        ┌──────────────┐       ┌──────────┐  │
│  │   CVAT   │◀───────│     Task     │◀──────│  Upload  │  │
│  │  Server  │        │   Creation   │       │    UI    │  │
│  └──────────┘        └──────────────┘       └──────────┘  │
│       │                                                     │
│       ▼              ┌──────────────┐                      │
│  ┌──────────┐        │   Quality    │       ┌──────────┐  │
│  │Annotators│───────▶│   Control    │──────▶│ Metrics  │  │
│  └──────────┘        └──────────────┘       └──────────┘  │
│                             │                               │
│                      ┌──────────────┐       ┌──────────┐  │
│                      │   Dataset    │──────▶│ AVA CSV  │  │
│                      │  Generation  │       └──────────┘  │
│                      └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| API Framework | FastAPI | 0.111.0 | RESTful services |
| UI Framework | Streamlit | 1.49.1 | Dashboards |
| Annotation Tool | CVAT | Latest | Manual annotation |
| Database | PostgreSQL | 14+ | Data persistence |
| Object Detection | RF-DETR/YOLOX | Latest | Person detection |
| Tracking | ByteTracker | Custom | Temporal consistency |
| Cloud Storage | AWS S3 | - | Large file handling |
| Container | Docker | 20.10+ | Deployment |

---

## Architecture Components

### Component Breakdown

#### 1. Proposal Generation Pipeline
- **Location**: `/proposal_generation_pipeline/`
- **Purpose**: Convert raw videos to annotatable proposals
- **Key Modules**: 15+ Python files
- **Output**: Dense proposals with bounding boxes and track IDs

#### 2. Processing Pipeline
- **Location**: `/processing_pipeline/`
- **Purpose**: Core business logic and services
- **Key Services**: 10+ service modules
- **UI Components**: 3 Streamlit dashboards

#### 3. Quality Control System
- **Location**: `/processing_pipeline/services/`
- **Purpose**: Validation and consensus generation
- **Key Features**: Rule engine, routing service, quality metrics

#### 4. Metrics Logging
- **Location**: `/metrics_logging/`
- **Purpose**: Operational metrics and analytics
- **Storage**: JSONL format with deduplication

#### 5. Deployment Setup
- **Location**: `/final_Depolyement_setup/`
- **Purpose**: Production deployment configuration
- **Components**: FastAPI app, routers, configuration

---

## Module Documentation

## Proposal Generation Pipeline

### Overview
The proposal generation pipeline transforms raw video inputs into annotation-ready proposals with intelligent keyframe selection and person detection.

### Module: orchestrator.py
**Purpose**: Main pipeline coordinator

**Class**: `ProposalOrchestrator`

**Key Methods**:
```python
class ProposalOrchestrator:
    def __init__(self, input_path, output_path):
        """Initialize pipeline with input/output paths"""
        self.input_path = input_path
        self.output_path = output_path
        self.stages = self._initialize_stages()

    def run_pipeline(self):
        """
        Execute complete proposal generation pipeline

        Stages:
        1. Video preprocessing
        2. Keyframe selection
        3. Person detection and tracking
        4. Proposal generation
        5. Assignment distribution
        6. XML generation for CVAT

        Returns:
            dict: Paths to generated outputs
        """

    def _initialize_stages(self):
        """Configure pipeline stages with parameters"""
```

### Module: tools/keyframe_selector.py
**Purpose**: Intelligent keyframe selection using RF-DETR

**Key Functions**:
```python
def select_keyframe(video_path, model_path='rf-detr-medium.pth'):
    """
    Select optimal keyframe from video

    Args:
        video_path: Path to input video
        model_path: RF-DETR model weights

    Returns:
        tuple: (frame_image, frame_index, detections)

    Algorithm:
    1. Load video and extract frames
    2. Run RF-DETR on candidate frames
    3. Score frames based on:
       - Person detection confidence
       - Number of visible persons
       - Pose quality
    4. Return highest scoring frame
    """
```

### Module: tools/person_tracker.py
**Purpose**: Person detection and tracking using YOLOX and ByteTracker

**Classes and Methods**:
```python
class PersonTracker:
    def __init__(self, detector='yolox', tracker='byte'):
        """Initialize with detection and tracking models"""
        self.detector = self._load_detector(detector)
        self.tracker = ByteTracker()

    def process_video(self, video_path):
        """
        Process entire video for person tracking

        Returns:
            list: Tracked persons with bounding boxes per frame
        """

    def process_keyframe(self, frame):
        """
        Process single keyframe for detection

        Returns:
            list: Detected persons with confidence scores
        """
```

### Module: tools/byte_tracker.py
**Purpose**: Implementation of BYTE tracking algorithm

**Core Algorithm**:
```python
class ByteTracker:
    def __init__(self, track_thresh=0.5, match_thresh=0.8):
        """
        BYTE tracker for multi-object tracking

        Args:
            track_thresh: Detection confidence threshold
            match_thresh: IoU threshold for matching
        """
        self.tracks = []
        self.track_id_count = 0

    def update(self, detections):
        """
        Update tracks with new detections

        Process:
        1. Split detections into high/low confidence
        2. Match existing tracks with high-conf detections
        3. Match remaining tracks with low-conf detections
        4. Initialize new tracks for unmatched high-conf
        5. Mark unmatched tracks as lost

        Returns:
            list: Active tracks with IDs
        """
```

### Module: tools/create_proposals_from_tracks.py
**Purpose**: Aggregate tracking results into proposal format

```python
def create_dense_proposals(tracks_dir, output_path):
    """
    Create dense proposals from tracking results

    Args:
        tracks_dir: Directory containing track JSONs
        output_path: Output pickle file path

    Output Format:
        {
            'video_id': {
                'frame_001': [
                    [x1, y1, x2, y2, confidence, track_id],
                    ...
                ]
            }
        }
    """
```

### Module: tools/proposals_to_cvat.py
**Purpose**: Convert proposals to CVAT XML format

```python
def generate_cvat_xml(proposals, output_path, attributes=None):
    """
    Generate CVAT 1.1 XML from proposals

    Args:
        proposals: Dense proposals dictionary
        output_path: XML file output path
        attributes: Action attribute definitions

    XML Structure:
        <annotations>
            <track id="0" label="person">
                <box frame="0" xtl="" ytl="" xbr="" ybr="">
                    <attribute name="">value</attribute>
                </box>
            </track>
        </annotations>
    """
```

---

## Processing Pipeline

### Overview
The processing pipeline contains core business logic, service layers, and user interfaces for annotation management.

### Module: services/cvat_integration.py
**Purpose**: CVAT API client for programmatic interaction

**Class**: `CVATClient`

```python
class CVATClient:
    def __init__(self, host, username, password):
        """
        Initialize CVAT client

        Args:
            host: CVAT server URL
            username: CVAT username
            password: CVAT password
        """
        self.host = host
        self.session = self._authenticate(username, password)

    def create_project(self, name, labels):
        """
        Create new annotation project

        Args:
            name: Project name
            labels: Label configuration with attributes

        Returns:
            int: Created project ID
        """

    def create_task(self, project_id, name, data):
        """
        Create annotation task

        Args:
            project_id: Parent project ID
            name: Task name
            data: Task data (frames)

        Returns:
            int: Created task ID
        """

    def upload_data(self, task_id, file_path):
        """
        Upload annotation data to task

        Supports:
        - ZIP archives with frames
        - Video files
        - Image directories
        """

    def import_annotations(self, task_id, format, file_path):
        """
        Import pre-annotations

        Args:
            task_id: Target task ID
            format: Annotation format ('CVAT XML 1.1')
            file_path: Annotation file path
        """

    def export_annotations(self, task_id, format='CVAT XML 1.1'):
        """
        Export annotations from task

        Returns:
            str: Exported annotation data
        """

    def assign_user(self, task_id, user_id):
        """Assign task to annotator"""
```

### Module: services/post_annotation_service.py
**Purpose**: Handle annotation retrieval after task completion

```python
class PostAnnotationService:
    def __init__(self, db_connection, cvat_client):
        """Initialize with database and CVAT connections"""
        self.db = db_connection
        self.cvat = cvat_client

    def process_completed_task(self, task_id, annotator):
        """
        Process completed annotation task

        Workflow:
        1. Export annotations from CVAT
        2. Parse CVAT XML format
        3. Validate with rule engine
        4. Store in PostgreSQL
        5. Trigger quality checks

        Args:
            task_id: Completed task ID
            annotator: Annotator username
        """

    def parse_cvat_xml(self, xml_data):
        """
        Parse CVAT XML annotations

        Returns:
            list: Parsed annotation records
            [
                {
                    'frame': 0,
                    'track_id': 1,
                    'bbox': [x1, y1, x2, y2],
                    'attributes': {...}
                }
            ]
        """

    def store_annotations(self, task_id, annotations, annotator):
        """
        Store annotations in database

        Database fields:
        - task_id, track_id, frame
        - xtl, ytl, xbr, ybr (bbox coordinates)
        - attributes (JSONB)
        - annotator, created_at
        """
```

### Module: services/quality_service.py
**Purpose**: Calculate quality metrics for annotations

```python
class QualityService:
    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.db = db_connection

    def calculate_iou(self, box1, box2):
        """
        Calculate Intersection over Union

        Args:
            box1, box2: Bounding boxes [x1, y1, x2, y2]

        Returns:
            float: IoU score (0-1)
        """

    def calculate_cohens_kappa(self, labels1, labels2):
        """
        Calculate Cohen's Kappa for agreement

        Formula:
            κ = (Po - Pe) / (1 - Pe)
            where:
            Po = observed agreement
            Pe = expected agreement by chance

        Returns:
            float: Kappa score (-1 to 1)
        """

    def compare_tasks(self, task1_id, task2_id):
        """
        Compare overlapping task annotations

        Returns:
            dict: {
                'mean_iou': 0.75,
                'kappa_scores': {...},
                'frame_agreements': [...],
                'disagreements': [...]
            }
        """

    def generate_quality_report(self, project_id):
        """
        Generate comprehensive quality report

        Includes:
        - Overall agreement statistics
        - Per-annotator performance
        - Attribute-wise agreement
        - Problem areas identification
        """
```

### Module: services/rule_engine.py
**Purpose**: Configurable validation rules for annotations

```python
class RuleEngine:
    def __init__(self, config_path='config/rules.yaml'):
        """Load validation rules from YAML"""
        self.rules = self._load_rules(config_path)

    def validate_annotation(self, annotation):
        """
        Validate single annotation against rules

        Checks:
        - Max active labels (limit: 4)
        - Minimum box area (1000 pixels)
        - Mutual exclusivity constraints
        - Context preconditions

        Returns:
            dict: {
                'valid': bool,
                'errors': [...],
                'warnings': [...]
            }
        """

    def check_mutual_exclusivity(self, attributes):
        """Check if attributes violate exclusivity rules"""

    def check_context_preconditions(self, attributes, context):
        """Verify required context for attributes"""

    def check_label_limits(self, attributes):
        """Ensure label count within limits"""
```

### Module: services/routing_service.py
**Purpose**: Smart routing for consensus and adjudication

```python
class RoutingService:
    def __init__(self, db_connection):
        """Initialize with database"""
        self.db = db_connection
        self.audit_rate = 0.6  # 60% audit sampling

    def find_partner_task(self, task_id):
        """
        Find overlapping task for comparison

        Returns:
            int: Partner task ID or None
        """

    def calculate_agreement_score(self, task1_id, task2_id):
        """
        Calculate overall agreement between tasks

        Uses:
        - Jaccard similarity for attributes
        - IoU for spatial agreement

        Returns:
            float: Agreement score (0-1)
        """

    def route_for_adjudication(self, task_id, agreement_score):
        """
        Determine if task needs adjudication

        Logic:
        - Score < 0.7: Route to expert
        - Random audit at 60% rate
        - Flag high-disagreement attributes
        """
```

### Module: services/dataset_generator.py
**Purpose**: Generate final AVA format dataset

```python
class DatasetGenerator:
    def __init__(self, db_connection):
        """Initialize with database"""
        self.db = db_connection

    def generate_ava_csv(self, project_id, output_path):
        """
        Generate AVA format CSV

        Format:
        video_id, timestamp, person_id, x1, y1, x2, y2, action_id, 1

        Process:
        1. Query approved annotations
        2. Apply consensus logic
        3. Map attributes to action IDs
        4. Format as AVA CSV

        Args:
            project_id: Source project
            output_path: Output CSV path
        """

    def apply_consensus(self, annotations):
        """
        Apply consensus logic for overlapping annotations

        Strategy:
        - Majority vote for attributes
        - Average for bounding boxes
        - Confidence weighting
        """

    def map_to_action_ids(self, attributes):
        """
        Map attribute combinations to numeric action IDs

        Returns:
            int: Action ID
        """
```

### Module: services/assignment_generator.py
**Purpose**: Generate annotator assignments with overlap

```python
class AssignmentGenerator:
    def generate_assignments(self, items, annotators, overlap_pct=20):
        """
        Generate random assignments with overlap

        Args:
            items: List of items to annotate
            annotators: List of annotator IDs
            overlap_pct: Percentage for multi-annotator

        Returns:
            dict: {annotator_id: [assigned_items]}

        Algorithm:
        1. Calculate overlap count
        2. Primary round-robin assignment
        3. Random secondary assignment for overlap
        """
```

---

## Quality Control System

### Rule Configuration (config/rules.yaml)

```yaml
# Validation Rules Configuration
version: "1.0"

# Values to ignore in validation
ignore_values:
  - unknown
  - idle
  - no_helmet
  - safe_zone

# Validation limits
limits:
  max_active_labels: 4      # Maximum concurrent labels
  min_box_area: 1000        # Minimum bbox area in pixels
  max_box_area: 500000      # Maximum bbox area
  min_confidence: 0.3       # Minimum detection confidence

# Mutual exclusivity constraints
mutual_exclusivity:
  walking_behavior:
    - [standing_still, walking, running]
  phone_usage:
    - [no_phone, talking_phone, texting]

# Context preconditions
context_preconditions:
  welding:
    required_context:
      - welder_tool
      - protective_gear

  driving:
    required_context:
      - vehicle

# Action flags
flags:
  ME_CONFLICT: "block"       # Mutual exclusivity violation
  CONTEXT_MISS: "flag"       # Missing context
  OVERLABEL: "flag"          # Too many labels
  TINY_BOX: "block"          # Box too small
  LOW_CONFIDENCE: "warn"     # Low confidence detection
```

### Shared Configuration (services/shared_config.py)

```python
# Centralized attribute definitions
ATTRIBUTE_DEFINITIONS = {
    'walking_behavior': {
        'type': 'select',
        'values': [
            'unknown',
            'normal_walk',
            'fast_walk',
            'slow_walk',
            'standing_still',
            'jogging',
            'window_shopping'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'phone_usage': {
        'type': 'select',
        'values': [
            'unknown',
            'no_phone',
            'talking_phone',
            'texting',
            'taking_photo',
            'listening_music'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'social_interaction': {
        'type': 'select',
        'values': [
            'unknown',
            'alone',
            'talking_companion',
            'group_walking',
            'greeting_someone',
            'asking_directions',
            'avoiding_crowd'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'carrying_items': {
        'type': 'select',
        'values': [
            'unknown',
            'empty_hands',
            'shopping_bags',
            'backpack',
            'briefcase_bag',
            'umbrella',
            'food_drink',
            'multiple_items'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'street_behavior': {
        'type': 'select',
        'values': [
            'unknown',
            'sidewalk_walking',
            'crossing_street',
            'waiting_signal',
            'looking_around',
            'checking_map',
            'entering_building',
            'exiting_building'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'posture_gesture': {
        'type': 'select',
        'values': [
            'unknown',
            'upright_normal',
            'looking_down',
            'looking_up',
            'hands_in_pockets',
            'arms_crossed',
            'pointing_gesture',
            'bowing_gesture'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'clothing_style': {
        'type': 'select',
        'values': [
            'unknown',
            'business_attire',
            'casual_wear',
            'tourist_style',
            'school_uniform',
            'sports_wear',
            'traditional_wear'
        ],
        'default': 'unknown',
        'mutable': True
    },

    'time_context': {
        'type': 'select',
        'values': [
            'unknown',
            'rush_hour',
            'leisure_time',
            'shopping_time',
            'tourist_hours',
            'lunch_break',
            'evening_stroll'
        ],
        'default': 'unknown',
        'mutable': True
    }
}

# Action ID mapping
ACTION_ID_MAP = {}  # Generated dynamically from attribute combinations
```

---

## Metrics Logging

### Module: metrics_logging/metrics_logger.py
**Purpose**: Central metrics collection and storage

```python
class MetricsLogger:
    def __init__(self, storage_dir='data/metrics'):
        """Initialize metrics logger"""
        self.storage_dir = Path(storage_dir)
        self.dedup_window = 5  # seconds

    def log_metric(self, project_id, event_type, data):
        """
        Log metric event with deduplication

        Event Types:
        - ingest_time: Input processing duration
        - task_ready: Task creation completion
        - annotation_start: Annotator begins work
        - annotation_end: Annotator completes work
        - job_completed: CVAT job finished
        - export_time: Dataset generation duration

        Storage Format:
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "project_id": "proj_123",
            "event_type": "annotation_end",
            "data": {
                "annotator": "user1",
                "task_id": 456,
                "duration": 120.5
            }
        }
        """

    def read_metrics(self, project_id, start_date=None, end_date=None):
        """Read metrics with optional date filtering"""

    def calculate_statistics(self, project_id):
        """
        Calculate aggregate statistics

        Returns:
            {
                'clips_per_annotator': {...},
                'avg_time_per_clip': 120.5,
                'total_active_time': 3600,
                'throughput': 15.2,
                'makespan': 7200
            }
        """
```

---

## Deployment Configuration

### Main Application (final_Depolyement_setup/main.py)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    pre_annotation,
    task_creator,
    quality_control,
    metrics
)

# Initialize FastAPI app
app = FastAPI(
    title="AVA Kinetics QC API",
    description="Quality Control API for AVA Kinetics annotation pipeline",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(pre_annotation.router, prefix="/pre-annotation")
app.include_router(task_creator.router, prefix="/task-creator")
app.include_router(quality_control.router, prefix="/quality-control")
app.include_router(metrics.router, prefix="/metrics")

@app.get("/")
async def root():
    return {
        "message": "AVA Kinetics QC API",
        "documentation": "/docs",
        "health": "ok"
    }

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    # Initialize database connection pool
    # Load configuration
    # Warm up ML models
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    # Close database connections
    # Save pending metrics
    pass
```

### Configuration Management (config.py)

```python
from pydantic import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application configuration"""

    # Application
    APP_NAME: str = "AVA Kinetics QC"
    ENV: str = "development"
    DEBUG: bool = False

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "ava_kinetics"
    DB_USER: str
    DB_PASSWORD: str

    # CVAT
    CVAT_HOST: str = "http://localhost:8080"
    CVAT_USERNAME: str
    CVAT_PASSWORD: str

    # AWS S3
    S3_BUCKET_NAME: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    USE_IAM_ROLE: bool = False

    # Paths
    DATA_DIR: str = "/data"
    UPLOAD_DIR: str = "/data/uploads"
    OUTPUT_DIR: str = "/data/outputs"
    METRICS_DIR: str = "/data/metrics"

    # ML Models
    RFDETR_MODEL_PATH: str = "rf-detr-medium.pth"
    YOLOX_MODEL_PATH: str = "yolox_s.pth"

    # Processing
    MAX_WORKERS: int = 4
    BATCH_SIZE: int = 32
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024 * 1024  # 5GB

    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
```

### Database Connection (database.py)

```python
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config import settings

class DatabasePool:
    """Database connection pool manager"""

    def __init__(self):
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.pool.putconn(conn)

    def close(self):
        """Close all connections"""
        self.pool.closeall()

# Global database pool
db_pool = DatabasePool()
```

---

## Database Architecture

### Schema Design

```sql
-- Projects table
CREATE TABLE projects (
    project_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    organization_slug VARCHAR(100) DEFAULT 'default',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB
);

-- Tasks table
CREATE TABLE tasks (
    task_id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'annotation',
    assignee VARCHAR(100),
    video_clip VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retrieved_at TIMESTAMP,
    qc_status VARCHAR(50) DEFAULT 'pending',
    overlap_group INTEGER,
    partner_task_id INTEGER REFERENCES tasks(task_id),
    metadata JSONB,
    INDEX idx_project_status (project_id, status),
    INDEX idx_overlap_group (overlap_group),
    INDEX idx_qc_status (qc_status)
);

-- Annotations table
CREATE TABLE annotations (
    annotation_id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(task_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    frame INTEGER NOT NULL,
    xtl FLOAT NOT NULL,
    ytl FLOAT NOT NULL,
    xbr FLOAT NOT NULL,
    ybr FLOAT NOT NULL,
    outside BOOLEAN DEFAULT FALSE,
    occluded BOOLEAN DEFAULT FALSE,
    attributes JSONB NOT NULL,
    annotator VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence FLOAT DEFAULT 1.0,
    INDEX idx_task_frame (task_id, frame),
    INDEX idx_track (task_id, track_id),
    UNIQUE KEY unique_annotation (task_id, track_id, frame)
);

-- Quality metrics table
CREATE TABLE quality_metrics (
    metric_id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    task_group VARCHAR(100),
    metric_type VARCHAR(50) NOT NULL,
    metric_value FLOAT NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    INDEX idx_project_metrics (project_id, metric_type),
    INDEX idx_task_group (task_group)
);

-- Create views for reporting
CREATE VIEW task_summary AS
SELECT
    p.name as project_name,
    t.task_id,
    t.name as task_name,
    t.assignee,
    t.status,
    t.qc_status,
    COUNT(DISTINCT a.annotation_id) as annotation_count,
    COUNT(DISTINCT a.track_id) as track_count,
    COUNT(DISTINCT a.frame) as frame_count,
    AVG(a.confidence) as avg_confidence
FROM projects p
JOIN tasks t ON p.project_id = t.project_id
LEFT JOIN annotations a ON t.task_id = a.task_id
GROUP BY p.name, t.task_id;

CREATE VIEW annotator_performance AS
SELECT
    annotator,
    COUNT(DISTINCT task_id) as tasks_completed,
    COUNT(*) as total_annotations,
    AVG(confidence) as avg_confidence,
    MIN(created_at) as first_annotation,
    MAX(created_at) as last_annotation
FROM annotations
GROUP BY annotator;
```

---

## API Reference

### Pre-Annotation Endpoints

#### Generate Upload URLs
```http
POST /pre-annotation/get-upload-urls
Content-Type: application/json

{
    "project_id": "proj_123",
    "file_names": ["proposals.pkl", "frames.zip"]
}

Response: 200 OK
{
    "upload_urls": {
        "proposals.pkl": "https://s3.amazonaws.com/...",
        "frames.zip": "https://s3.amazonaws.com/..."
    },
    "expires_in": 3600
}
```

#### Process Clips from S3
```http
POST /pre-annotation/process-clips-s3
Content-Type: application/json

{
    "project_id": "proj_123",
    "proposals_key": "uploads/proj_123/proposals.pkl",
    "frames_key": "uploads/proj_123/frames.zip"
}

Response: 200 OK
{
    "status": "processing",
    "job_id": "job_456",
    "estimated_time": 300
}
```

### Task Creator Endpoints

#### Create Project
```http
POST /task-creator/create-project-s3
Content-Type: application/json

{
    "project_name": "Street Scenes Q1 2024",
    "organization": "default",
    "annotators": ["user1", "user2", "user3"],
    "overlap_percentage": 20,
    "package_keys": [
        "packages/user1.zip",
        "packages/user2.zip"
    ]
}

Response: 201 Created
{
    "project_id": 123,
    "tasks_created": 10,
    "message": "Project created successfully"
}
```

### Quality Control Endpoints

#### Update QC Status
```http
PATCH /quality-control/update-status
Content-Type: application/json

{
    "task_id": 456,
    "qc_status": "approved",
    "notes": "High quality annotations"
}

Response: 200 OK
{
    "task_id": 456,
    "qc_status": "approved",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

#### Generate Dataset
```http
POST /quality-control/generate-dataset
Content-Type: application/json

{
    "project_id": 123,
    "format": "ava_csv",
    "approved_only": true,
    "consensus_strategy": "majority_vote"
}

Response: 200 OK
{
    "dataset_url": "https://s3.amazonaws.com/datasets/proj_123.csv",
    "rows": 10000,
    "unique_videos": 100,
    "unique_actions": 25,
    "expires_in": 86400
}
```

### Metrics Endpoints

#### Get Metrics Summary
```http
GET /metrics/summary?project_id=123

Response: 200 OK
{
    "project_id": 123,
    "metrics": {
        "total_clips": 1000,
        "completed_clips": 850,
        "clips_per_annotator": {
            "user1": 300,
            "user2": 280,
            "user3": 270
        },
        "avg_time_per_clip": 120.5,
        "total_active_time": 3600,
        "throughput": 15.2,
        "quality_scores": {
            "mean_iou": 0.75,
            "mean_kappa": 0.68
        }
    }
}
```

---

## Integration Points

### CVAT Integration

The system integrates with CVAT through:
1. **REST API**: Project/task management
2. **Webhooks**: Job completion notifications
3. **Data Formats**: CVAT XML 1.1 for import/export

### AWS S3 Integration

S3 is used for:
1. **Large File Uploads**: Pre-signed URLs for direct browser uploads
2. **Dataset Storage**: Final datasets archived in S3
3. **Metrics Backup**: Long-term metrics storage

Configuration options:
- **IAM Role**: Preferred for EC2 deployments
- **Access Keys**: For local development

### PostgreSQL Integration

Database features utilized:
1. **Connection Pooling**: 1-20 concurrent connections
2. **JSONB**: Flexible attribute storage
3. **Transactions**: ACID compliance
4. **Indexes**: Optimized queries

---

## Workflow Documentation

### Complete Annotation Workflow

1. **Video Upload**
   - Upload raw videos as ZIP
   - System extracts and preprocesses

2. **Proposal Generation**
   - Select keyframes intelligently
   - Detect persons using RF-DETR/YOLOX
   - Track across frames
   - Generate dense proposals

3. **Task Creation**
   - Convert proposals to CVAT XML
   - Create project with action labels
   - Generate overlapping assignments
   - Upload to CVAT

4. **Annotation Phase**
   - Annotators login to CVAT
   - Refine bounding boxes
   - Add action attributes
   - Submit completed work

5. **Quality Control**
   - Calculate IoU between annotators
   - Compute Cohen's Kappa
   - Apply validation rules
   - Route for adjudication if needed

6. **Dataset Generation**
   - Apply consensus logic
   - Generate AVA format CSV
   - Upload to S3
   - Send download link

---

## Installation Guide

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Docker 20.10+
- CUDA 11.0+ (for GPU acceleration)
- 16GB+ RAM
- 100GB+ storage

### Installation Steps

#### 1. Clone Repository
```bash
cd /Users/Surya/AVA_Kinetics
git clone <repository-url> AVA_Kinetics_QC
cd AVA_Kinetics_QC
```

#### 2. Setup Python Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Download Models
```bash
# Download RF-DETR model
wget <model-url> -O rf-detr-medium.pth

# Download YOLOX model
wget <model-url> -O yolox_s.pth
```

#### 4. Configure Environment
```bash
cp example.env .env
# Edit .env with your configuration
nano .env
```

#### 5. Setup Database
```bash
# Create database
createdb ava_kinetics

# Run migrations
psql ava_kinetics < database/schema.sql
```

#### 6. Start CVAT
```bash
cd cvat
docker-compose up -d
```

#### 7. Start Services
```bash
# Start API server
uvicorn final_Depolyement_setup.main:app --reload

# Start Streamlit dashboards (in separate terminals)
streamlit run processing_pipeline/app.py --server.port 8501
streamlit run processing_pipeline/admin_app.py --server.port 8502
streamlit run processing_pipeline/qc_app.py --server.port 8503
```

### Docker Deployment

```bash
# Build container
docker build -t ava-kinetics-qc .

# Run with docker-compose
docker-compose up -d
```

---

## Troubleshooting

### Common Issues

#### Issue: CVAT Connection Failed
```
Error: Failed to authenticate with CVAT
```
**Solution**: Verify CVAT credentials and URL in .env file

#### Issue: Database Connection Pool Exhausted
```
Error: connection pool exhausted
```
**Solution**: Increase max connections in database.py or optimize queries

#### Issue: S3 Upload Failed
```
Error: Access Denied
```
**Solution**: Check AWS credentials or IAM role permissions

#### Issue: Low Inter-Annotator Agreement
```
Warning: Kappa score below threshold
```
**Solution**: Review annotation guidelines, provide training

#### Issue: Slow Proposal Generation
```
Performance: Processing taking too long
```
**Solution**: Enable GPU, reduce batch size, or parallelize

### Debug Mode

Enable debug logging:
```python
# In .env
DEBUG=True
LOG_LEVEL=DEBUG
```

### Performance Optimization

1. **Enable GPU**: Set DEVICE=cuda in configuration
2. **Increase Workers**: Adjust MAX_WORKERS for parallelization
3. **Optimize Batch Size**: Tune BATCH_SIZE for your hardware
4. **Database Indexes**: Ensure indexes are created
5. **Cache Results**: Use Redis for frequently accessed data

---

## Appendix

### A. Performance Benchmarks

| Operation | CPU Time | GPU Time | Throughput |
|-----------|----------|----------|------------|
| Keyframe Selection | 3s/video | 0.5s/video | 120 videos/min (GPU) |
| Person Detection | 2s/frame | 0.2s/frame | 300 frames/min (GPU) |
| XML Generation | 0.1s/file | - | 600 files/min |
| Quality Calculation | 1s/pair | - | 60 pairs/min |
| Dataset Generation | 10s/1000rows | - | 6000 rows/min |

### B. System Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| CPU | 4 cores | 8 cores | 16 cores |
| RAM | 8 GB | 16 GB | 32 GB |
| GPU | - | GTX 1080 | RTX 3090 |
| Storage | 100 GB | 500 GB | 2 TB SSD |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

### C. Attribute Action Mapping

| Attribute Combination | Action ID | Description |
|----------------------|-----------|-------------|
| walking_behavior=normal, phone_usage=no | 1 | Normal walking |
| walking_behavior=normal, phone_usage=texting | 2 | Walking while texting |
| walking_behavior=standing, social_interaction=group | 3 | Standing in group |
| ... | ... | ... |

### D. Glossary

- **AVA**: Atomic Visual Actions dataset format
- **CVAT**: Computer Vision Annotation Tool
- **IoU**: Intersection over Union (spatial agreement metric)
- **Kappa**: Cohen's Kappa (categorical agreement metric)
- **RF-DETR**: Recurrent Feature Detection Transformer
- **YOLOX**: You Only Look Once X (object detector)
- **ByteTracker**: Simple online multi-object tracking algorithm

---

## Support Information

- **Documentation**: /documentation/
- **API Docs**: http://localhost:8000/docs
- **CVAT UI**: http://localhost:8080
- **Admin Dashboard**: http://localhost:8502
- **Metrics Dashboard**: http://localhost:8503

---

*Document Version: 1.0.0*
*Last Updated: November 2024*
*Total Lines of Code: ~15,000+*