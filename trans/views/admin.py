from collections import defaultdict
import logging

from django import forms
from django.http.response import HttpResponseBadRequest, HttpResponseNotFound, Http404

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.files import File
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls.base import reverse
from django.views.generic import View
from django.conf import settings
from django.db import transaction

from trans.forms import UploadFileForm

from trans.models import User, Task, Translation, Contest, Contestant, UserContest, ContestantContest, Country
from trans.utils.pdf import build_final_pdf, merge_final_pdfs
from trans.utils.batch import BatchRecipe, RecipeContestant
from trans.utils.translation import get_trans_by_user_and_task, is_translate_in_editing, unleash_edit_token
import trans.utils.print_job_queue as print_job_queue

logger = logging.getLogger(__name__)


class AdminCheckMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(AdminCheckMixin, self).dispatch(request, *args, **kwargs)


class StaffCheckMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser or user.groups.filter(name="staff").exists()

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(StaffCheckMixin, self).dispatch(request, *args, **kwargs)


class EditorCheckMixin(LoginRequiredMixin, object):
    user_check_failure_path = 'home'  # can be path, url name or reverse_lazy

    def check_user(self, user):
        return user.is_superuser or user.groups.filter(name="editor").exists()

    def user_check_failed(self, request, *args, **kwargs):
        return redirect(self.user_check_failure_path)

    def dispatch(self, request, *args, **kwargs):
        if not self.check_user(request.user):
            return self.user_check_failed(request, *args, **kwargs)
        return super(EditorCheckMixin, self).dispatch(request, *args, **kwargs)


class RightsCheckMixin(object):
    user = None
    contest = None

    def init_user(self, request, username):
        try:
            self.user = User.objects.get(username=username)
        except ObjectDoesNotExist:
            raise Http404('User not found')
        if self.user.id != request.user.id and not request.user.is_superuser and not request.user.is_staff:
            raise PermissionDenied('You cannot edit this user')   # Generates HTTP 403

    def init_contest(self, request, contest_id):
        try:
            self.contest = Contest.objects.get(id=contest_id)
        except ObjectDoesNotExist:
            raise Http404('Contest not found')
        if self.contest.frozen or not self.contest.public:
            raise PermissionDenied('You cannot edit this contest')

        uc = UserContest.objects.filter(user=self.user, contest=self.contest).first()
        if uc and uc.frozen:
            raise PermissionDenied('You cannot edit this contest after you froze it')


class UserTranslations(StaffCheckMixin, View):
    def get(self, request, username):
        user = User.objects.get(username=username)
        # tasks = Task.objects.filter(contest__public=True).values_list('id', 'title')
        translations = []
        for task in Task.objects.filter(contest__public=True):
            translation = Translation.objects.filter(user=user, task=task).first()
            is_editing = translation and is_translate_in_editing(translation)
            if translation:
                translations.append((
                    task.id,
                    task.name,
                    True,
                    translation.id,
                    translation.frozen,
                    is_editing))
            else:
                translations.append((task.id, task.name, False, 'None', False, False))
        tasks_by_contest = {contest: [] for contest in Contest.objects.all()}
        for task in Task.objects.filter(contest__public=True, contest__frozen=False).order_by('order'):
            translation = Translation.objects.filter(user=user, task=task).first()
            is_editing = translation and is_translate_in_editing(translation)
            frozen = translation and translation.frozen
            translation_id = translation.id if translation else None
            final_pdf_url = translation.final_pdf.url if translation and translation.final_pdf else None
            tasks_by_contest[task.contest].append({
                'id': task.id,
                'name': task.name,
                'trans_id': translation_id,
                'is_editing': is_editing,
                'frozen': frozen,
                'final_pdf_url': final_pdf_url
            })
        tasks_lists = [
            {
                'title': c.title,
                'slug': c.slug,
                'id': c.id,
                'user_contest': UserContest.objects.filter(contest=c, user=user).first(),
                'tasks': tasks_by_contest[c]
            }
            for c in Contest.objects.order_by('-order')
            if len(tasks_by_contest[c]) > 0
        ]
        can_upload_final_pdf = request.user.has_perm('trans.change_translation')
        form = UploadFileForm()
        return render(request, 'user.html', context={
            'user_name': username,
            'is_onsite': user.is_onsite,
            'country': user.country.name,
            'is_editor': user.is_editor,
            'tasks_lists': tasks_lists,
            'language': user.credentials(),
            'can_upload_final_pdf': can_upload_final_pdf,
            'form': form
        })


