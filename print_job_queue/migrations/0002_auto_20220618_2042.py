# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-06-18 16:42
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('print_job_queue', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='draftprintjob',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='finalprintjob',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='printeddraftdocument',
            name='job',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_set', to='print_job_queue.DraftPrintJob'),
        ),
        migrations.AlterField(
            model_name='printedfinaldocument',
            name='job',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_set', to='print_job_queue.FinalPrintJob'),
        ),
    ]
