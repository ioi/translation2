from django.conf import settings

from django.urls import path
from .views import *
from django.conf.urls.static import static

urlpatterns = [
    # Draft job routes.
    path('draft/<str:group>/', DraftJobQueue.as_view(), name='draft_queue'),
    path('draft_job_pick_up/<str:job_id>/', DraftJobPickUp.as_view(), name='draft_job_pick_up'),
    path('draft_job_mark_completion/<str:job_id>/', DraftJobMarkCompletion.as_view(), name='draft_job_mark_completion'),

    # Final job routes.
    path('final/<str:group>/', FinalJobQueue.as_view(), name='final_queue'),
    path('final_job_pick_up/<str:job_id>/', FinalJobPickUp.as_view(), name='final_job_pick_up'),
    path('final_job_mark_completion/<str:job_id>/', FinalJobMarkCompletion.as_view(), name='final_job_mark_completion'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
