# Generated by Django 5.0.6 on 2024-07-22 14:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('print_job_queue', '0005_worker_remove_printeddraftdocument_job_and_more'),
        ('trans', '0029_remove_usercontest_extra_country_1_code_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usercontest',
            name='final_print_job',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='print_job_queue.printjob'),
        ),
    ]
