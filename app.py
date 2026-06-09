import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


app = Flask(__name__)
app.secret_key = "local-mvp-secret-key"

DATABASE = Path(__file__).with_name("database.db")

CATEGORIES = [
    "Procurement",
    "Engineering",
    "Production Issue",
    "SAP / BOM",
    "Audit Preparation",
    "Other",
]

STATUSES = [
    "Not Started",
    "In Progress",
    "Waiting for Approval",
    "Waiting for Supplier",
    "Blocked",
    "Completed",
    "Cancelled",
]

PRIORITIES = ["Low", "Medium", "High", "Urgent"]
ACTIVE_STATUSES = ["Not Started", "In Progress", "Waiting for Approval", "Waiting for Supplier", "Blocked"]
QUERY_ALIASES = {
    "膜架": "film rack",
    "膜架采购": "film rack purchase",
    "采购": "procurement",
    "内包装": "inner packaging",
    "凹痕": "dent",
    "客户审核": "customer audit",
    "审核准备": "audit preparation",
    "物料": "sap bom",
}


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_all_tasks():
    with get_connection() as connection:
        return connection.execute("SELECT * FROM tasks ORDER BY due_date ASC, id ASC").fetchall()


def fetch_task(task_id):
    with get_connection() as connection:
        return connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def is_overdue(task):
    return task["status"] not in ("Completed", "Cancelled") and task["due_date"] < date.today().isoformat()


def summarize_task(task):
    return (
        f"{task['title']} is currently {task['status']}. "
        f"Owner: {task['owner']}. Latest progress: {task['progress_note']} "
        f"Main risk: {task['risk']} Due date: {task['due_date']}."
    )


def count_phrase(count, singular_label, plural_label=None):
    label = singular_label if count == 1 else (plural_label or f"{singular_label}s")
    return f"{count} {label}"


def is_are(count):
    return "is" if count == 1 else "are"


def search_tasks(query):
    normalized_query = query.strip().lower()
    alias_terms = []
    for chinese_term, english_term in QUERY_ALIASES.items():
        if chinese_term in normalized_query:
            alias_terms.append(english_term)
            normalized_query = f"{normalized_query} {english_term}"

    tasks = fetch_all_tasks()

    if not normalized_query:
        return []

    if any(keyword in normalized_query for keyword in ["overdue", "超期", "延期"]):
        return [task for task in tasks if is_overdue(task)]

    if any(keyword in normalized_query for keyword in ["blocked", "受阻", "卡住"]):
        return [task for task in tasks if task["status"] == "Blocked"]

    if any(keyword in normalized_query for keyword in ["supplier", "供应商", "报价"]):
        return [task for task in tasks if task["status"] == "Waiting for Supplier"]

    matches = []
    for task in tasks:
        searchable_text = " ".join(
            [
                task["title"],
                task["category"],
                task["owner"],
                task["status"],
                task["progress_note"],
                task["risk"],
            ]
        ).lower()

        if normalized_query in searchable_text:
            matches.append(task)
            continue

        query_terms = [term for term in normalized_query.replace("/", " ").split() if len(term) > 1]
        if any(term in searchable_text for term in query_terms):
            matches.append(task)

    if any(keyword in normalized_query for keyword in ["audit", "审核", "客户审核"]):
        audit_tasks = [task for task in tasks if task["category"] == "Audit Preparation"]
        matches = audit_tasks + [task for task in matches if task["category"] != "Audit Preparation"]

    if any(keyword in normalized_query for keyword in ["bom", "sap", "物料"]):
        bom_tasks = [task for task in tasks if task["category"] == "SAP / BOM"]
        matches = bom_tasks + [task for task in matches if task["category"] != "SAP / BOM"]

    seen_ids = set()
    unique_matches = []
    for task in matches:
        if task["id"] not in seen_ids:
            unique_matches.append(task)
            seen_ids.add(task["id"])

    if alias_terms:
        unique_matches.sort(
            key=lambda task: (
                not any(term in task["title"].lower() for term in alias_terms),
                task["due_date"],
            )
        )

    return unique_matches


@app.context_processor
def inject_options():
    return {
        "categories": CATEGORIES,
        "statuses": STATUSES,
        "priorities": PRIORITIES,
        "today": date.today().isoformat(),
        "is_overdue": is_overdue,
    }


