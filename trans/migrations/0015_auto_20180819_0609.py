# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-08-19 06:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('trans', '0014_country_code2'),
    ]

    operations = [
        migrations.AddField(
            model_name='translation',
            name='final_pdf',
            field=models.FileField(null=True, upload_to='final_pdf/'),
        ),
    ]
