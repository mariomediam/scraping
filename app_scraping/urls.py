from django.urls import path

from .views import (
    HomeView, 
    test_scraping, 
    login_siaf, 
    incrementar_numero,
    siaf_status,
    siaf_endpoint_example,
    siaf_clear_tokens,
    siaf_token_info,
    siaf_leer_devengado,
)

urlpatterns = [
    path('home', HomeView.as_view(), name='home'),
    path('test-scraping', test_scraping.as_view(), name='test-scraping'),
    path('login-siaf', login_siaf.as_view(), name='login-siaf'),
    path('incrementar', incrementar_numero.as_view(), name='incrementar'),
    path('siaf-status', siaf_status.as_view(), name='siaf-status'),
    path('siaf-endpoint-example', siaf_endpoint_example.as_view(), name='siaf-endpoint-example'),
    path('siaf-clear-tokens', siaf_clear_tokens.as_view(), name='siaf-clear-tokens'),
    path('siaf-token-info', siaf_token_info.as_view(), name='siaf-token-info'),
    path('siaf-leer-devengado', siaf_leer_devengado.as_view(), name='siaf-leer-devengado'),
]
