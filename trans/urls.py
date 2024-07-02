from django.conf import settings

from django.urls import path
from .views import *
from django.conf.urls.static import static

urlpatterns = [
          path('', FirstPage.as_view(), name='firstpage'),
          path('healthcheck', Healthcheck.as_view(), name='healthcheck'),
          path('settings/', Settings.as_view(), name='settings'),
          path('login/', Login.as_view(), name='login'),
          path('logout/', Logout.as_view(), name='logout'),

          path('home/', Home.as_view(), name='home'),
          path('task/<str:contest_slug>/<str:task_name>/', Translations.as_view(), name='edit'),
          path('<str:task_type>/<str:contest_slug>/<str:task_name>/markdown', TranslationMarkdown.as_view(), name='task_md'),
          path('<str:task_type>/<str:contest_slug>/<str:task_name>/pdf', TranslationPDF.as_view(), name='task_pdf'),
          path('<str:task_type>/<str:contest_slug>/<str:task_name>/print', TranslationPrint.as_view(), name='task_print'),
          path('<str:task_type>/<str:contest_slug>/<str:task_name>/revisions', Versions.as_view(), name='revisions'),

          path('getvers/', GetVersion.as_view(), name='getVersion'),
          path('task/<str:contest_slug>/<str:task_name>/save/', SaveTranslation.as_view(), name='save_translation'),

          path('access_edit_translate/<str:id>/', AccessTranslationEdit.as_view(), name='access_edit_translate'),
          path('finish_edit_translate/<str:id>/', FinishTranslate.as_view(), name='finish_trans'),
          path('get_latest_translation/<str:id>/', GetLatestTranslation.as_view(), name='get_latest_translation'),

          path('task/<str:contest_slug>/<str:task_name>/release', ReleaseTask.as_view(), name='release_task'),
          path('add_task/', AddTask.as_view(), name='add_task'),
          path('revert/', Revert.as_view(), name='revert'),

          path('users/', UsersList.as_view(), name='users_list'),
          path('users/<str:public>/', UsersList.as_view(), name='public_users_list'),
          path('user/<str:username>/', UserTranslations.as_view(), name='user_trans'),
          path('upload_final_pdf/', AddFinalPDF.as_view(), name='upload_final_pdf'),
          path('user_freeze_trans/<str:task_name>/', UserFreezeTranslation.as_view(), name='user_freeze_trans'),
          path('staff_freeze_trans/<str:task_name>/<str:username>/', StaffFreezeTranslation.as_view(), name='staff_freeze_trans'),
          path('freeze_user_contest/<str:username>/<str:contest_id>/', FreezeUserContest.as_view(), name='freeze_user_contest'),
          path('unfreeze_user_contest/<str:username>/<str:contest_id>/', UnfreezeUserContest.as_view(), name='unfreeze_user_contest'),
          path('seal_user_contest/<str:username>/<str:contest_id>/', SealUserContest.as_view(), name='seal_user_contest'),
          path('unleash_edit_token/<str:id>/', UnleashEditTranslationToken.as_view(), name='unleash_edit_token'),

          path('notifications/', ReadNotifications.as_view(), name='notifications'),
          path('reset_notifications/', reset_notifications, name='reset_notifications'),
          path('send_notification/', SendNotification.as_view(), name='send_notif'),
          path('user/<str:username>/font.css', UserFont.as_view(), name='userfontcss'),
      ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
