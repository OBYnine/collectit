from celery import shared_task

from .importers import import_numizmatik_news


@shared_task(name="news.tasks.import_numizmatik_news_task")
def import_numizmatik_news_task(limit=None, update_existing=False):
    result = import_numizmatik_news(
        limit=limit,
        update_existing=update_existing,
        dry_run=False,
        use_ai=True,
    )
    return {
        "candidates": result.candidates,
        "imported": result.imported,
        "updated": result.updated,
        "skipped": result.skipped,
        "article_id": result.article_id,
        "errors": result.errors,
    }
