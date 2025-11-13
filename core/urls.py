from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index_tr'),
    path('en/', views.index_en, name='index_en'),
    path('ar/', views.index_ar, name='index_ar'),
    path('download/', views.download_video, name='download_video'),
    path('proxy-download/', views.proxy_download, name='proxy_download'),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", TemplateView.as_view(template_name="sitemap.xml", content_type="application/xml")),
]