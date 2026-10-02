"""Export helpers; database initialization is deferred until database helpers are used."""
from importlib import import_module

__all__ = ["get_connection", "init_database", "save_post", "save_posts_batch", "save_comments_batch",
           "search_posts", "search_comments", "get_subreddit_stats", "get_all_subreddits",
           "start_job_record", "complete_job_record", "get_job_history", "get_job_stats",
           "print_job_history", "enable_auto_vacuum", "backup_database", "vacuum_database", "get_database_info"]


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".database", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
