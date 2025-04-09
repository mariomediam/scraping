from django.urls import path

from .views import HomeView, test_scraping

urlpatterns = [
    path('home', HomeView.as_view(), name='home'),
    path('test-scraping', test_scraping.as_view(), name='test-scraping'),
]
