"""
Contains all the URLs for the Dark Language Support App
"""

from django.conf.urls import url

from openedx.core.djangoapps.dark_lang import views

urlpatterns = [
    url(r'^$', views.PreviewLanguageFragmentView.as_view(), name='preview_lang'),
]