@app.route("/", methods=["GET", "POST"])
def index():
    query_text = ""
    summaries = []

    if request.method == "POST":
        query_text = request.form.get("query", "")
        summaries = [summarize_task(task) for task in search_tasks(query_text)]

    tasks = fetch_all_tasks()
    status_counts = {status: 0 for status in STATUSES}
    for task in tasks:
        status_counts[task["status"]] = status_counts.get(task["status"], 0) + 1

    overdue_tasks = [task for task in tasks if is_overdue(task)]
    recent_tasks = sorted(tasks, key=lambda task: task["last_updated"], reverse=True)[:5]

    return render_template(
        "index.html",
        total_tasks=len(tasks),
        status_counts=status_counts,
        overdue_tasks=overdue_tasks,
        recent_tasks=recent_tasks,
        query_text=query_text,
        summaries=summaries,
    )


@app.route("/tasks")
def task_list():
    return render_template("task_list.html", tasks=fetch_all_tasks())


@app.route("/tasks/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        form = request.form
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    title, category, owner, status, priority,
                    progress_note, risk, due_date, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form["title"],
                    form["category"],
                    form["owner"],
                    form["status"],
                    form["priority"],
                    form["progress_note"],
                    form["risk"],
                    form["due_date"],
                    form["last_updated"],
                ),
            )
        flash("Task added successfully.")
        return redirect(url_for("task_list"))

    return render_template("add_task.html")


@app.route("/tasks/<int:task_id>")
def task_detail(task_id):
    task = fetch_task(task_id)
    if task is None:
        flash("Task not found.")
        return redirect(url_for("task_list"))
    return render_template("task_detail.html", task=task)


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = fetch_task(task_id)
    if task is None:
        flash("Task not found.")
        return redirect(url_for("task_list"))

    if request.method == "POST":
        form = request.form
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET owner = ?, status = ?, priority = ?, progress_note = ?,
                    risk = ?, due_date = ?, last_updated = ?
                WHERE id = ?
                """,
                (
                    form["owner"],
                    form["status"],
                    form["priority"],
                    form["progress_note"],
                    form["risk"],
                    form["due_date"],
                    form["last_updated"],
                    task_id,
                ),
            )
        flash("Task updated successfully.")
        return redirect(url_for("task_detail", task_id=task_id))

    return render_template("edit_task.html", task=task)


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    flash("Task deleted successfully.")
    return redirect(url_for("task_list"))


@app.route("/query", methods=["GET", "POST"])
def query():
    query_text = ""
    matching_tasks = []
    summaries = []

    if request.method == "POST":
        query_text = request.form.get("query", "")
        matching_tasks = search_tasks(query_text)
        summaries = [summarize_task(task) for task in matching_tasks]

    return render_template(
        "query.html",
        query_text=query_text,
        matching_tasks=matching_tasks,
        summaries=summaries,
    )


@app.route("/report")
def report():
    tasks = fetch_all_tasks()
    active_tasks = [task for task in tasks if task["status"] in ACTIVE_STATUSES]
    completed_tasks = [task for task in tasks if task["status"] == "Completed"]
    blocked_tasks = [task for task in tasks if task["status"] == "Blocked"]
    overdue_tasks = [task for task in tasks if is_overdue(task)]
    supplier_tasks = [task for task in tasks if task["status"] == "Waiting for Supplier"]
    high_priority_tasks = [task for task in tasks if task["priority"] in ("High", "Urgent")]

    risks = []
    for task in blocked_tasks + high_priority_tasks:
        if task["risk"] and task["risk"] not in risks:
            risks.append(task["risk"])
    main_risks = "; ".join(risks[:4]) if risks else "No major risks reported this week."

    report_text = (
        "Weekly Progress Summary:\n\n"
        f"There are {count_phrase(len(active_tasks), 'active task')} this week. "
        f"{count_phrase(len(completed_tasks), 'task')} {is_are(len(completed_tasks))} completed, "
        f"{count_phrase(len(blocked_tasks), 'task')} {is_are(len(blocked_tasks))} blocked, "
        f"and {count_phrase(len(supplier_tasks), 'task')} {is_are(len(supplier_tasks))} waiting for supplier response.\n\n"
        f"{count_phrase(len(overdue_tasks), 'task')} {is_are(len(overdue_tasks))} overdue. "
        f"{count_phrase(len(high_priority_tasks), 'task')} {is_are(len(high_priority_tasks))} marked High or Urgent priority.\n\n"
        f"Main risks: {main_risks}"
    )

    return render_template(
        "report.html",
        report_text=report_text,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        blocked_tasks=blocked_tasks,
        overdue_tasks=overdue_tasks,
        supplier_tasks=supplier_tasks,
        high_priority_tasks=high_priority_tasks,
    )


if __name__ == "__main__":
    app.run(debug=True)
