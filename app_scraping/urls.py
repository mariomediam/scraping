from django.urls import path

from .views import HomeView, test_scraping, login_siaf, incrementar_numero

urlpatterns = [
    path('home', HomeView.as_view(), name='home'),
    path('test-scraping', test_scraping.as_view(), name='test-scraping'),
    path('login-siaf', login_siaf.as_view(), name='login-siaf'),
    path('incrementar', incrementar_numero.as_view(), name='incrementar'),
]
