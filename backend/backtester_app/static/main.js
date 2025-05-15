document.addEventListener('DOMContentLoaded', () => {
    const tickerInput = document.getElementById('tickerInput');
    const strategySelect = document.getElementById('strategySelect');
    const fetchButton = document.getElementById('fetchData');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const resultsSection = document.getElementById('resultsSection');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    let equityChart = null;

    // Set default end date to today
    const today = new Date();
    endDateInput.value = today.toISOString().split('T')[0];

    // Define preset strategies
    const presetStrategies = {
        'GOLDEN_CROSS': {
            name: 'Golden Cross (50/200 SMA)',
            description: 'A long-term trend following strategy. Buy when the 50-day moving average crosses above the 200-day moving average, sell when it crosses below.',
            params: {
                indicator: 'SMA',
                short_window: 50,
                long_window: 200
            }
        },
        'DUAL_MA': {
            name: 'Dual Moving Average (10/30 SMA)',
            description: 'A medium-term trend following strategy. Buy when the 10-day moving average crosses above the 30-day moving average, sell when it crosses below.',
            params: {
                indicator: 'SMA',
                short_window: 10,
                long_window: 30
            }
        },
        'RSI_STRATEGY': {
            name: 'RSI Reversal Strategy',
            description: 'A mean-reversion strategy. Buy when RSI drops below 30 (oversold) and then rises back above it. Sell when RSI rises above 70 (overbought) and then drops below it.',
            params: {
                indicator: 'RSI',
                rsi_period: 14,
                overbought: 70,
                oversold: 30
            }
        },
        'MACD_CROSS': {
            name: 'MACD Signal Line Cross',
            description: 'A versatile strategy that works in trending and ranging markets. Buy when the MACD line crosses above the signal line, sell when it crosses below.',
            params: {
                indicator: 'MACD',
                fast_period: 12,
                slow_period: 26,
                signal_period: 9
            }
        },
        'BOLLINGER_BOUNCE': {
            name: 'Bollinger Band Bounce',
            description: 'A mean-reversion strategy. Buy when price touches the lower band and starts to move up. Sell when price touches the upper band and starts to move down.',
            params: {
                indicator: 'BBANDS',
                window: 20,
                num_std_dev: 2
            }
        }
    };

    // Populate strategy select dropdown with preset strategies
    function populateStrategyDropdown() {
        strategySelect.innerHTML = '';
        Object.keys(presetStrategies).forEach(strategyKey => {
            const option = document.createElement('option');
            option.value = strategyKey;
            option.textContent = presetStrategies[strategyKey].name;
            strategySelect.appendChild(option);
        });
    }

    // Initialize dropdown
    populateStrategyDropdown();

    // Add strategy description element
    const strategyDescription = document.createElement('div');
    strategyDescription.className = 'strategy-description';
    strategySelect.parentNode.appendChild(strategyDescription);

    // Update description when strategy changes
    strategySelect.addEventListener('change', () => {
        const selectedStrategy = strategySelect.value;
        const strategy = presetStrategies[selectedStrategy];
        strategyDescription.textContent = strategy.description;
    });

    // Set initial description
    strategySelect.dispatchEvent(new Event('change'));

    fetchButton.addEventListener('click', async() => {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) {
            alert('Please enter a stock ticker');
            return;
        }

        try {
            loadingIndicator.style.display = 'block';
            resultsSection.style.display = 'none';

            // Get selected strategy and its parameters
            const strategyKey = strategySelect.value;
            const strategy = presetStrategies[strategyKey];
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;

            // Always fetch SPY data first for benchmark comparison
            console.log("Fetching SPY data for comparison...");

            // Store benchmark data globally to ensure it's available
            let benchmarkData = null;

            try {
                // First, always get benchmark performance for SPY (buy & hold)
                console.log('Sending SPY benchmark request with data:', {
                    symbol: 'SPY',
                    start_date: startDate,
                    end_date: endDate
                });

                const benchmarkResponse = await fetch('/api/benchmark/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        symbol: 'SPY',
                        start_date: startDate,
                        end_date: endDate
                    })
                });

                console.log('SPY benchmark response status:', benchmarkResponse.status);

                if (benchmarkResponse.ok) {
                    benchmarkData = await benchmarkResponse.json();
                    console.log('SPY benchmark data loaded successfully:', benchmarkData);
                } else {
                    const errorText = await benchmarkResponse.text();
                    console.warn('Failed to get SPY benchmark data:', errorText);
                }
            } catch (benchError) {
                console.error('Error fetching benchmark initially:', benchError);
                // Continue with the main data fetch even if benchmark fails
            }

            // Now fetch data for the selected ticker
            const response = await fetch('/api/fetch-data/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ symbol: ticker })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch data');
            }

            const data = await response.json();
            console.log('Data fetched:', data);

            // Run backtest with strategy parameters
            const backtestResponse = await fetch('/api/backtest/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...strategy.params,
                    start_date: startDate,
                    end_date: endDate
                })
            });

            if (!backtestResponse.ok) {
                const errorData = await backtestResponse.json();
                throw new Error(errorData.error || 'Failed to run backtest');
            }

            const backtestData = await backtestResponse.json();
            backtestData.start_date = startDate;
            backtestData.end_date = endDate;
            backtestData.strategy = strategyKey;
            backtestData.strategy_name = strategy.name;
            console.log('Backtest results:', backtestData);

            // If we already have the benchmark data, use it
            if (benchmarkData) {
                displayResults(backtestData, benchmarkData);
            } else {
                // Try once more to get the benchmark data
                try {
                    const secondBenchmarkResponse = await fetch('/api/benchmark/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            symbol: 'SPY',
                            start_date: startDate,
                            end_date: endDate
                        })
                    });

                    if (secondBenchmarkResponse.ok) {
                        benchmarkData = await secondBenchmarkResponse.json();
                        console.log('SPY benchmark results (second attempt):', benchmarkData);
                        displayResults(backtestData, benchmarkData);
                    } else {
                        console.warn('Failed to get SPY benchmark data on second attempt');
                        displayResults(backtestData);
                    }
                } catch (error) {
                    console.error('Error fetching benchmark on second attempt:', error);
                    displayResults(backtestData);
                }
            }

        } catch (error) {
            console.error('Error:', error);
            alert(`Error: ${error.message}`);
        } finally {
            loadingIndicator.style.display = 'none';
        }
    });

    function displayResults(data, spyData = null) {
        console.log("Displaying results with strategy data:", data);
        console.log("SPY benchmark data for display:", spyData);

        // Format dates for display
        const startDate = new Date(data.start_date);
        const endDate = new Date(data.end_date);
        const formattedStartDate = startDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
        const formattedEndDate = endDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

        // Display backtest period and strategy
        document.getElementById('backtestPeriod').textContent = `${formattedStartDate} to ${formattedEndDate}`;
        document.getElementById('strategyName').textContent = data.strategy_name || getStrategyName(data.strategy);

        // Update strategy metrics
        document.getElementById('totalReturn').textContent = `${(data.total_return * 100).toFixed(2)}%`;
        document.getElementById('maxDrawdown').textContent = `${(data.max_drawdown * 100).toFixed(2)}%`;
        document.getElementById('sharpeRatio').textContent = data.sharpe_ratio.toFixed(2);

        // Parse portfolio value, dates, and trades from JSON strings
        const portfolioValue = JSON.parse(data.equity_curve);
        const trades = JSON.parse(data.trades);

        // Ensure we get the portfolio dates
        let portfolioDates = null;
        if (data.portfolio_dates) {
            portfolioDates = JSON.parse(data.portfolio_dates);
            console.log("Portfolio dates loaded:", portfolioDates.length, "dates");
        } else {
            console.warn("No portfolio dates available in data");
        }

        // Update SPY metrics if available
        let spyPortfolioValue = null;
        let spyDates = null;
        if (spyData && spyData.equity_curve) {
            try {
                console.log("Processing SPY data with:", spyData);
                document.getElementById('spyReturn').textContent = `${(spyData.total_return * 100).toFixed(2)}%`;
                document.getElementById('spyDrawdown').textContent = `${(spyData.max_drawdown * 100).toFixed(2)}%`;
                document.getElementById('spySharpe').textContent = spyData.sharpe_ratio.toFixed(2);

                // Parse SPY portfolio value and dates for chart
                spyPortfolioValue = JSON.parse(spyData.equity_curve);
                if (spyData.portfolio_dates) {
                    spyDates = JSON.parse(spyData.portfolio_dates);
                }
                console.log("SPY data loaded for comparison, portfolio values:", spyPortfolioValue.length);
            } catch (e) {
                console.error("Error parsing SPY data:", e);
                document.getElementById('spyReturn').textContent = '-';
                document.getElementById('spyDrawdown').textContent = '-';
                document.getElementById('spySharpe').textContent = '-';
            }
        } else {
            // If no SPY data, display placeholders
            console.warn('No SPY comparison data available:', spyData);
            document.getElementById('spyReturn').textContent = '-';
            document.getElementById('spyDrawdown').textContent = '-';
            document.getElementById('spySharpe').textContent = '-';
        }

        // Update portfolio value chart
        updatePortfolioChart(portfolioValue, spyPortfolioValue, portfolioDates, spyDates);

        // Update trades table
        updateTradesTable(trades);

        // Show results section
        resultsSection.style.display = 'block';
    }

    function getStrategyName(strategyKey) {
        return presetStrategies[strategyKey] ? presetStrategies[strategyKey].name : strategyKey;
    }

    function updatePortfolioChart(portfolioValue, spyPortfolioValue = null, portfolioDates = null, spyDates = null) {
        const ctx = document.getElementById('equityCurve').getContext('2d');

        if (equityChart) {
            equityChart.destroy();
        }

        // Create strategy dataset
        const datasets = [{
            label: 'Strategy',
            data: portfolioValue,
            borderColor: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.1)',
            fill: true,
            tension: 0.4,
            borderWidth: 2
        }];

        // Add SPY dataset if available
        if (spyPortfolioValue && spyPortfolioValue.length > 0) {
            console.log("Including SPY data in chart:", spyPortfolioValue.length, "data points");

            datasets.push({
                label: 'SPY (Buy & Hold)',
                data: spyPortfolioValue,
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            });
        } else {
            console.warn("No SPY data available for chart");
        }

        // Format X-axis labels as months/years if we have date data
        let labels = Array.from({ length: portfolioValue.length }, (_, i) => i);

        if (portfolioDates && portfolioDates.length > 0) {
            // Ensure we don't exceed the number of portfolio values
            const dateCount = Math.min(portfolioDates.length, portfolioValue.length);

            // Use the dates we have for labels
            labels = portfolioDates.slice(0, dateCount).map(dateStr => {
                const d = new Date(dateStr);
                return d.toLocaleString('default', { month: 'short', year: '2-digit' });
            });

            // If we have many dates, reduce the number of displayed labels
            const stepSize = Math.max(1, Math.floor(labels.length / 12));
            labels = labels.map((label, i) => i % stepSize === 0 ? label : '');
        }

        equityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1000 // General animation time
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Portfolio Value Over Time',
                        font: { size: 16 }
                    },
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            boxWidth: 10
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: $${context.raw ? context.raw.toFixed(2) : 'N/A'}`;
                            },
                            title: function(tooltipItems) {
                                if (portfolioDates && tooltipItems.length > 0) {
                                    const index = tooltipItems[0].dataIndex;
                                    if (index < portfolioDates.length) {
                                        return portfolioDates[index];
                                    }
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(200, 200, 200, 0.2)'
                        },
                        ticks: {
                            maxTicksLimit: 12, // Show up to 12 months/years
                            callback: function(value, index) {
                                if (portfolioDates && portfolioDates.length > 0) {
                                    // Display fewer labels for readability
                                    const step = Math.ceil(portfolioDates.length / 12);
                                    if (index % step === 0) {
                                        const d = new Date(portfolioDates[index]);
                                        return d.toLocaleString('default', { month: 'short', year: '2-digit' });
                                    }
                                    return '';
                                }
                                return value;
                            }
                        }
                    },
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(200, 200, 200, 0.2)'
                        },
                        ticks: {
                            callback: value => `$${value.toLocaleString()}`
                        }
                    }
                }
            }
        });
    }

    function updateTradesTable(trades) {
        const tbody = document.getElementById('tradesTableBody');
        tbody.innerHTML = '';

        if (!trades || trades.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="6" style="text-align:center; color:#888;">No trades were made during this period.</td>`;
            tbody.appendChild(row);
            return;
        }

        trades.forEach(trade => {
            const row = document.createElement('tr');
            const percentPnl = trade.percent_pnl.toFixed(2);
            const dollarPnl = trade.dollar_pnl.toFixed(2);
            row.innerHTML = `
                <td>${new Date(trade.entry_date).toLocaleDateString()}</td>
                <td>${new Date(trade.exit_date).toLocaleDateString()}</td>
                <td>$${trade.entry_price.toFixed(2)}</td>
                <td>$${trade.exit_price.toFixed(2)}</td>
                <td>${trade.position > 0 ? 'Long' : 'Short'}</td>
                <td class="${trade.dollar_pnl >= 0 ? 'profit' : 'loss'}">
                    ${percentPnl > 0 ? '+' : ''}${percentPnl}% ($${dollarPnl > 0 ? '+' : ''}${dollarPnl})
                </td>
            `;
            tbody.appendChild(row);
        });
    }
});