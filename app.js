const express = require('express');
const path = require('path');
const fs = require('fs');
const app = express();

// Конфигурация
const PORT = process.env.PORT || 3000;
const HOST = '0.0.0.0';

// Middleware
app.use(express.static('public'));
app.use(express.json());

// Функция для чтения файлов проекта
function readProjectFile(filename) {
    try {
        return fs.readFileSync(filename, 'utf8');
    } catch (err) {
        return `Файл ${filename} не найден`;
    }
}

// Главная страница - AI Dashboard
app.get('/', (req, res) => {
    const html = `
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧠 AI Dashboard | Project Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }
        
        .header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
        }
        
        .card h3 {
            font-size: 1.5rem;
            margin-bottom: 15px;
            color: #4a5568;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-online { background: #48bb78; }
        .status-offline { background: #f56565; }
        .status-warning { background: #ed8936; }
        
        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            font-weight: 500;
            color: #718096;
        }
        
        .metric-value {
            font-weight: bold;
            color: #2d3748;
        }
        
        .logs {
            background: #1a202c;
            color: #e2e8f0;
            border-radius: 10px;
            padding: 20px;
            font-family: 'Courier New', monospace;
            max-height: 300px;
            overflow-y: auto;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #4299e1;
            color: white;
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            background: #3182ce;
            transform: scale(1.1);
        }
        
        .timestamp {
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-top: 20px;
            font-size: 0.9rem;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 AI Dashboard</h1>
            <p>Monitoring AI Project Status & Logs</p>
        </div>
        
        <div class="dashboard">
            <div class="card">
                <h3>
                    <span class="status-indicator status-online"></span>
                    Статус Сервера
                </h3>
                <div class="metric">
                    <span class="metric-label">Сервер</span>
                    <span class="metric-value">🟢 Онлайн</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Порт</span>
                    <span class="metric-value">${PORT}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Node.js</span>
                    <span class="metric-value">${process.version}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">PM2</span>
                    <span class="metric-value">✅ Готов</span>
                </div>
            </div>
            
            <div class="card">
                <h3>
                    <span class="status-indicator status-online"></span>
                    Файлы Проекта
                </h3>
                <div class="metric">
                    <span class="metric-label">project.init.md</span>
                    <span class="metric-value">✅</span>
                </div>
                <div class="metric">
                    <span class="metric-label">prestart.checklist</span>
                    <span class="metric-value">✅</span>
                </div>
                <div class="metric">
                    <span class="metric-label">ailog.md</span>
                    <span class="metric-value">✅</span>
                </div>
                <div class="metric">
                    <span class="metric-label">task.todo.json</span>
                    <span class="metric-value">✅</span>
                </div>
            </div>
            
            <div class="card">
                <h3>
                    <span class="status-indicator status-warning"></span>
                    Системные Метрики
                </h3>
                <div class="metric">
                    <span class="metric-label">Память</span>
                    <span class="metric-value">${Math.round(process.memoryUsage().heapUsed / 1024 / 1024)} MB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime</span>
                    <span class="metric-value">${Math.floor(process.uptime())}s</span>
                </div>
                <div class="metric">
                    <span class="metric-label">PID</span>
                    <span class="metric-value">${process.pid}</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3>📋 AI Log Monitor</h3>
            <div class="logs" id="ailog">
                Загрузка логов...
            </div>
        </div>
        
        <div class="timestamp">
            Последнее обновление: ${new Date().toLocaleString('ru-RU')}
        </div>
    </div>
    
    <button class="refresh-btn pulse" onclick="location.reload()">🔄</button>
    
    <script>
        // Загрузка AI логов
        async function loadAILogs() {
            try {
                const response = await fetch('/api/ailog');
                const text = await response.text();
                document.getElementById('ailog').textContent = text;
            } catch (err) {
                document.getElementById('ailog').textContent = 'Ошибка загрузки логов: ' + err.message;
            }
        }
        
        // Автообновление каждые 30 секунд
        setInterval(() => {
            loadAILogs();
        }, 30000);
        
        // Загрузка при старте
        loadAILogs();
    </script>
</body>
</html>`;
    
    res.send(html);
});

// API для получения AI логов
app.get('/api/ailog', (req, res) => {
    const ailog = readProjectFile('ailog.md');
    res.type('text/plain').send(ailog);
});

// API для получения статуса проекта
app.get('/api/status', (req, res) => {
    const status = {
        server: 'online',
        port: PORT,
        nodeVersion: process.version,
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        pid: process.pid,
        files: {
            'project.init.md': fs.existsSync('project.init.md'),
            'prestart.checklist': fs.existsSync('prestart.checklist'),
            'ailog.md': fs.existsSync('ailog.md'),
            'task.todo.json': fs.existsSync('task.todo.json'),
            'ai.meta.json': fs.existsSync('ai.meta.json')
        },
        timestamp: new Date().toISOString()
    };
    
    res.json(status);
});

// API для получения задач
app.get('/api/tasks', (req, res) => {
    try {
        const tasksData = readProjectFile('task.todo.json');
        const tasks = JSON.parse(tasksData);
        res.json(tasks);
    } catch (err) {
        res.status(500).json({ error: 'Не удалось загрузить задачи', details: err.message });
    }
});

// Запуск сервера
app.listen(PORT, HOST, () => {
    console.log(`
🧠 AI Dashboard Server запущен!
🌐 URL: http://localhost:${PORT}
📡 Host: ${HOST}
🚀 Node.js: ${process.version}
⚡ Готов к работе!
    `);
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('🛑 Получен сигнал SIGTERM, завершение работы...');
    process.exit(0);
});

process.on('SIGINT', () => {
    console.log('🛑 Получен сигнал SIGINT (Ctrl+C), завершение работы...');
    process.exit(0);
}); 