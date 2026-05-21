import requests
import pandas as pd
from datetime import datetime
import re
import os
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta, timezone

# Date range filter — last 8 weeks
end_date = datetime.now(timezone.utc)
start_date = end_date - timedelta(weeks=8)
start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
print(f"Fetching entries from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

API_KEY = os.getenv("CLOCKIFY_API_KEY")
WORKSPACE_ID = "5d31e75e59da6530a30fc2f1"

headers = {"X-Api-Key": API_KEY}

name_mapping = {
    "feenstdr": "Darren Feenstra",
    "Kristin Bennett": "Kristin Bennett",
    "Brady Semple": "Brady Semple",
    "Laiba Yousafzai": "Laiba Yousafzai",
    "Patrick Chin": "Patrick Chin",
    "ramesm11": "Mahdi",
}

MMRI_EMPLOYEES = [
    "Kristin Bennett", "Darren Feenstra", "Brady Semple",
    "Laiba Yousafzai", "Patrick Chin", "Mahdi"
]

# Get all projects with pagination
print("Loading projects...")
all_projects = []
page = 1
while True:
    projects_response = requests.get(
        f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/projects",
        headers=headers,
        params={"page": page, "page-size": 50}
    )
    page_projects = projects_response.json()
    if not page_projects:
        break
    all_projects.extend(page_projects)
    page += 1

projects = {p['id']: p['name'] for p in all_projects}
print(f"Total projects found: {len(projects)}")

# Get all users with pagination
print("Loading users...")
users = []
page = 1
while True:
    users_response = requests.get(
        f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/users",
        headers=headers,
        params={"page": page, "page-size": 50}
    )
    page_users = users_response.json()
    if not page_users:
        break
    users.extend(page_users)
    page += 1

print(f"Total users found: {len(users)}")

# Get entries for MMRI employees first to find relevant projects
print("Finding relevant projects...")
mmri_project_ids = set()
for user in users:
    user_name = user['name']
    mapped_name = name_mapping.get(user_name, user_name)
    if mapped_name not in MMRI_EMPLOYEES:
        continue
    user_id = user['id']
    
    entries_response = requests.get(
    f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/user/{user_id}/time-entries",
    headers=headers,
    params={"start": start_str, "end": end_str, "page-size": 500}
)
    entries = entries_response.json()
    for entry in entries:
        project_id = entry.get('projectId', '')
        if project_id:
            mmri_project_ids.add(project_id)

print(f"Relevant projects found: {len(mmri_project_ids)}")

# Get tasks only for relevant projects
print("Loading tasks for relevant projects...")
project_tasks = {}
for project_id in mmri_project_ids:
    tasks_response = requests.get(
        f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/projects/{project_id}/tasks",
        headers=headers
    )
    tasks = tasks_response.json()
    project_tasks[project_id] = {t['id']: t['name'] for t in tasks} if isinstance(tasks, list) else {}

def parse_duration(duration):
    if not duration:
        return 0
    hours = re.search(r'(\d+)H', duration)
    minutes = re.search(r'(\d+)M', duration)
    h = int(hours.group(1)) if hours else 0
    m = int(minutes.group(1)) if minutes else 0
    return round(h + m/60, 2)

all_entries = []

for user in users:
    user_name = user['name']
    mapped_name = name_mapping.get(user_name, user_name)

    if mapped_name not in MMRI_EMPLOYEES:
        continue

    user_id = user['id']
    print(f"Fetching entries for {mapped_name}...")

    entries_response = requests.get(
    f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/user/{user_id}/time-entries",
    headers=headers,
    params={"start": start_str, "end": end_str, "page-size": 500}
)
    entries = entries_response.json()

    for entry in entries:
        project_id = entry.get('projectId', '')
        full_project_name = projects.get(project_id, 'No Project') if project_id else 'No Project'
        # Extract just the project code (everything before the first ' - ')
        project_name = full_project_name.split(' - ')[0] if ' - ' in full_project_name else full_project_name
        task_id = entry.get('taskId', '')
        task_name = project_tasks.get(project_id, {}).get(task_id, 'No Task') if task_id else 'No Task'
        duration = entry.get('timeInterval', {}).get('duration', '')
        start = entry.get('timeInterval', {}).get('start', '')

        if start:
            date = datetime.fromisoformat(start.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            week = datetime.fromisoformat(start.replace('Z', '+00:00')).strftime('%Y-W%W')
        else:
            date = ''
            week = ''

        all_entries.append({
            'Employee': mapped_name,
            'Project': project_name,
            'Task': task_name,
            'Date': date,
            'Week': week,
            'Hours': parse_duration(duration)
        })

df = pd.DataFrame(all_entries)
df.to_csv('clockify_data.csv', index=False)
print("Done! clockify_data.csv created")
print(df.head())

def save_weekly_summary(df):
    summary = df.groupby('Employee')['Hours'].sum().reset_index()
    summary = summary.sort_values('Hours', ascending=False)
    
    body = f"MMRI Weekly Clockify Summary - {datetime.today().strftime('%B %d, %Y')}\n\n"
    body += "Hours by Employee:\n"
    for _, row in summary.iterrows():
        body += f"  - {row['Employee']}: {row['Hours']:.1f} hours\n"
    
    body += "\nProject Breakdown:\n"
    project_summary = df.groupby(['Employee', 'Project'])['Hours'].sum().reset_index()
    for _, row in project_summary.iterrows():
        body += f"  - {row['Employee']} | {row['Project']}: {row['Hours']:.1f} hours\n"
    
    with open('weekly_summary.txt', 'w') as f:
        f.write(body)
    print("✅ Weekly summary saved to weekly_summary.txt!")

save_weekly_summary(df)