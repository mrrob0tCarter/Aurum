import flet as ft
import httpx

API_URL = "http://localhost:8000"


def main(page: ft.Page):
    page.title = "Aurum"
    page.window_width = 500
    page.window_height = 400

    def on_search(e):
        username = user_input.value.strip()
        if not username:
            output.value = "Type a GitHub username first."
            page.update()
            return

        try:
            response = httpx.get(f"{API_URL}/github/{username}", timeout=10)
            data = response.json()

            if "error" in data:
                output.value = f"Error: {data['error']}"
            else:
                output.value = (
                    f"Username: {data['username']}\n"
                    f"Name: {data['name'] or 'n/a'}\n"
                    f"Bio: {data['bio'] or 'n/a'}\n"
                    f"Public repos: {data['public_repos']}\n"
                    f"Followers: {data['followers']}"
                )
        except Exception as err:
            output.value = f"Could not reach backend: {err}"

        page.update()

    user_input = ft.TextField(label="GitHub username", on_submit=on_search)
    button = ft.Button("Search", on_click=on_search)
    output = ft.Text(size=14)

    page.add(user_input, button, output)


ft.run(main)