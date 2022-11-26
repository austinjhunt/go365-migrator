# Generated by Django 4.1.3 on 2022-11-26 16:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0007_administrationsettings_require_idp_login'),
    ]

    operations = [
        migrations.AlterField(
            model_name='administrationsettings',
            name='require_idp_login',
            field=models.BooleanField(default=False, verbose_name='Require Single Sign On (login via the IdP). If true, local login form (username, password) will be disabled.'),
        ),
        migrations.AlterField(
            model_name='administrationsettings',
            name='smtp_enable_email_notifications',
            field=models.BooleanField(default=False, verbose_name='Enable email notifications (on migration completion)? If enabled, SMTP fields will be required.'),
        ),
        migrations.AlterField(
            model_name='administrationsettings',
            name='twilio_account_auth_token',
            field=models.CharField(blank=True, max_length=32, null=True, verbose_name='Twilio Account Auth Token (from your Twilio account dashboard)'),
        ),
        migrations.AlterField(
            model_name='administrationsettings',
            name='twilio_account_sid',
            field=models.CharField(blank=True, max_length=32, null=True, verbose_name='Twilio Account SID (from your Twilio account dashboard)'),
        ),
        migrations.AlterField(
            model_name='administrationsettings',
            name='twilio_enable_sms_notifications',
            field=models.BooleanField(default=False, verbose_name='Enable SMS notifications for users. If enabled, Twilio settings will be required.'),
        ),
        migrations.AlterField(
            model_name='administrationsettings',
            name='twilio_messaging_service_sid',
            field=models.CharField(blank=True, max_length=32, null=True, verbose_name='Twilio Messaging Service SID'),
        ),
        migrations.AlterField(
            model_name='migration',
            name='state',
            field=models.CharField(choices=[('Waiting to scan source data', 'Waiting To Scan'), ('Scanning source data', 'Scanning'), ('Source data scan is complete', 'Scan Complete'), ('Waiting to migrate source data to target', 'Waiting To Migrate'), ('Migrating source data to target', 'Migrating'), ('Migration to target failed', 'Migration Failed'), ('Migration is complete', 'Migration Complete')], db_index=True, default='Waiting to scan source data', max_length=56),
        ),
    ]