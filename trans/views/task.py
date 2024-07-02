from django.http.response import HttpResponseForbidden

from django.shortcuts import render, redirect
from django.views.generic import View
from django.urls import reverse
from django.http import HttpResponse, HttpResponseBadRequest

from trans.utils import get_trans_by_user_and_task
from trans.models import Task, User, Contest
from trans.views.admin import ISCEditorCheckMixin


class AddTask(ISCEditorCheckMixin, View):
    def post(self, request):
        if request.user.username != "ISC":
            return HttpResponseForbidden("You don't have access to this page")
        name = request.POST['name']
        contest_id = request.POST['contest']
        contest = Contest.objects.filter(id=contest_id).first()
        contest_tasks = Task.objects.filter(contest=contest)
        order = contest_tasks.latest('order').order + 1 if contest_tasks else 1
        new_task, created = Task.objects.get_or_create(name=name, contest=contest, order=order)
        user = User.objects.get(username=request.user.username)
        trans = get_trans_by_user_and_task(user, new_task) # to initiate translation
        trans.add_version('# ' + name.capitalize(), saved=False)
        return redirect(to=reverse('edit', kwargs={'contest_slug': contest.slug, 'task_name': name}))


class ReleaseTask(ISCEditorCheckMixin, View):
    def post(self, request, contest_slug, task_name):
        release_note = request.POST.get('release_note', '')
        task = Task.objects.get(name=task_name, contest__slug=contest_slug)
        if task.contest.frozen:
            return HttpResponseBadRequest("The task is frozen")
        task.publish_latest(release_note)
        return HttpResponse("done")
