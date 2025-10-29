# urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('download/', views.download_video, name='download_video'),
]