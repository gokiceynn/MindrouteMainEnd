@echo off
echo ========================================
echo MindRoute Frontend Başlatılıyor
echo ========================================
echo.

echo [1/2] Node Modules Kontrolü...
if not exist "mindroute-web\node_modules" (
    echo    node_modules bulunamadı, yükleniyor...
    cd mindroute-web
    call npm install
    cd ..
)

echo.
echo [2/2] Frontend Sunucusu Başlatılıyor...
echo    Port: 5173
echo    URL: http://localhost:5173
echo.
echo    ⚠️  Bu pencereyi kapatmayın! Frontend burada çalışacak.
echo.

cd mindroute-web
call npm run dev

pause

