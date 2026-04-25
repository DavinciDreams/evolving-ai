"""
Persistent data storage manager for the self-improving agent.
Ensures all data is preserved across sessions.
"""

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.config import config
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class PersistentDataManager:
    """Manages persistent storage for all agent components."""

    def __init__(self):
        self.data_dir = Path(config.memory_persist_directory).parent / "persistent_data"
        self.session_file = self.data_dir / "session_data.json"
        self.agent_state_file = self.data_dir / "agent_state.json"
        self.interactions_db = self.data_dir / "interactions.db"
        self.evaluations_file = self.data_dir / "evaluations.json"
        self.modifications_log = self.data_dir / "modifications.json"

        self.session_id = None
        self.session_start_time = None

    async def initialize(self):
        """Initialize persistent data manager."""
        try:
            logger.info("Initializing persistent data manager...")

            # Ensure data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Initialize session
            await self._start_new_session()

            # Initialize interactions database
            await self._initialize_interactions_db()

            # Load previous agent state
            await self._load_agent_state()

            logger.info("Persistent data manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize persistent data manager: {e}")
            raise

    async def _start_new_session(self):
        """Start a new session and save session data."""
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_start_time = datetime.now()

        session_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "end_time": None,
            "total_interactions": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "modifications_made": 0,
            "memories_added": 0,
            "knowledge_added": 0,
        }

        await self._save_json(self.session_file, session_data)
        logger.info(f"Started new session: {self.session_id}")

    async def _initialize_interactions_db(self):
        """Initialize SQLite database for interactions."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            # Create interactions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    conversation_id TEXT,
                    timestamp DATETIME NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    evaluation_score REAL,
                    context_used TEXT,
                    improvement_applied BOOLEAN DEFAULT FALSE,
                    metadata TEXT
                )
            """
            )

            # Create evaluations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_id INTEGER,
                    timestamp DATETIME NOT NULL,
                    overall_score REAL NOT NULL,
                    criteria_scores TEXT,
                    feedback TEXT,
                    improvement_suggestions TEXT,
                    confidence REAL,
                    FOREIGN KEY (interaction_id) REFERENCES interactions (id)
                )
            """
            )

            # Create modifications table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS modifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    component TEXT NOT NULL,
                    modification_type TEXT NOT NULL,
                    description TEXT,
                    success BOOLEAN,
                    backup_path TEXT,
                    metadata TEXT
                )
            """
            )

            # Migration: Add conversation_id column if it doesn't exist
            cursor.execute("PRAGMA table_info(interactions)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'conversation_id' not in columns:
                logger.info("Adding conversation_id column to interactions table")
                cursor.execute(
                    "ALTER TABLE interactions ADD COLUMN conversation_id TEXT"
                )
                conn.commit()

            # preferences table: stores (worse, better) response pairs for proto-DPO
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    query TEXT NOT NULL,
                    original_response TEXT NOT NULL,
                    improved_response TEXT NOT NULL,
                    original_score REAL NOT NULL,
                    improved_score REAL NOT NULL,
                    score_delta REAL NOT NULL
                )
            """)

            # user_feedback table: stores explicit human ratings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_id INTEGER,
                    timestamp DATETIME NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    FOREIGN KEY (interaction_id) REFERENCES interactions (id)
                )
            """)

            # lessons table: stores LLM-extracted lessons for Reflexion
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    lesson_text TEXT NOT NULL,
                    source TEXT DEFAULT 'reflexion'
                )
            """)

            conn.commit()
            conn.close()

            logger.info("Interactions database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize interactions database: {e}")
            raise

    async def _load_agent_state(self):
        """Load previous agent state if available."""
        if self.agent_state_file.exists():
            try:
                agent_state = await self._load_json(self.agent_state_file)
                logger.info(f"Loaded agent state from {self.agent_state_file}")
                return agent_state
            except Exception as e:
                logger.warning(f"Failed to load agent state: {e}")

        return {}

    async def save_interaction(
        self,
        query: str,
        response: str,
        evaluation_score: Optional[float] = None,
        context_used: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> int:
        """Save an interaction to the database."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO interactions
                (session_id, conversation_id, timestamp, query, response, evaluation_score, context_used, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.session_id,
                    conversation_id,
                    datetime.now().isoformat(),
                    query,
                    response,
                    evaluation_score,
                    json.dumps(context_used) if context_used else None,
                    json.dumps(metadata) if metadata else None,
                ),
            )

            interaction_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Update session stats
            await self._update_session_stats("total_interactions", 1)

            logger.info(f"Saved interaction {interaction_id}" + (f" (conversation: {conversation_id})" if conversation_id else ""))
            return interaction_id

        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
            raise

    async def save_evaluation(
        self,
        interaction_id: int,
        overall_score: float,
        criteria_scores: Dict[str, float],
        feedback: str,
        improvement_suggestions: List[str],
        confidence: float,
    ):
        """Save an evaluation to the database."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO evaluations 
                (interaction_id, timestamp, overall_score, criteria_scores, feedback, improvement_suggestions, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    interaction_id,
                    datetime.now().isoformat(),
                    overall_score,
                    json.dumps(criteria_scores),
                    feedback,
                    json.dumps(improvement_suggestions),
                    confidence,
                ),
            )

            conn.commit()
            conn.close()

            # Update session stats
            await self._update_session_stats("successful_evaluations", 1)

            logger.info(f"Saved evaluation for interaction {interaction_id}")

        except Exception as e:
            logger.error(f"Failed to save evaluation: {e}")
            await self._update_session_stats("failed_evaluations", 1)
            raise

    async def save_modification(
        self,
        component: str,
        modification_type: str,
        description: str,
        success: bool,
        backup_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Save a modification record."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO modifications 
                (session_id, timestamp, component, modification_type, description, success, backup_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.session_id,
                    datetime.now().isoformat(),
                    component,
                    modification_type,
                    description,
                    success,
                    backup_path,
                    json.dumps(metadata) if metadata else None,
                ),
            )

            conn.commit()
            conn.close()

            # Update session stats
            if success:
                await self._update_session_stats("modifications_made", 1)

            logger.info(f"Saved modification record for {component}")

        except Exception as e:
            logger.error(f"Failed to save modification: {e}")
            raise

    async def get_recent_interactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent interactions from the database."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM interactions
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            columns = [desc[0] for desc in cursor.description]
            interactions = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()
            return interactions

        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []

    async def get_conversation_history(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all interactions for a specific conversation."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            query = """
                SELECT * FROM interactions
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """
            params = [conversation_id]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)

            columns = [desc[0] for desc in cursor.description]
            interactions = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()
            logger.info(f"Retrieved {len(interactions)} interactions for conversation {conversation_id}")
            return interactions

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def get_session_statistics(self) -> Dict[str, Any]:
        """Get statistics for the current session."""
        try:
            session_data = await self._load_json(self.session_file)

            # Add computed statistics
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()

            # Get interaction count for this session
            cursor.execute(
                """
                SELECT COUNT(*) FROM interactions WHERE session_id = ?
            """,
                (self.session_id,),
            )
            interaction_count = cursor.fetchone()[0]

            # Get average evaluation score
            cursor.execute(
                (
                    "SELECT AVG(evaluation_score) "
                    "FROM interactions "
                    "WHERE session_id = ? AND evaluation_score IS NOT NULL"
                ),
                (self.session_id,),
            )
            result = cursor.fetchone()
            avg_score = result[0] if result and result[0] is not None else 0.0

            conn.close()

            session_data.update(
                {
                    "current_interactions": interaction_count,
                    "average_evaluation_score": avg_score,
                    "session_duration_minutes": (
                        datetime.now() - self.session_start_time
                    ).total_seconds()
                    / 60,
                }
            )

            return session_data

        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}

    async def save_agent_state(self, state: Dict[str, Any]):
        """Save current agent state."""
        try:
            state["last_updated"] = datetime.now().isoformat()
            state["session_id"] = self.session_id

            await self._save_json(self.agent_state_file, state)
            logger.info("Agent state saved")

        except Exception as e:
            logger.error(f"Failed to save agent state: {e}")
            raise

    async def create_backup(self, component: str) -> str:
        """Create a backup of component data."""
        try:
            backup_dir = Path(config.backup_directory)
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{component}_backup_{timestamp}"
            backup_path = backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            # Copy relevant files based on component
            if component == "memory":
                memory_dir = Path(config.memory_persist_directory)
                if memory_dir.exists():
                    shutil.copytree(memory_dir, backup_path / "memory")

            elif component == "knowledge":
                knowledge_dir = Path(config.knowledge_base_path)
                if knowledge_dir.exists():
                    shutil.copytree(knowledge_dir, backup_path / "knowledge")

            elif component == "agent_state":
                if self.agent_state_file.exists():
                    shutil.copy2(
                        self.agent_state_file, backup_path / "agent_state.json"
                    )
                else:
                    # Create empty state file for backup
                    (backup_path / "agent_state.json").write_text("{}")

            elif component == "interactions":
                if self.interactions_db.exists():
                    shutil.copy2(self.interactions_db, backup_path / "interactions.db")

            logger.info(f"Created backup: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Failed to create backup for {component}: {e}")
            raise

    async def _update_session_stats(self, stat_name: str, increment: int = 1):
        """Update session statistics."""
        try:
            session_data = await self._load_json(self.session_file)
            session_data[stat_name] = session_data.get(stat_name, 0) + increment
            await self._save_json(self.session_file, session_data)
        except Exception as e:
            logger.warning(f"Failed to update session stats: {e}")

    async def _save_json(self, file_path: Path, data: Dict[str, Any]):
        """Save data to JSON file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def _load_json(self, file_path: Path) -> Dict[str, Any]:
        """Load data from JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def cleanup(self):
        """Clean up and finalize session data."""
        try:
            # Update session end time
            session_data = await self._load_json(self.session_file)
            session_data["end_time"] = datetime.now().isoformat()
            await self._save_json(self.session_file, session_data)

            logger.info(f"Session {self.session_id} finalized")

        except Exception as e:
            logger.error(f"Failed to cleanup session: {e}")

    async def get_recent_evaluations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent N evaluation rows joined with interaction query."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.overall_score, e.criteria_scores, e.feedback,
                       e.improvement_suggestions, e.confidence, e.timestamp,
                       i.query
                FROM evaluations e
                LEFT JOIN interactions i ON e.interaction_id = i.id
                ORDER BY e.timestamp DESC
                LIMIT ?
            """, (limit,))
            columns = ["overall_score", "criteria_scores", "feedback",
                       "improvement_suggestions", "confidence", "timestamp", "query"]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to get recent evaluations: {e}")
            return []

    async def save_preference_pair(
        self,
        query: str,
        original_response: str,
        improved_response: str,
        original_score: float,
        improved_score: float,
    ) -> int:
        """Save a (worse, better) response pair for preference learning."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO preferences
                (timestamp, query, original_response, improved_response,
                 original_score, improved_score, score_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                query,
                original_response,
                improved_response,
                original_score,
                improved_score,
                improved_score - original_score,
            ))
            pair_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return pair_id
        except Exception as e:
            logger.error(f"Failed to save preference pair: {e}")
            return -1

    async def save_user_feedback(
        self,
        interaction_id: int,
        rating: int,
        comment: Optional[str] = None,
    ) -> int:
        """Save explicit human feedback (rating +1 or -1) for an interaction."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_feedback (interaction_id, timestamp, rating, comment)
                VALUES (?, ?, ?, ?)
            """, (interaction_id, datetime.now().isoformat(), rating, comment))
            feedback_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"Saved user feedback {feedback_id} for interaction {interaction_id}: {rating}")
            return feedback_id
        except Exception as e:
            logger.error(f"Failed to save user feedback: {e}")
            return -1

    async def save_learned_lessons(self, lessons: List[str]) -> None:
        """Persist Reflexion lessons (replaces previous lesson set)."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()
            # Keep history but mark old lessons; insert new batch
            cursor.executemany("""
                INSERT INTO lessons (timestamp, lesson_text, source)
                VALUES (?, ?, 'reflexion')
            """, [(datetime.now().isoformat(), lesson) for lesson in lessons])
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(lessons)} learned lessons")
        except Exception as e:
            logger.error(f"Failed to save learned lessons: {e}")

    async def get_learned_lessons(self, limit: int = 10) -> List[str]:
        """Return the most recent learned lessons."""
        try:
            conn = sqlite3.connect(self.interactions_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lesson_text FROM lessons
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            lessons = [row[0] for row in cursor.fetchall()]
            conn.close()
            return lessons
        except Exception as e:
            logger.error(f"Failed to get learned lessons: {e}")
            return []


# Global persistent data manager instance
persistent_data_manager = PersistentDataManager()
