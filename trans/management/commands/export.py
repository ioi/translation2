from django.conf import settings
from django.core.management.base import BaseCommand
from pathlib import Path
import shutil
from trans.models import Contest, Task, Translation, Attachment
from trans.utils.pdf import build_final_pdf


class Command(BaseCommand):
    help = "Exports final versions of all translations"

    def add_arguments(self, parser):
        parser.add_argument("destdir", help="Directory to export the translations to")

    def handle(self, *args, **options):
        export_path = Path(options['destdir'])
        export_path.mkdir(parents=True, exist_ok=True)

        for contest in Contest.objects.all():
            self.export_contest(contest, export_path)

        self.export_attachments(export_path)

    def export_contest(self, contest, export_path):
        print(f'Exporting contest {contest.slug}')
        contest_path = export_path / contest.slug
        contest_path.mkdir(exist_ok=True)

        for task in Task.objects.filter(contest=contest):
            self.export_task(task, contest_path)

    def export_task(self, task, contest_path):
        print(f'\tTask {task.name}')
        task_path = contest_path / task.name
        task_path.mkdir(exist_ok=True)

        for trans in Translation.objects.filter(task=task):
            is_editor = trans.user.is_editor()
            if is_editor or (trans.translating and trans.frozen):
                if is_editor:
                    lang = trans.user.language_code
                else:
                    lang =  f'{trans.user.language.code}_{trans.user.country.code2}'
                ver = trans.get_latest_version()
                self.export_version(trans, ver, lang, task_path)

    def export_version(self, trans, ver, lang, task_path):
        print(f'\t\tTranslation {lang} ({ver.create_time.isoformat()})')
        ver_path = task_path / lang

        with open(ver_path.with_suffix('.md'), 'w') as f:
            f.write(ver.text)

        if trans.final_pdf:
            pdf = settings.MEDIA_ROOT + trans.final_pdf.name
        else:
            pdf = build_final_pdf(trans)
        shutil.copyfile(pdf, ver_path.with_suffix('.pdf'))

    def export_attachments(self, export_path):
        print('Exporting attachments')
        att_path = export_path / 'images'
        att_path.mkdir(exist_ok=True)

        for att in Attachment.objects.all():
            print(f'\t{att.uploaded_file.name}')
            assert att.uploaded_file.name.startswith('images/')
            shutil.copyfile(settings.MEDIA_ROOT + att.uploaded_file.name, export_path / att.uploaded_file.name)
