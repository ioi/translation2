from django.conf import settings

from django.conf.urls import url
from .views import *
from django.conf.urls.static import static

urlpatterns = [
    # Draft job routes.
    url(r'^draft/$', draft_queue, name='draft_queue'),
    url(r'^draft_job_pick_up/(?P<job_id>[\w]*)/$',
        DraftJobPickUp.as_view(),
        name='draft_job_pick_up'),
    url(r'^draft_job_mark_completion/(?P<job_id>[\w]*)/$',
        DraftJobMarkCompletion.as_view(),
        name='draft_job_mark_completion'),

    # Final job routes.
    url(r'^final/$', final_queue, name='final_queue'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
