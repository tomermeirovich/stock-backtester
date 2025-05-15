from django.db import models

# Create your models here.

class PriceData(models.Model):
    timestamp = models.DateTimeField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.FloatField()

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp} - Close: {self.close}"

class BacktestResult(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    indicator = models.CharField(max_length=50)
    short_window = models.IntegerField(null=True, blank=True)
    long_window = models.IntegerField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_return = models.FloatField(default=0.0)
    max_drawdown = models.FloatField(default=0.0)
    sharpe_ratio = models.FloatField(default=0.0)
    equity_curve = models.JSONField()
    trades = models.JSONField()

    def __str__(self):
        strategy_desc = f"{self.indicator}"
        if self.short_window is not None and self.long_window is not None:
            strategy_desc += f" ({self.short_window}/{self.long_window})"
        return f"{strategy_desc} - Return: {self.total_return:.2%}"
