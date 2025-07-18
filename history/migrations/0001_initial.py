# Generated by Django 5.2.3 on 2025-06-13 14:56

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('files', '0001_initial'),
        ('translations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TranslationHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('translated_files', models.JSONField(default=dict)),
                ('target_languages', models.JSONField(default=list)),
                ('strings_translated', models.IntegerField(default=0)),
                ('words_translated', models.IntegerField(default=0)),
                ('success_rate', models.FloatField(default=0.0)),
                ('processing_time', models.DurationField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('service_used', models.CharField(max_length=50)),
                ('original_file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='files.translationfile')),
                ('task', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='translations.translationtask')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='translation_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Translation histories',
                'ordering': ['-created_at'],
            },
        ),
    ]
