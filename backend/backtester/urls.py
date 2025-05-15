"""
URL configuration for backtester project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from backtester_app.views import DataFetchView, BacktestView, IndicatorsView, BenchmarkView
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/fetch-data/', DataFetchView.as_view(), name='fetch-data'),
    path('api/backtest/', BacktestView.as_view(), name='backtest'),
    path('api/indicators/', IndicatorsView.as_view(), name='indicators'),
    path('api/benchmark/', BenchmarkView.as_view(), name='benchmark'),
    path('', TemplateView.as_view(template_name='index.html'), name='index'),
]
