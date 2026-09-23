from fastapi import FastAPI
import httpx

app = FastAPI(title="Aurum API")


@app.get("/")
def root():
    return {"app": "Aurum", "status": "running"}


@app.get("/hello")
def hello():
    return {"message": "Hello from Aurum backend"}


@app.get("/github/{username}")
def github_user(username: str):
    """Fetch public info about a GitHub user."""
    url = f"https://api.github.com/users/{username}"
    response = httpx.get(url, timeout=10)

    if response.status_code != 200:
        return {"error": f"GitHub returned {response.status_code}"}

    data = response.json()
    return {
        "username": data["login"],
        "name": data.get("name"),
        "bio": data.get("bio"),
        "public_repos": data["public_repos"],
        "followers": data["followers"],
        "avatar": data["avatar_url"],
    }