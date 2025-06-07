# 🤖 AIL — Assistant Initialization Logic

**AIL** is a minimal yet powerful template for automating project initialization using AI (e.g., Cursor). It provides structure, logs actions, verifies environment, and restores context seamlessly.

---

## 🔍 Project Purpose

AIL is not just a repository. It's a **logic template** that any AI assistant should follow when starting a project:

* Entry point is `project.init.md`
* Pre-launch checks are in `prestart.checklist`
* Logs go into `ailog.md`
* Tasks are managed in `task.todo.json`
* Behavior rules are set in `ai.meta.json`

---

## 🧩 Project Structure

```
/aiproject/
├── project.init.md        # Entry point
├── prestart.checklist     # Pre-launch checks
├── ailog.md               # AI action log
├── task.todo.json         # Current tasks
├── ai.meta.json           # Cursor behavior rules
├── snapshot.success.md    # Successful session snapshot
├── app.js                 # Node.js server
├── package.json           # Project dependencies
├── ecosystem.config.js    # PM2 configuration
└── logs/                  # Logs directory
```

---

## 🚀 How to Run the Project

### 🖥️ 1. Install dependencies

```bash
npm install -g pm2
npm install
```

### ▶️ 2. Start the server

```bash
npm start
```

### 🔁 3. Run via PM2

```bash
npm run pm2
```

---

## 🤖 Special Prompt for Cursor

Add this to **User Rules** (via `.cursor/user-rules.json` or Cursor settings):

```json
[
  "Always start from project.init.md",
  "If the file is missing — suggest creating it",
  "Before starting tasks — validate prestart.checklist",
  "If errors found — stop and log into ailog.md",
  "If ailog.md contains 'Problems' — resolve them first",
  "If task.todo.json is empty — wait for user input and log it",
  "If snapshot.success.md exists — use it to understand expected state",
  "Always summarize the session in ailog.md (what was done, what remains)"
]
```

---

## 📸 Successful Session Snapshot

See [`snapshot.success.md`](./snapshot.success.md) — shows an ideal state after a successful session.

---

## 📚 License

MIT — free to use, adapt, fork, and improve. Share your variations and help improve the ecosystem.

---

🧠 *Created with love for logic and AI 💡*

---

## 📝 Дополнение на русском

### Назначение

Этот шаблон помогает автоматизировать запуск проектов с AI, структурировать работу, отслеживать прогресс и не терять задачи между сессиями.

### Что делает AI:

* Стартует с `project.init.md`
* Проверяет `prestart.checklist` перед запуском
* Записывает действия в `ailog.md`
* Работает с задачами в `task.todo.json`
* Использует `snapshot.success.md` для восстановления состояния

Подходит для любых AI-ассистентов, включая Cursor.
