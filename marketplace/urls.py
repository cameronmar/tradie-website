from django.urls import path
from . import views

urlpatterns = [
    # Static
    path('',                       views.home,          name='home'),
    path('how-it-works/',          views.how_it_works,  name='how_it_works'),
    path('privacy/',               views.privacy,       name='privacy'),
    path('terms/',                 views.terms,         name='terms'),
    path('support/',               views.contact_support, name='contact_support'),
    # Auth
    path('register/',              views.register_client,  name='register_client'),
    path('register/tradie/',       views.register_tradie,  name='register_tradie'),
    path('login/',                 views.login_view,    name='login'),
    path('logout/',                views.logout_view,   name='logout'),
    path('dashboard/',             views.dashboard,     name='dashboard'),
    # Dashboards
    path('dashboard/client/',      views.client_dashboard, name='client_dashboard'),
    path('dashboard/tradie/',      views.tradie_dashboard, name='tradie_dashboard'),
    path('billing/',               views.billing,          name='billing'),
    # Tasks
    path('tasks/',                 views.browse_tasks,  name='browse_tasks'),
    path('tasks/post/',            views.post_task,     name='post_task'),
    path('tasks/<int:pk>/',        views.task_detail,   name='task_detail'),
    path('tasks/<int:pk>/quote/',  views.submit_quote,  name='submit_quote'),
    path('tasks/<int:pk>/quote/check-promo/', views.check_promo_code, name='check_promo_code'),
    path('tasks/<int:pk>/quoting-appointment/', views.book_quoting_appointment, name='book_quoting_appointment'),
    path('tasks/<int:pk>/quoting-appointment/<int:appt_pk>/accept/<int:slot_pk>/', views.accept_quoting_appointment_slot, name='accept_quoting_appointment_slot'),
    path('tasks/<int:pk>/quoting-appointment/<int:appt_pk>/decline/', views.decline_quoting_appointment, name='decline_quoting_appointment'),
    path('tasks/<int:pk>/quoting-appointment/<int:appt_pk>/cancel/', views.cancel_quoting_appointment, name='cancel_quoting_appointment'),
    path('tasks/<int:pk>/quotes/<int:qpk>/accept/', views.accept_quote, name='accept_quote'),
    path('tasks/<int:pk>/complete/', views.complete_task, name='complete_task'),
    # Reviews
    path('tasks/<int:pk>/rate/tradie/', views.rate_tradie, name='rate_tradie'),
    path('tasks/<int:pk>/rate/client/', views.rate_client, name='rate_client'),
    # Profile
    path('profile/<int:pk>/',      views.tradie_profile, name='tradie_profile'),
    # Notices
    path('notices/',                         views.notices,      name='notices'),
    path('notices/settings/',                views.notification_settings, name='notification_settings'),
    # Messages
    path('messages/',                        views.inbox,        name='inbox'),
    path('messages/<int:tpk>/<int:opk>/',    views.conversation, name='conversation'),
]
