# Generated by Django 4.1.3 on 2022-11-24 21:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0005_migration_flattened_google_files_list_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='migration',
            name='flattened_google_files_list',
        ),
    ]
