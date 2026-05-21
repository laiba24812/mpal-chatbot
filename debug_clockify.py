import requests
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("CLOCKIFY_API_KEY")
WORKSPACE_ID = "5d31e75e59da6530a30fc2f1"
headers = {"X-Api-Key": API_KEY}

# Get all users with pagination
users = []
page = 1
while True:
    response = requests.get(
        f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/users",
        headers=headers,
        params={"page": page, "page-size": 50}
    )
    page_users = response.json()
    if not page_users:
        break
    users.extend(page_users)
    page += 1

# Find Laiba and print her entries
for user in users:
    if user['name'] == 'Laiba Yousafzai':
        print("Found Laiba! ID:", user['id'])
        entries = requests.get(
            f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/user/{user['id']}/time-entries",
            headers=headers
        ).json()
        for e in entries[:5]:
            print('Project ID:', e.get('projectId'))
            print('Description:', e.get('description'))
            print()
        
        print("Projects dict sample:")
        projects_r = requests.get(
            f"https://api.clockify.me/api/v1/workspaces/{WORKSPACE_ID}/projects/61797ccb28be343d87e40a48",
            headers=headers
        )
        print(projects_r.json()['name'])
        break