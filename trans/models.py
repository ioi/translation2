import json

from django.db.models.signals import post_save, post_delete
from django.contrib.auth.models import User as DjangoUser
from django.db import models
from django.utils import timezone
from django.conf import settings

from trans.utils.notification import add_notification_to_users_cache, remove_notification

from print_job_queue import models as print_job_queue_models


class User(DjangoUser):
    language = models.ForeignKey('Language', on_delete=models.deletion.CASCADE)
    country = models.ForeignKey('Country', on_delete=models.deletion.CASCADE)
    text_font_base64 = models.TextField(default='', blank=True)
    text_font_name = models.CharField(max_length=255, default='', blank=True)
    num_of_contestants = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.username

    def credentials(self):
        return self.country.name + '_' + self.language.name

    def has_contestants(self):
        return self.num_of_contestants > 0

    def is_translating(self):
        return self.language.code != 'en'

    @property
    def raw_password(self):
        return '****'

    @raw_password.setter
    def raw_password(self, raw_password):
        self.set_password(raw_password)

    @property
    def language_code(self):
        language_code = self.language.code
        country_code2 = self.country.code2
        if country_code2 is None:
            return language_code
        else:
            return '{}_{}'.format(language_code, country_code2)

    @staticmethod
    def get_translators():
        return User.objects.filter(is_staff=False)

    def is_editor(self):
        return self.groups.filter(name='editor').exists() or self.is_superuser


class Contest(models.Model):
    title = models.CharField(max_length=100, blank=False)
    order = models.IntegerField(default=1)
    slug = models.CharField(db_index=True, max_length=10, blank=False, unique=True)
    public = models.BooleanField(default=False)
    frozen = models.BooleanField(default=False)

    def __str__(self):
        return "{} (order: {})".format(self.title, self.order)


class Task(models.Model):
    name = models.CharField(db_index=True, max_length=255, blank=False)
    contest = models.ForeignKey('Contest', on_delete=models.CASCADE, default=None)
    order = models.IntegerField(default=1)

    def get_base_translation(self):
        return Translation.objects.filter(user__username='ISC', task=self).first()

    def publish_latest(self, release_note):
        base_trans = self.get_base_translation()
        if not base_trans:
            return None
        latest_version = base_trans.get_latest_version()
        if not latest_version:
            return None
        query = Version.objects.filter(id=latest_version.id)
        return query.update(release_note=release_note, released=True, saved=True, create_time=timezone.now())

    def get_latest_text(self):
        base_trans = self.get_base_translation()
        return base_trans.get_latest_text() if base_trans else ''

    def get_published_text(self):
        base_trans = self.get_base_translation()
        return base_trans.get_published_text() if base_trans else ''

    def is_published(self):
        base_trans = self.get_base_translation()
        if base_trans:
            return base_trans.version_set.filter(released=True).exists()
        return False

    def get_latest_change_time(self):
        base_trans = self.get_base_translation()
        latest_published_version = base_trans.version_set.filter(released=True).order_by('-create_time').first()
        if latest_published_version:
            return latest_published_version.create_time
        return None

    def __str__(self):
        return '{} ({}: {})'.format(self.name, self.contest.title, self.order)


def final_pdf_path(instance, _):
    return 'final_pdf/{}/{}.pdf'.format(
        instance.task.name,
        instance.user.language_code,
    )


