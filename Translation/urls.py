from django.urls import include, path, re_path
from django.contrib import admin

from trans.views.user import FirstPage

urlpatterns = [
    path('admin/login/', FirstPage.as_view()),
    path('admin/', admin.site.urls),
    path('queue/', include('print_job_queue.urls')),
    path('' , include('trans.urls')),
]
