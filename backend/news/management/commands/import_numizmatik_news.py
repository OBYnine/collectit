from django.core.management.base import BaseCommand, CommandError

from news.importers import NewsImportError, import_numizmatik_news


class Command(BaseCommand):
    help = "Import latest numismatic news from numizmatik.ru and publish one AI-generated digest."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Number of source articles to combine.")
        parser.add_argument("--dry-run", action="store_true", help="Parse sources but do not call Gemini or save.")
        parser.add_argument("--update-existing", action="store_true", help="Regenerate already imported articles.")
        parser.add_argument(
            "--skip-ai",
            action="store_true",
            help="Save parsed source text without Gemini rewriting. Use only for emergency/debug.",
        )

    def handle(self, *args, **options):
        try:
            result = import_numizmatik_news(
                limit=options["limit"],
                dry_run=options["dry_run"],
                update_existing=options["update_existing"],
                use_ai=not options["skip_ai"] and not options["dry_run"],
            )
        except NewsImportError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Sources: {candidates}; imported digests: {imported}; updated digests: {updated}; "
                "skipped digests: {skipped}; article_id: {article_id}; errors: {errors}".format(
                    candidates=result.candidates,
                    imported=result.imported,
                    updated=result.updated,
                    skipped=result.skipped,
                    article_id=result.article_id or "-",
                    errors=len(result.errors),
                )
            )
        )
        for item in result.dry_run_items:
            self.stdout.write(
                "- {external_id}: {title} ({images} images) {url}".format(**item)
            )
        for error in result.errors:
            self.stderr.write(self.style.ERROR(error))
        if result.errors and not options["dry_run"]:
            raise CommandError("Import finished with errors; no digest was published.")
