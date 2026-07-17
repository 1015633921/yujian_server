from __future__ import annotations


VERSION = "20260717_09_community_ugc_core"


MYSQL_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS community_ugc_posts (
      post_id VARCHAR(80) PRIMARY KEY,
      owner_user_id VARCHAR(100) NOT NULL,
      title VARCHAR(120) NOT NULL,
      content TEXT NOT NULL,
      image_urls_json LONGTEXT NOT NULL,
      tags_json LONGTEXT NOT NULL,
      design_id VARCHAR(80),
      source_post_id VARCHAR(80),
      status VARCHAR(20) NOT NULL DEFAULT 'draft',
      submitted_at VARCHAR(40),
      published_at VARCHAR(40),
      deleted_at VARCHAR(40),
      created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL,
      INDEX idx_ugc_posts_public (status, published_at, post_id),
      INDEX idx_ugc_posts_owner (owner_user_id, status, updated_at),
      INDEX idx_ugc_posts_source (source_post_id),
      INDEX idx_ugc_posts_design (design_id, post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_likes (
      post_id VARCHAR(80) NOT NULL,
      user_id VARCHAR(100) NOT NULL,
      created_at VARCHAR(40) NOT NULL,
      PRIMARY KEY (post_id, user_id),
      INDEX idx_ugc_likes_user (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_saves (
      post_id VARCHAR(80) NOT NULL,
      user_id VARCHAR(100) NOT NULL,
      created_at VARCHAR(40) NOT NULL,
      PRIMARY KEY (post_id, user_id),
      INDEX idx_ugc_saves_user (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_comments (
      comment_id VARCHAR(80) PRIMARY KEY,
      post_id VARCHAR(80) NOT NULL,
      author_user_id VARCHAR(100) NOT NULL,
      content VARCHAR(500) NOT NULL,
      status VARCHAR(20) NOT NULL DEFAULT 'active',
      deleted_at VARCHAR(40),
      created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL,
      INDEX idx_ugc_comments_post (post_id, status, created_at),
      INDEX idx_ugc_comments_author (author_user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_follows (
      follower_user_id VARCHAR(100) NOT NULL,
      followed_user_id VARCHAR(100) NOT NULL,
      created_at VARCHAR(40) NOT NULL,
      PRIMARY KEY (follower_user_id, followed_user_id),
      INDEX idx_ugc_follows_followed (followed_user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_reports (
      report_id VARCHAR(80) PRIMARY KEY,
      reporter_user_id VARCHAR(100) NOT NULL,
      target_type VARCHAR(20) NOT NULL,
      target_id VARCHAR(80) NOT NULL,
      reason VARCHAR(40) NOT NULL,
      detail VARCHAR(500),
      status VARCHAR(20) NOT NULL DEFAULT 'open',
      created_at VARCHAR(40) NOT NULL,
      updated_at VARCHAR(40) NOT NULL,
      UNIQUE KEY ux_ugc_reporter_target (reporter_user_id, target_type, target_id),
      INDEX idx_ugc_reports_target (target_type, target_id, status),
      INDEX idx_ugc_reports_status (status, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
)


SQLITE_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS community_ugc_posts (
      post_id TEXT PRIMARY KEY,
      owner_user_id TEXT NOT NULL,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      image_urls_json TEXT NOT NULL,
      tags_json TEXT NOT NULL,
      design_id TEXT,
      source_post_id TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      submitted_at TEXT,
      published_at TEXT,
      deleted_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_likes (
      post_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (post_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_saves (
      post_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (post_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_comments (
      comment_id TEXT PRIMARY KEY,
      post_id TEXT NOT NULL,
      author_user_id TEXT NOT NULL,
      content TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      deleted_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_follows (
      follower_user_id TEXT NOT NULL,
      followed_user_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (follower_user_id, followed_user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_ugc_reports (
      report_id TEXT PRIMARY KEY,
      reporter_user_id TEXT NOT NULL,
      target_type TEXT NOT NULL,
      target_id TEXT NOT NULL,
      reason TEXT NOT NULL,
      detail TEXT,
      status TEXT NOT NULL DEFAULT 'open',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE (reporter_user_id, target_type, target_id)
    )
    """,
)


SQLITE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_ugc_posts_public ON community_ugc_posts(status, published_at, post_id)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_posts_owner ON community_ugc_posts(owner_user_id, status, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_posts_source ON community_ugc_posts(source_post_id)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_posts_design ON community_ugc_posts(design_id, post_id)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_likes_user ON community_ugc_likes(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_saves_user ON community_ugc_saves(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_comments_post ON community_ugc_comments(post_id, status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_comments_author ON community_ugc_comments(author_user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_follows_followed ON community_ugc_follows(followed_user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_reports_target ON community_ugc_reports(target_type, target_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_ugc_reports_status ON community_ugc_reports(status, created_at)",
)


TABLES = (
    "community_ugc_reports",
    "community_ugc_follows",
    "community_ugc_comments",
    "community_ugc_saves",
    "community_ugc_likes",
    "community_ugc_posts",
)


def upgrade(connection, backend: str, database: str = "") -> None:
    del database
    for statement in MYSQL_TABLES if backend == "mysql" else SQLITE_TABLES:
        connection.execute(statement)
    if backend != "mysql":
        for statement in SQLITE_INDEXES:
            connection.execute(statement)


def downgrade(connection, backend: str, database: str = "") -> None:
    del backend, database
    for table in TABLES:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
