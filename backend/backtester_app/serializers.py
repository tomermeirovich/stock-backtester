from rest_framework import serializers
from .models import PriceData, BacktestResult

class PriceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceData
        fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

class BacktestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestResult
        fields = ['id', 'created_at', 'indicator', 'short_window', 'long_window',
                 'start_date', 'end_date', 'total_return', 'max_drawdown',
                 'sharpe_ratio', 'equity_curve', 'trades'] 