class UsersList(StaffCheckMixin, View):
    def _fetch_users(self):
        users = []
        for user in (User.get_translators() | User.objects.filter(username='ISC')).distinct():
            users.append({
                'username': user.username,
                'country_code': user.country.code,
                'country_name': user.country,
                'language_code': user.language_code,
                'is_onsite': user.is_onsite,
                'is_translating': user.is_translating,
            })
        return users

    def _fetch_translations(self, usernames):
        contests = []
        contest_tasks = defaultdict(list)
        for task in Task.objects.filter(contest__public=True, contest__frozen=False).order_by('-contest__order', 'order'):
            contest = task.contest
            contest_tasks[contest.id].append(task)

            if not contests or contests[-1]['id'] != contest.id:
                contests.append({
                    'title': contest.title,
                    'slug': contest.slug,
                    'id': contest.id,
                })
        # Django template doesn't play well with defaultdicts.
        contest_tasks = dict(contest_tasks)

        user_translations = {username: {} for username in usernames}
        for translation in Translation.objects.filter(task__contest__public=True, task__contest__frozen=False):
            user = translation.user
            task = translation.task
            # Task.name is unique, so translation does not need to be keyed by contest.
            if user.username not in user_translations:
                continue
            user_translations[user.username][task.name] = {
                'id': translation.id,
                'is_editing': is_translate_in_editing(translation),
                'frozen': translation.frozen,
                'final_pdf_url': translation.final_pdf.url if translation.final_pdf else None,
                'translating': translation.translating
            }

        user_contests = {username: {} for username in usernames}
        for user_contest in UserContest.objects.filter(contest__public=True, contest__frozen=False):
            user = user_contest.user
            contest = user_contest.contest
            if user.username not in user_contests or not contest:
                continue
            user_contests[user.username][contest.id] = {
                'frozen': user_contest.frozen,
                'note': user_contest.note,
                'sealed': user_contest.sealed,
                'extra_country_1_code': user_contest.extra_country_1_code,
                'extra_country_1_count': user_contest.extra_country_1_count,
                'extra_country_2_code': user_contest.extra_country_2_code,
                'extra_country_2_count': user_contest.extra_country_2_count
            }

        return (contests, contest_tasks, user_translations, user_contests)

    def _chunks(self, xs, n):
        return (xs[i:len(xs):n] for i in range(n))

    def get(self, request, public=False):
        users = self._fetch_users()
        (contests, contest_tasks, user_translations, user_contests) = \
            self._fetch_translations([user['username'] for user in users])

        render_page = 'users_public.html' if public else 'users.html'
        users_public = self._chunks(sorted(users, key=lambda u: u['username']), 4)
        return render(request, render_page, context={
            'users': users,
            'users_public': users_public,
            'contests': contests,
            'contest_tasks': contest_tasks,
            'user_translations': user_translations,
            'user_contests': user_contests,
        })


class AddFinalPDF(StaffCheckMixin, View):
    def post(self, request):
        id = request.POST['trans_id']
        trans = Translation.objects.filter(id=id).first()
        form = UploadFileForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponseBadRequest("You should attach a file")

        pdf_file = request.FILES.get('uploaded_file', None)
        if not pdf_file or pdf_file.name.split('.')[-1] != 'pdf':
            return HttpResponseBadRequest("You should attach a pdf file")

        trans.frozen = True
        trans.final_pdf = pdf_file
        trans.save()
#        trans.notify_final_pdf_change()
        return redirect(request.META.get('HTTP_REFERER'))


