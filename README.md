# Manufacturing Progress Assistant

A lightweight local MVP web app for tracking manufacturing project, procurement, engineering, production issue, audit, and SAP/BOM progress. It uses Flask, SQLite, simple HTML/CSS, and keyword matching for natural language-like queries.

## Features

- Dashboard with total tasks, status counts, overdue tasks, and recently updated tasks
- Add, view, edit, and delete manufacturing progress tasks
- Task list with status, priority, due date, and action buttons
- Natural language-like query page using simple keyword matching
- Weekly report generator with active, completed, blocked, overdue, supplier, and high-priority summaries
- Seed data for realistic manufacturing operations examples

## Tech Stack

- Python
- Flask
- SQLite
- HTML/CSS
- Bootstrap

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Initialize the Database

```bash
python init_db.py
```

This creates `database.db` and loads the sample manufacturing task data.

## Run the Flask App

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Example Queries

- What is the status of film rack purchase?
- 膜架采购现在到哪了？
- Which tasks are blocked?
- What tasks are waiting for supplier?
- Show overdue tasks
- 客户审核准备进度怎么样？
- SAP BOM progress
- 物料变更进度

## Project Structure

```text
manufacturing-progress-assistant/
├── app.py
├── requirements.txt
├── README.md
├── database.db
├── init_db.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── add_task.html
│   ├── task_list.html
│   ├── task_detail.html
│   ├── edit_task.html
│   ├── query.html
│   └── report.html
└── static/
    └── style.css
```

## Future Improvement Ideas

- Connect to Microsoft Teams
- Connect to SharePoint Excel
- Connect to Outlook emails
- Add OpenAI API for better natural language understanding
- Add user login and permissions
- Add automatic reminder for overdue tasks
- Export weekly report to Word or PDF
- Add charts for task status and risk level
