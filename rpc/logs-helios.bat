@echo off
:: ============================================================================
:: VIEW HELIOS LOGS
:: ============================================================================

title Helios Logs
color 0E

echo.
echo  ============================================
echo   HELIOS LOGS (Press Ctrl+C to exit)
echo  ============================================
echo.

docker logs helios-client -f --tail 100
