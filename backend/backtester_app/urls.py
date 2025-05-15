from django.urls import path
from .views import DataFetchView, IndicatorsView, BacktestView

urlpatterns = [
    path('fetch-data/', DataFetchView.as_view(), name='fetch-data'),
    path('indicators/', IndicatorsView.as_view(), name='indicators'),
    path('backtest/', BacktestView.as_view(), name='backtest'),
] 