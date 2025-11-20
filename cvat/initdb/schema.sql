-- initdb/Schema.sql

-- Clean slate
DROP TABLE IF EXISTS audits;
DROP TABLE IF EXISTS qc_flags;
DROP TABLE IF EXISTS golden_annotations;
DROP TABLE IF EXISTS annotations;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS projects;

-- 1. Core Hierarchy
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(project_id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50),
    assignee VARCHAR(255),
    retrieved_at TIMESTAMP WITH TIME ZONE,
    qc_status VARCHAR(50) DEFAULT 'pending'
    -- States: 'pending', 'consensus_pass', 'adjudication_needed', 'audit_pending', 'approved', 'rejected'
);

-- 2. Raw Annotations (From Annotators)
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(task_id),
    keyframe_name VARCHAR(255) NOT NULL, -- Links to Manifest
    person_id INTEGER NOT NULL,
    xtl REAL, ytl REAL, xbr REAL, ybr REAL,
    attributes JSONB
);

-- 3. The Golden Set (From Master Adjudication)
CREATE TABLE IF NOT EXISTS golden_annotations (
    golden_id SERIAL PRIMARY KEY,
    keyframe_name VARCHAR(255) NOT NULL,
    person_id INTEGER NOT NULL,

    -- Metadata to track origin
    original_task_id_A INTEGER,
    original_task_id_B INTEGER,

    -- The Perfect Data
    xtl REAL, ytl REAL, xbr REAL, ybr REAL,
    attributes JSONB,

    adjudicated_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyframe_name, person_id)
);

-- 4. Blind Audits (The Statistical Safety Net)
CREATE TABLE IF NOT EXISTS audits (
    audit_id SERIAL PRIMARY KEY,
    keyframe_name VARCHAR(255) NOT NULL,
    person_id INTEGER NOT NULL,

    original_consensus_attributes JSONB, -- What A & B agreed on
    auditor_attributes JSONB,            -- What Master blindly chose

    is_overturn BOOLEAN,                 -- TRUE if Master disagreed
    auditor_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. QC Flags (For automated rules like Spatial Jitter or Schema Fail)
CREATE TABLE IF NOT EXISTS qc_flags (
    flag_id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(task_id),
    keyframe_name VARCHAR(255),
    issue_type VARCHAR(50), -- e.g., 'SPATIAL_LOW_IOU', 'SCHEMA_FAIL', 'ME_CONFLICT'
    severity VARCHAR(20),   -- 'flag' or 'block'
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
