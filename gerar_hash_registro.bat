@echo off
rem Gera o pacote do codigo-fonte do ManuMetria e o hash SHA-512 para o registro
rem de software (INPI). Procedimento em DESENVOLVIMENTO.md.
rem O ZIP e o .txt com o hash vao para a pasta REGISTRO_INPI, ao lado desta pasta.
rem O ZIP gerado nunca mais pode ser alterado: guarde-o em mais de um lugar.
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo.
echo Gera o pacote do codigo-fonte e o hash SHA-512 (ver DESENVOLVIMENTO.md).
choice /c SN /m "Gerar o pacote para o registro agora"
if errorlevel 2 exit /b 0
%PY% tools\gerar_hash_registro.py
echo.
pause
