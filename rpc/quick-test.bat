@echo off
:: ============================================================================
:: QUICK TEST - Fast RPC check
:: ============================================================================

echo.
echo Testing RPC on http://127.0.0.1:8545 ...
echo.

curl -s -X POST http://127.0.0.1:8545 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"

echo.
echo.
pause
