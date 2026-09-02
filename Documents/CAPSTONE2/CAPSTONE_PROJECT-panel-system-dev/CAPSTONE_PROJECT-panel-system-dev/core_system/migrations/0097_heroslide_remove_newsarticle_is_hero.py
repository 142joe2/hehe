from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0096_newsarticle_is_hero"),
    ]

    operations = [
        migrations.CreateModel(
            name="HeroSlide",
            fields=[
                ("hero_id", models.AutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("subtitle", models.TextField(blank=True, help_text="Short text shown on the slide", max_length=500)),
                ("image", models.ImageField(blank=True, null=True, upload_to="hero/%Y/%m/")),
                ("button_text", models.CharField(default="Read More", max_length=50)),
                ("button_url", models.CharField(blank=True, help_text="Internal or external link for the slide button", max_length=500)),
                ("sort_order", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True, help_text="Show on the homepage hero carousel")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Hero Slide",
                "verbose_name_plural": "Hero Slides",
                "db_table": "HERO_SLIDE",
                "ordering": ["sort_order", "-created_at"],
            },
        ),
        migrations.RemoveField(
            model_name="newsarticle",
            name="is_hero",
        ),
    ]