class FreezeTranslationView(View):
    def _freeze_translation(self, username, task_name, frozen, translating):
        user = User.objects.filter(username=username).first()
        if user is None:
            return HttpResponseNotFound('No such user')

        task = Task.objects.filter(name=task_name).first()
        if task is None:
            return HttpResponseNotFound('No such task')

        trans = get_trans_by_user_and_task(user, task)

        trans.frozen = frozen
        if frozen:
            if translating:
                trans.translating = True
                pdf_path = build_final_pdf(trans)
                with open(pdf_path, 'rb') as f:
                    trans.final_pdf = File(f)
                    # Needs to be called while the file is open.
                    trans.save()
            else:
                trans.translating = False
                trans.save()
        else:
            trans.final_pdf.delete()
            trans.translating = None
            trans.save()

        # No one should be editing anyway once the translation is frozen. This
        # helps make the translation immediately editable if it gets thawed
        # before the last edit timeout.
        unleash_edit_token(trans)


class UserFreezeTranslation(LoginRequiredMixin, FreezeTranslationView):
    def post(self, request, task_name):
        frozen = request.POST['freeze'] == 'True'
        translating = request.POST.get('translating') != 'False'
        self._freeze_translation(request.user.username, task_name, frozen, translating)

        # trans.notify_final_pdf_change()
        # return redirect(to=reverse('user_trans', kwargs={'username' : trans.user.username}))
        return redirect(request.META.get('HTTP_REFERER'))


class StaffFreezeTranslation(StaffCheckMixin, FreezeTranslationView):
    def post(self, request, username, task_name):
        frozen = request.POST['freeze'] == 'True'
        translating = request.POST.get('translating') != 'False'
        self._freeze_translation(username, task_name, frozen, translating)

        # trans.notify_final_pdf_change()
        # return redirect(to=reverse('user_trans', kwargs={'username' : trans.user.username}))
        return redirect(request.META.get('HTTP_REFERER'))


class FreezeForm(forms.ModelForm):
    class Meta:
        model = UserContest
        fields = ['skip_verification', 'note']
        widgets = {
            'note': forms.Textarea(attrs={'cols': 80, 'rows': 3}),
        }


class FreezeUserContest(LoginRequiredMixin, RightsCheckMixin, View):
    @transaction.atomic
    def _handle(self, request, username, contest_id, is_post):
        self.init_user(request, username)
        self.init_contest(request, contest_id)

        self.tasks = self.contest.task_set.order_by('order')
        self.errors = []
        user_contest, _ = UserContest.objects.get_or_create(contest=self.contest, user=self.user)
        self.batch_recipe = BatchRecipe(contest=self.contest, for_user=self.user, user_contest=user_contest)

        if self.user.is_staff:
            self.errors.append('Staff does not have translations')
        elif self.user.is_onsite or self.user.is_translating:
            if self.user.is_translating:
                self.check_own_translations()
            if self.user.is_onsite:
                self.make_recipe()
        else:
            self.errors.append('You neither have on-site contestants nor you are translating')

        if self.errors:
            form = None
        else:
            if is_post:
                form = FreezeForm(request.POST, instance=user_contest)
                if form.is_valid() and not self.errors:
                    pdf = self.batch_recipe.build_pdf()
                    user_contest.frozen = True
                    user_contest.sealed = False
                    user_contest.save()
                    print_job_queue.handle_user_contest_frozen(user_contest, pdf)
                    return redirect('home')
            else:
                form = FreezeForm(instance=user_contest)

        return render(request, 'freeze_user_contest.html', context={
            'form': form,
            'contest': self.contest,
            'for_user': self.user,
            'user': request.user,
            'errors': self.errors,
        })

    def check_own_translations(self):
        for task in self.tasks:
            trans = Translation.objects.filter(user=self.user, task=task).first()
            if not trans:
                self.errors.append(f'Task {task.name} has no translation')
            elif not trans.frozen:
                self.errors.append(f'Task {task.name} translation is not frozen')

    def make_recipe(self):
        for ctant in Contestant.objects.filter(user=self.user).order_by('code'):
            if not ctant.on_site:
                continue

            ct_recipe = self.batch_recipe.add_contestant(ctant)
            cc = ContestantContest.obtain(ctant, self.contest, self.user)
            by_user = cc.translation_by_user
            if by_user is not None:
                for task in self.tasks:
                    trans = Translation.objects.filter(user=cc.translation_by_user, task=task).first()
                    err = None
                    if not trans:
                        err = 'which does not exist'
                    elif not trans.frozen:
                        err = 'which is not frozen'
                    elif trans.translating:
                        ct_recipe.translations.append(trans)
                    if err is not None and by_user != self.user:
                        self.errors.append(f'Contestant {ctant.code} requests translation of {task.name} to {by_user.language.name} ({by_user.country.name}) {err}')

    def get(self, request, username, contest_id):
        return self._handle(request, username, contest_id, False)

    def post(self, request, username, contest_id):
        return self._handle(request, username, contest_id, True)


