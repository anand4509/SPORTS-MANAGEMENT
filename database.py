import mysql.connector
import streamlit as st


def _settings():
    cfg = st.secrets.get("mysql", {})
    return {
        "host": cfg.get("host", "localhost"),
        "port": int(cfg.get("port", 3306)),
        "user": cfg.get("user", "sports_management"),
        "password": cfg.get("password", "98Anand@12"),
        "database": cfg.get("database", "sports_coordinator_db"),
        "connection_timeout": 5,
    }


def get_connection():
    return mysql.connector.connect(**_settings())


def init_db():
    """Create application tables. The configured DB must already exist."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(60) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('Admin','Coordinator','Secretary') NOT NULL DEFAULT 'Coordinator',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment VARCHAR(40) NOT NULL UNIQUE,
                name VARCHAR(120) NOT NULL,
                department VARCHAR(120) NOT NULL,
                sport VARCHAR(80) NOT NULL,
                team_name VARCHAR(120) DEFAULT '',
                phone VARCHAR(30) DEFAULT '',
                selection_status ENUM('Trial','Selected','Reserve','Not Selected')
                    NOT NULL DEFAULT 'Trial',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_name VARCHAR(150) NOT NULL,
                sport VARCHAR(80) NOT NULL,
                event_date DATE NOT NULL,
                venue VARCHAR(150) DEFAULT '',
                status ENUM('Planned','Ongoing','Completed','Postponed','Cancelled')
                    NOT NULL DEFAULT 'Planned',
                result VARCHAR(255) DEFAULT '',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                player_id INT NOT NULL,
                event_id INT NULL,
                attendance_date DATE NOT NULL,
                status ENUM('Present','Absent','Late','Excused') NOT NULL,
                notes VARCHAR(255) DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_attendance (player_id, event_id, attendance_date),
                CONSTRAINT fk_att_player FOREIGN KEY (player_id)
                    REFERENCES players(id) ON DELETE CASCADE,
                CONSTRAINT fk_att_event FOREIGN KEY (event_id)
                    REFERENCES events(id) ON DELETE SET NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                player_id INT NULL,
                player_name VARCHAR(120) NOT NULL,
                sport VARCHAR(80) NOT NULL,
                achievement VARCHAR(180) NOT NULL,
                competition VARCHAR(150) DEFAULT '',
                achievement_date DATE NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_ach_player FOREIGN KEY (player_id)
                    REFERENCES players(id) ON DELETE SET NULL
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS achievement_files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                achievement_id INT NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                stored_filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_file_achievement
                    FOREIGN KEY (achievement_id)
                    REFERENCES achievements(id)
                    ON DELETE CASCADE
            )
        """)

        conn.commit()
        cur.close()
    finally:
        conn.close()


def query_df(sql, params=()):
    import pandas as pd
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        result = cur.lastrowid
        cur.close()
        return result
    finally:
        conn.close()