class Translation(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    task = models.ForeignKey('Task', on_delete=models.CASCADE, default=0)
    frozen = models.BooleanField(default=False)
    translating = models.BooleanField(null=True)
    final_pdf = models.FileField(upload_to=final_pdf_path, null=True)

    class Meta:
        unique_together = (
            ('user', 'task',),
        )

    def add_version(self, text, release_note='', saved=True):
        if text.strip() == '':
            return None
        latest_version = self.version_set.order_by('-create_time').first()
        if latest_version and latest_version.text.strip() == text.strip():
            query = Version.objects.filter(id=latest_version.id)
            return query.update(create_time=timezone.now(), saved=(saved or latest_version.saved))
        return Version.objects.create(translation=self, text=text, release_note=release_note, saved=saved)

    def save_last_version(self, release_note='', saved=True):
        latest_version = self.get_latest_version()
        latest_version.create_time = timezone.now()
        latest_version.release_note = release_note
        latest_version.saved = saved
        latest_version.save()

    def get_latest_version(self):
        return self.version_set.order_by('-create_time').first()

    def get_published_versions_count(self):
        return self.version_set.filter(released=True).count()

    def get_latest_text(self):
        latest_version = self.get_latest_version()
        return latest_version.text if latest_version else ''

    def get_published_text(self):
        latest_published_version = self.version_set.filter(released=True).order_by('-create_time').first()
        return latest_published_version.text if latest_published_version else None

    def get_latest_change_time(self):
        latest_version = self.get_latest_version()
        return latest_version.create_time.timestamp() if latest_version else None

    def is_editable_by(self, user):
        contest = self.task.contest
        user_contest = UserContest.objects.filter(user=user, contest=contest).first()
        frozen_by_user_contest = user_contest and user_contest.frozen
        return self.frozen or contest.frozen or frozen_by_user_contest

    def __str__(self):
        return "{} ({})".format(self.task.name, self.user.username)


class UserContest(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    contest = models.ForeignKey('Contest', on_delete=models.CASCADE, default=None)
    frozen = models.BooleanField(default=False)
    sealed = models.BooleanField(default=False)
    note = models.TextField(default='')
    extra_country_1_code = models.CharField(max_length=6, blank=True)
    extra_country_2_code = models.CharField(max_length=6, blank=True)
    extra_country_1_count = models.PositiveIntegerField(default=0)
    extra_country_2_count = models.PositiveIntegerField(default=0)

    # The print job that corresponds to the latest state, if it is frozen.
    # If the UserContest is not frozen, this is null.
    final_print_job = models.ForeignKey(print_job_queue_models.FinalPrintJob,
                                        null=True,
                                        on_delete=models.PROTECT)


class Version(models.Model):
    translation = models.ForeignKey('Translation', on_delete=models.CASCADE)
    text = models.TextField(default=None)
    saved = models.BooleanField(default=False)
    released = models.BooleanField(default=False)
    release_note = models.CharField(max_length=255, blank=True)
    create_time = models.DateTimeField(default=timezone.now)

    def can_view_by(self, user):
        if self.translation.user != user and self.translation.user.username != 'ISC':
            return False
        return True

    def __str__(self):
        return "{}: {} ({})".format(self.id, self.translation.task.name, self.translation.user.username)


class Language(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(primary_key=True, max_length=255)
    rtl = models.BooleanField(default=False)

    def direction(self):
        return 'rtl' if self.rtl else 'ltr'

    def __str__(self):
        return self.name


class Country(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(primary_key=True, max_length=255)
    code2 = models.CharField(max_length=255, null=True, default=None)

    def __str__(self):
        return self.name


class Notification(models.Model):
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=300)
    create_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return "%s-%s" % (self.title, self.description)


def send_notif(sender, instance, created, *args, **kwargs):
    if created:
        add_notification_to_users_cache(User.objects.all(), instance)
        # Redis Messages
        # message = RedisMessage("%s^%s"%(instance.title, instance.description))
        # RedisPublisher(facility='notifications', broadcast=True).publish_message(message)


def remove_notif(sender, instance, *args, **kwargs):
    remove_notification(User.objects.all(), instance)


post_save.connect(send_notif, sender=Notification)
post_delete.connect(remove_notif, sender=Notification)


class Attachment(models.Model):
    uploaded_file = models.FileField(upload_to='images/')
    title = models.CharField(max_length=100)
    create_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class FlatPage(models.Model):
    slug = models.CharField(max_length=100, primary_key=True)
    content = models.TextField(default=None, blank=True)

    def __str__(self):
        return self.slug