class UnfreezeUserContest(LoginRequiredMixin, View):
    def post(self, request, username, contest_id):
        user = User.objects.get(username=username)
        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return HttpResponseNotFound("There is no contest")
        user_contest = UserContest.objects.filter(contest=contest, user=user).first()
        if user_contest is not None:
            user_contest.frozen = False
            print_job_queue.handle_user_contest_unfrozen(user_contest)
            user_contest.delete()
#        return redirect(to=reverse('user_trans', kwargs={'username': username}))
        return redirect(request.META.get('HTTP_REFERER'))

class SealUserContest(LoginRequiredMixin, View):
    def post(self, request, username, contest_id):
        user = User.objects.get(username=username)
        contest = Contest.objects.filter(id=contest_id).first()
        if contest is None:
            return HttpResponseNotFound("There is no contest")
        user_contest = UserContest.objects.filter(contest=contest, user=user).first()
        if user_contest is not None:
            user_contest.sealed = True
            user_contest.save()
        return redirect(request.META.get('HTTP_REFERER'))

class UnleashEditTranslationToken(LoginRequiredMixin, View):
    def post(self, request, id):
        trans = Translation.objects.get(id=id)
        if trans is None:
            return HttpResponseNotFound("There is no task")
        unleash_edit_token(trans)
        return redirect(to=reverse('user_trans', kwargs={'username': trans.user.username}))


class EditUserContest(LoginRequiredMixin, RightsCheckMixin, View):
    @transaction.atomic
    def _handle(self, request, username, contest_id, is_post):
        self.init_user(request, username)
        self.init_contest(request, contest_id)

        contestants = Contestant.objects.filter(user=self.user).order_by('code')

        translating_users = User.objects.filter(is_translating=True).select_related('language', 'country').order_by('language__name', 'country__name')
        trans_choices = [
            (u.id, f'{u.language.name} ({u.country.name})')
            for u in translating_users
        ]
        trans_choices.insert(0, ("-", "No translation"))

        class TransSettingsForm(forms.BaseForm):
            base_fields = {}

        for c in contestants:
            if c.on_site:
                TransSettingsForm.base_fields[f'trans_{c.id}'] = forms.ChoiceField(choices=trans_choices)

        if is_post:
            form = TransSettingsForm(request.POST)
            if form.is_valid():
                for c in contestants:
                    if c.on_site:
                        cc, _ = ContestantContest.objects.get_or_create(contest=self.contest, contestant=c)
                        trans_by = form.cleaned_data[f'trans_{c.id}']
                        if trans_by == "-":
                            cc.translation_by_user_id = None
                        else:
                            cc.translation_by_user_id = trans_by
                        cc.save()
                return redirect('home')
        else:
            form_init = {}
            for c in contestants:
                if c.on_site:
                    cc = ContestantContest.obtain(c, self.contest, self.user)
                    form_init[f'trans_{c.id}'] = cc.translation_by_user_id or "-"
            form = TransSettingsForm(initial=form_init)

        return render(request, 'edit_user_contest.html', context={
            'form': form,
            'contest': self.contest,
            'for_user': self.user,
            'user': request.user,
            'contestant_table': [(c, form[f'trans_{c.id}'] if c.on_site else None) for c in contestants],
        })

    def get(self, request, username, contest_id):
        return self._handle(request, username, contest_id, False)

    def post(self, request, username, contest_id):
        return self._handle(request, username, contest_id, True)
