from django.utils.text import slugify
from django.db import migrations


def backfill_slugs(apps, schema_editor):
    NewsArticle = apps.get_model("core_system", "NewsArticle")
    used = set(
        NewsArticle.objects.exclude(slug="").values_list("slug", flat=True)
    )
    for article in NewsArticle.objects.filter(slug="").order_by("news_id"):
        base = slugify(article.title) or f"news-{article.news_id}"
        slug = base
        suffix = 2
        while slug in used:
            slug = f"{base}-{suffix}"
            suffix += 1
        article.slug = slug
        used.add(slug)
        article.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0094_add_news_foreign_keys"),
    ]

    operations = [
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
