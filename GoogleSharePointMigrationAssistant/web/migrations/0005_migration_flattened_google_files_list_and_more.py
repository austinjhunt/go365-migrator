# Generated by Django 4.1.3 on 2022-11-24 16:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0004_migration_complete_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='migration',
            name='flattened_google_files_list',
            field=models.JSONField(blank=True, null=True, verbose_name='Flattened list of all Google files included in the migration'),
        ),
        migrations.AddField(
            model_name='migration',
            name='source_data_scan_result',
            field=models.JSONField(blank=True, null=True, verbose_name='High-level stats about the migration to be run based on scanning the source data to be migrated'),
        ),
    ]
