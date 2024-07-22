# Generated by Django 5.0.6 on 2024-07-22 14:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('print_job_queue', '0004_auto_20220626_0413'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Worker',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('job_type', models.IntegerField(choices=[(0, 'DRAFT'), (1, 'FINAL')], null=True)),
                ('modulo', models.PositiveIntegerField()),
                ('index', models.PositiveIntegerField()),
                ('server_print', models.BooleanField()),
            ],
        ),
        migrations.RemoveField(
            model_name='printeddraftdocument',
            name='job',
        ),
        migrations.RemoveField(
            model_name='finalprintjob',
            name='owner',
        ),
        migrations.RemoveField(
            model_name='printedfinaldocument',
            name='job',
        ),
        migrations.CreateModel(
            name='PrintJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(0, 'PENDING'), (1, 'IN_PROGRESS'), (2, 'DONE'), (3, 'INVALID'), (4, 'PRINTING')])),
                ('group', models.CharField(max_length=25)),
                ('job_type', models.IntegerField(choices=[])),
                ('owner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('worker', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='print_job_queue.worker')),
            ],
        ),
        migrations.CreateModel(
            name='PrintedDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_path', models.FilePathField(match='*.pdf', recursive=True)),
                ('print_count', models.PositiveIntegerField()),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_set', to='print_job_queue.printjob')),
            ],
        ),
        migrations.DeleteModel(
            name='DraftPrintJob',
        ),
        migrations.DeleteModel(
            name='PrintedDraftDocument',
        ),
    ]
