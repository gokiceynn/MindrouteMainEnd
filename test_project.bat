@echo off
echo ========================================
echo MindRoute Test Script
echo ========================================
echo.

echo [1/4] MongoDB Bağlantı Kontrolü...
python -c "from pymongo import MongoClient; c = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=2000); c.admin.command('ping'); print('✅ MongoDB bağlantısı başarılı')" 2>nul || (
    echo ❌ MongoDB bağlantısı başarısız!
    echo    MongoDB'yi başlatmak için: mongod
    pause
    exit /b 1
)

echo.
echo [2/4] Python Bağımlılıkları Kontrolü...
python -c "import fastapi, uvicorn, pymongo, requests; print('✅ Tüm Python bağımlılıkları yüklü')" 2>nul || (
    echo ❌ Bazı bağımlılıklar eksik!
    echo    Yüklemek için: pip install -r app/requirements.txt
    pause
    exit /b 1
)

echo.
echo [3/4] Backend Sunucusu Başlatılıyor...
echo    Port: 8002
echo    URL: http://127.0.0.1:8002
echo    Health: http://127.0.0.1:8002/health
echo.
echo    ⚠️  Bu pencereyi kapatmayın! Backend burada çalışacak.
echo.
cd app
python -m uvicorn app.main:app --reload --port 8002 --host 127.0.0.1

pause

