CREATE DATABASE IF NOT EXISTS railway_dw;
USE railway_dw;

-- =========================================================
-- 1. RAW LAYER: Stores exact source records per batch
-- =========================================================
CREATE TABLE IF NOT EXISTS raw_trains (
    id INT AUTO_INCREMENT PRIMARY KEY,
    train_number VARCHAR(50),
    train_name VARCHAR(150),
    source VARCHAR(100),
    destination VARCHAR(100),
    original_route TEXT,
    diverted_route TEXT,
    batch_id VARCHAR(64) NOT NULL,
    ingested_at DATETIME NOT NULL
);

-- =========================================================
-- 2. REJECTED LAYER: Stores rows failing validation rules
-- =========================================================
CREATE TABLE IF NOT EXISTS rejected_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    train_number VARCHAR(50),
    train_name VARCHAR(150),
    source VARCHAR(100),
    destination VARCHAR(100),
    original_route TEXT,
    diverted_route TEXT,
    rejection_reason TEXT NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    ingested_at DATETIME NOT NULL
);

-- =========================================================
-- 3. CLEAN MASTER TABLE: Validated trains
-- =========================================================
CREATE TABLE IF NOT EXISTS trains (
    train_number VARCHAR(10) PRIMARY KEY,
    train_name VARCHAR(150) NOT NULL,
    source_station VARCHAR(100) NOT NULL,
    destination_station VARCHAR(100) NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- =========================================================
-- 4. NORMALIZED ROUTE TABLE: One row per station stop
-- =========================================================
CREATE TABLE IF NOT EXISTS route_stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL,
    route_type ENUM('ORIGINAL', 'DIVERTED') NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    sequence_no INT NOT NULL,
    UNIQUE KEY uq_train_route_seq (train_number, route_type, sequence_no),
    CONSTRAINT fk_route_train
        FOREIGN KEY (train_number) REFERENCES trains(train_number)
        ON DELETE CASCADE
);

-- =========================================================
-- 5. DIVERSION EVENTS TABLE: Route comparison metadata
-- =========================================================
CREATE TABLE IF NOT EXISTS diversion_events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    train_number VARCHAR(10) NOT NULL,
    original_route TEXT NOT NULL,
    diverted_route TEXT NOT NULL,
    is_diverted BOOLEAN NOT NULL,
    skipped_count INT NOT NULL DEFAULT 0,
    added_count INT NOT NULL DEFAULT 0,
    batch_id VARCHAR(64) NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_train_diversion_pair (train_number, original_route(200), diverted_route(200)),
    CONSTRAINT fk_diversion_train
        FOREIGN KEY (train_number) REFERENCES trains(train_number)
        ON DELETE CASCADE
);

-- =========================================================
-- 6. PIPELINE AUDIT LOG: Execution history & metrics
-- =========================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL UNIQUE,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(20) NOT NULL,
    records_read INT DEFAULT 0,
    records_loaded INT DEFAULT 0,
    records_rejected INT DEFAULT 0,
    error_message TEXT
);