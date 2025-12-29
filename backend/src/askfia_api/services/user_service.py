"""User service for email registration and query tracking using MotherDuck."""

import logging
import os
from contextlib import contextmanager
from datetime import UTC, date, datetime

import duckdb
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class User(BaseModel):
    """User data model."""

    id: str
    email: str
    created_at: datetime
    last_access: datetime | None = None


class QueryUsage(BaseModel):
    """Daily query usage tracking."""

    email: str
    query_date: date
    query_count: int


class UserService:
    """
    Service for managing users and their query quotas.

    Uses DuckDB/MotherDuck for persistent cloud storage of user data.
    Supports both local DuckDB files and MotherDuck cloud connections.
    """

    def __init__(self, db_path: str, daily_limit: int = 50):
        """
        Initialize user service.

        Args:
            db_path: Path to DuckDB file OR MotherDuck connection string (md:database_name)
            daily_limit: Maximum AI queries per day (0 = unlimited)
        """
        self.db_path = db_path
        self.is_motherduck = db_path.startswith("md:")
        self.daily_limit = daily_limit
        self._ensure_database()

    def _ensure_database(self) -> None:
        """Create database and tables if they don't exist."""
        # For MotherDuck, first ensure the database exists
        if self.is_motherduck:
            self._ensure_motherduck_database()

        with self._get_connection() as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR PRIMARY KEY,
                    email VARCHAR UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_access TIMESTAMP
                )
            """)

            # Create index on email for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """)

            # Query usage table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_usage (
                    email VARCHAR,
                    query_date DATE,
                    query_count INTEGER DEFAULT 0,
                    PRIMARY KEY (email, query_date)
                )
            """)

            logger.info(f"User database initialized at {self.db_path}")

    def _ensure_motherduck_database(self) -> None:
        """Ensure the MotherDuck database exists, creating it if necessary."""
        # Extract database name from path (e.g., "md:askfia" -> "askfia")
        db_name = self.db_path.replace("md:", "")

        token = os.environ.get("MOTHERDUCK_TOKEN") or os.environ.get("motherduck_token")
        if not token:
            raise RuntimeError("MotherDuck token not configured")

        # Connect to MotherDuck without specifying a database
        conn = duckdb.connect(f"md:?motherduck_token={token}")
        try:
            # Check if database exists
            result = conn.execute("SHOW DATABASES").fetchall()
            existing_dbs = [row[0] for row in result]

            if db_name not in existing_dbs:
                logger.info(f"Creating MotherDuck database: {db_name}")
                conn.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
                logger.info(f"Created MotherDuck database: {db_name}")
            else:
                logger.debug(f"MotherDuck database already exists: {db_name}")
        finally:
            conn.close()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        if self.is_motherduck:
            # Check for MotherDuck token
            if not os.environ.get("MOTHERDUCK_TOKEN") and not os.environ.get("motherduck_token"):
                raise RuntimeError(
                    "MotherDuck token not configured. Set MOTHERDUCK_TOKEN environment variable."
                )
            # MotherDuck connection
            conn = duckdb.connect(self.db_path, read_only=False)
            logger.debug(f"Connected to MotherDuck: {self.db_path}")
        else:
            # Local DuckDB file
            conn = duckdb.connect(self.db_path, read_only=False)
            logger.debug(f"Connected to local DuckDB: {self.db_path}")
        try:
            yield conn
        finally:
            conn.close()

    def register_user(self, email: str) -> tuple[User, bool]:
        """
        Register a new user or return existing user.

        Args:
            email: User's email address

        Returns:
            Tuple of (User, is_new_user)
        """
        import uuid

        email = email.lower().strip()
        now = datetime.now(UTC)

        with self._get_connection() as conn:
            # Try to get existing user
            result = conn.execute(
                "SELECT id, email, created_at, last_access FROM users WHERE email = ?",
                [email],
            )
            row = result.fetchone()

            if row:
                # Update last access
                conn.execute(
                    "UPDATE users SET last_access = ? WHERE email = ?",
                    [now, email],
                )
                logger.info(f"Existing user logged in: {email}")
                created_at = row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(str(row[2]))
                return User(
                    id=row[0],
                    email=row[1],
                    created_at=created_at,
                    last_access=now,
                ), False

            # Create new user
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, email, created_at, last_access) VALUES (?, ?, ?, ?)",
                [user_id, email, now, now],
            )
            logger.info(f"New user registered: {email}")

            return User(id=user_id, email=email, created_at=now, last_access=now), True

    def get_user(self, email: str) -> User | None:
        """
        Get a user by email.

        Args:
            email: User's email address

        Returns:
            User if found, None otherwise
        """
        email = email.lower().strip()

        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT id, email, created_at, last_access FROM users WHERE email = ?",
                [email],
            )
            row = result.fetchone()

            if not row:
                return None

            created_at = row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(str(row[2]))
            last_access = None
            if row[3]:
                last_access = row[3] if isinstance(row[3], datetime) else datetime.fromisoformat(str(row[3]))

            return User(
                id=row[0],
                email=row[1],
                created_at=created_at,
                last_access=last_access,
            )

    def get_queries_remaining(self, email: str) -> int:
        """
        Get remaining queries for today.

        Args:
            email: User's email address

        Returns:
            Number of queries remaining today (999999 if unlimited)
        """
        if self.daily_limit <= 0:
            return 999999  # Unlimited

        email = email.lower().strip()
        today = date.today()

        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT query_count FROM query_usage WHERE email = ? AND query_date = ?",
                [email, today],
            )
            row = result.fetchone()

            if not row:
                return self.daily_limit

            return max(0, self.daily_limit - row[0])

    def increment_usage(self, email: str) -> int:
        """
        Increment query count for today.

        Args:
            email: User's email address

        Returns:
            New query count for today
        """
        email = email.lower().strip()
        today = date.today()

        with self._get_connection() as conn:
            # Upsert query count
            conn.execute(
                """
                INSERT INTO query_usage (email, query_date, query_count)
                VALUES (?, ?, 1)
                ON CONFLICT (email, query_date)
                DO UPDATE SET query_count = query_usage.query_count + 1
                """,
                [email, today],
            )

            # Get new count
            result = conn.execute(
                "SELECT query_count FROM query_usage WHERE email = ? AND query_date = ?",
                [email, today],
            )
            row = result.fetchone()
            return row[0] if row else 1

    def check_quota(self, email: str) -> tuple[bool, int]:
        """
        Check if user has remaining quota.

        Args:
            email: User's email address

        Returns:
            Tuple of (has_quota, queries_remaining)
        """
        remaining = self.get_queries_remaining(email)
        if self.daily_limit <= 0:
            return True, remaining  # Unlimited
        return remaining > 0, remaining

    def get_user_stats(self, email: str) -> dict:
        """
        Get comprehensive stats for a user.

        Args:
            email: User's email address

        Returns:
            Dict with user statistics
        """
        email = email.lower().strip()
        today = date.today()

        with self._get_connection() as conn:
            # Get user info
            result = conn.execute(
                "SELECT id, email, created_at, last_access FROM users WHERE email = ?",
                [email],
            )
            user_row = result.fetchone()

            if not user_row:
                return {"error": "User not found"}

            # Get today's usage
            result = conn.execute(
                "SELECT query_count FROM query_usage WHERE email = ? AND query_date = ?",
                [email, today],
            )
            usage_row = result.fetchone()
            queries_used = usage_row[0] if usage_row else 0

            # Get total queries all time
            result = conn.execute(
                "SELECT SUM(query_count) as total FROM query_usage WHERE email = ?",
                [email],
            )
            total_row = result.fetchone()
            total_queries = total_row[0] or 0

            return {
                "id": user_row[0],
                "email": user_row[1],
                "created_at": str(user_row[2]),
                "last_access": str(user_row[3]) if user_row[3] else None,
                "queries_used_today": queries_used,
                "queries_remaining_today": self.get_queries_remaining(email),
                "daily_limit": self.daily_limit if self.daily_limit > 0 else None,
                "total_queries_all_time": total_queries,
            }

    def get_total_users(self) -> int:
        """Get total number of registered users."""
        with self._get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM users")
            row = result.fetchone()
            return row[0] if row else 0

    def get_all_users(self) -> list[User]:
        """Get all registered users."""
        with self._get_connection() as conn:
            result = conn.execute(
                "SELECT id, email, created_at, last_access FROM users ORDER BY created_at DESC"
            )
            rows = result.fetchall()

            users = []
            for row in rows:
                created_at = row[2] if isinstance(row[2], datetime) else datetime.fromisoformat(str(row[2]))
                last_access = None
                if row[3]:
                    last_access = row[3] if isinstance(row[3], datetime) else datetime.fromisoformat(str(row[3]))
                users.append(User(
                    id=row[0],
                    email=row[1],
                    created_at=created_at,
                    last_access=last_access,
                ))
            return users
