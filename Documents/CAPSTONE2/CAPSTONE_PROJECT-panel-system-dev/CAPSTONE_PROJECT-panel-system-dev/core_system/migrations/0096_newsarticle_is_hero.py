from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0095_backfill_news_article_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsarticle",
            name="is_hero",
            field=models.BooleanField(default=False, help_text="Show in homepage hero carousel"),
        ),
    ]
