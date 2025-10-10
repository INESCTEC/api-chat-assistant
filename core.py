import json
import yaml
import os
import requests
from dotenv import load_dotenv
from documentation import OpenAPIDocumentation
from llm_utils import ask_model, handle_bootstrap_mode

# ============ CONFIG ============
# Load environment variables
load_dotenv()

# Set working directory to script location
default_repo_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(default_repo_path)

# File paths
FILES_DIR = 'Files'
doc_name = os.getenv("DOCUMENTATION_FILE", "documentation") # default to "documentation"
FILE_PATH = os.path.join(FILES_DIR, f"{doc_name}.json")
CHAT_HISTORY_FILE = os.path.join(FILES_DIR, 'chat_history.json')
REQUEST_OUTPUT_FILE = os.path.join(FILES_DIR, 'request.json')

# Ensure required directories exist
os.makedirs(FILES_DIR, exist_ok=True)

# Load API token from .env
API_TOKEN = os.getenv("API_TOKEN")

AUTH_SCHEME = os.getenv("AUTH_SCHEME", "Token")  # default to "Token"

spec = None

# ============ UTILITIES ============
def set_spec(new_spec: OpenAPIDocumentation):
    global spec
    spec = new_spec

def get_spec():
    return spec

# Load OpenAPI spec if available
if os.path.exists(FILE_PATH):
    set_spec(OpenAPIDocumentation(FILE_PATH))

def load_chat_history():
    try:
        with open(CHAT_HISTORY_FILE, "r") as f:
            history = json.load(f)
            return history[-20:]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def store_chat_history(chat_history):
    with open(CHAT_HISTORY_FILE, "w") as file:
        json.dump(chat_history, file, indent=4)

def fetch_and_save_openapi_spec(url, filename="openapi_spec.json", folder="Files"):
    """Fetches an OpenAPI spec from a URL and saves it to disk.
    Returns (filepath, None) on success or (None, error_message) on failure.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")

        if 'application/json' in content_type or url.endswith('.json'):
            spec = response.json()
        elif 'application/yaml' in content_type or 'text/yaml' in content_type or url.endswith(('.yaml', '.yml')):
            spec = yaml.safe_load(response.text)
        else:
            return None, f"Unsupported content type: {content_type}"
        
        # Ensure the folder exists
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        
        # Save the spec to a file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(spec, f, indent=2)

        return filepath, None

    except requests.exceptions.RequestException as req_err:
        return None, f"Network error: {req_err}"
    except (json.JSONDecodeError, yaml.YAMLError, ValueError) as parse_err:
        return None, f"Parsing error: {parse_err}"
    except OSError as file_err:
        return None, f"File error while saving spec: {file_err}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

def make_api_request(endpoint, payload, method):
    """Executes the API request and handles responses."""
    url = spec.get_host() + endpoint

    headers = {}
    if AUTH_SCHEME.lower() != "none" and API_TOKEN:
        if AUTH_SCHEME.lower() in ["token", "bearer"]:
            headers["Authorization"] = f"{AUTH_SCHEME} {API_TOKEN}"
        else:
            headers[AUTH_SCHEME] = API_TOKEN

    methods = {
        "GET": requests.get,
        "POST": requests.post,
        "PUT": requests.put,
        "PATCH": requests.patch,
        "DELETE": requests.delete
    }

    try:
        response = methods[method](
            url,
            headers=headers,
            params=payload if method in ["GET", "DELETE"] else None,
            data=payload.get("data") if method in ["POST", "PUT", "PATCH"] else None
        )

        if response.status_code == 200:
            with open(REQUEST_OUTPUT_FILE, 'w') as file:
                json.dump(response.json(), file, indent=4)
            return f"✅ Success! The {method} request to '{url}' completed without issues.", REQUEST_OUTPUT_FILE

        elif response.status_code >= 500:
            return (
                f"🚨 Oops! Something went wrong on the server (Error {response.status_code}). "
                f"This isn't your fault — please try again in a few minutes.", None
            )

        else:
            return (
                f"⚠️ The request didn't go through (Error {response.status_code}). "
                f"This might be due to missing or incorrect data. Please double-check and try again.\n\n"
                f"Details: {response.text}", None
            )

    except Exception as e:
        return (
            f"❌ An unexpected error occurred while trying to send the request. "
            f"Please try again.\n\nError: {str(e)}", None
        )

# ============ MAIN CHAT LOOP ============

def get_answer(user_input):
    spec = get_spec()

    if spec is None:
        return handle_bootstrap_mode(user_input)

    # If spec is loaded, continue as normal
    chat_history = load_chat_history()
    answer_str = ask_model(user_input, chat_history, spec)

    chat_history.append({"role": "user", "content": user_input})
    chat_history.append({"role": "assistant", "content": answer_str})
    store_chat_history(chat_history)

    return answer_str