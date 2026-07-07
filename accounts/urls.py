# from django.urls import path
# from . import views

# urlpatterns = [
#     path('csrf/', views.get_csrf_token, name='csrf'),
#     path('register/', views.register_viewer, name='register'),
#     path('login/', views.login_view, name='login'),
#     path('logout/', views.logout_view, name='logout'),
#     path('apply-creator/', views.submit_creator_application, name='apply_creator'),
#     path('status/', views.check_auth_status, name='auth_status'),
# ]


from django.urls import path
from . import views

urlpatterns = [
    path('csrf/', views.get_csrf_token, name='csrf'),
    path('login/', views.admin_login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('status/', views.check_auth_status, name='auth_status'),
]