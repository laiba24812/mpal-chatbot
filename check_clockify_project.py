import requests, os
from dotenv import load_dotenv
load_dotenv()
headers = {"X-Api-Key": os.getenv("CLOCKIFY_API_KEY")}
r = requests.get("https://api.clockify.me/api/v1/workspaces/5d31e75e59da6530a30fc2f1/projects/61797ccb28be343d87e40a48", headers=headers)
import json
print(json.dumps(r.json(), indent=2))