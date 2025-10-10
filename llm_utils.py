import os
import json
from typing import List, Dict, Optional
from documentation import OpenAPIDocumentation

# LLM clients
import ollama
import google.generativeai as genai
import openai

# === API Keys ===
genai.configure(api_key=os.getenv("GENAI_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")

# === Constants ===
GEMINI_MODEL = "gemini-1.5-flash"
OPENAI_MODEL = "gpt-4o"
OLLAMA_MODEL = 'llama3.1:8b-instruct-q8_0'

# === Model Switch ===
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "gemini", "ollama", or "openai"

def ask_model(question: str, chat_history: List[Dict], spec: Optional[OpenAPIDocumentation]) -> str:
    """Send the question to the chosen LLM with history and spec prompts."""
    documentation_prompt = get_documentation_prompt(spec)
    messages = [documentation_prompt, strict_system_rules] + chat_history + [{"role": "user", "content": question}]

    try:
        if LLM_PROVIDER == "gemini":
            full_prompt = "\n\n".join(m["content"] for m in messages if "content" in m)
            response = genai.GenerativeModel(GEMINI_MODEL).generate_content(full_prompt)
            return response.text.strip()

        elif LLM_PROVIDER == "ollama":
            response = ollama.chat(
                model=OLLAMA_MODEL,
                keep_alive=True,
                messages=messages,
                options={'temperature': 0.3, "seed": 4, "num_ctx": 30000},
                format='json'
            )
            return response.message.content.strip()

        elif LLM_PROVIDER == "openai":
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message['content'].strip()

        else:
            raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    except Exception as e:
        return json.dumps({
            "answer": "An internal error occurred, try again later.",
            "endpoint": "",
            "method": "",
            "params": {},
            "ready": False
        })

def handle_bootstrap_mode(user_input: str) -> str:
    """Use LLM to extract an OpenAPI URL and load the spec."""
    try:
        messages = [bootstrap_prompt, {"role": "user", "content": user_input}]

        if LLM_PROVIDER == "gemini":
            flattened_prompt = "\n\n".join([msg["content"] for msg in messages if "content" in msg])
            response = genai.GenerativeModel(GEMINI_MODEL).generate_content(flattened_prompt)
            content = response.text.strip()


        elif LLM_PROVIDER == "ollama":
            response = ollama.chat(
                model=OLLAMA_MODEL,
                keep_alive=True,
                messages=messages,
                options={'temperature': 0.3, "seed": 4, "num_ctx": 30000},
                format='json'
            )
            content = response.message.content.strip()

        elif LLM_PROVIDER == "openai":
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=0.3
            )
            choice = response.choices[0]
            content = (
                choice.message['content'].strip()
                if isinstance(choice.message, dict)
                else choice.message.content.strip()
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")
        
        if content.startswith("```"):
            content = content.strip().lstrip("`json").rstrip("`").strip()

        # Parse and extract URL
        response_data = json.loads(content)
        url = response_data.get("url", "")

        if url:
            from REQUEST_CHAT.core import fetch_and_save_openapi_spec, set_spec  # Avoid circular imports
            filepath, error = fetch_and_save_openapi_spec(url)

            if error:
                return json.dumps({
                    "answer": f"❌ Failed to load the OpenAPI documentation from the provided URL.\n\nDetails: {error}",
                    "endpoint": "",
                    "method": "",
                    "params": {},
                    "ready": False,
                    "url": url
                })

            set_spec(OpenAPIDocumentation(filepath))

            return json.dumps({
                "answer": f"✅ OpenAPI documentation loaded from {url}. You may now ask about the API.",
                "endpoint": "",
                "method": "",
                "params": {},
                "ready": False,
                "url": url
            })

        return json.dumps(response_data)

    except Exception as e:
        return json.dumps({
            "answer": f"❌ Internal error while handling your request.\n\nError: {str(e)}",
            "endpoint": "",
            "method": "",
            "params": {},
            "ready": False,
            "url": ""
        })


def get_documentation_prompt(spec):
    filters = {"method": None, "parameters": None, "method_description": None, "endpoint": None}
    doc_string = spec.get_api_info() + "\n" + spec.get_documentation(filters)
    return {
        "role": "system",
        "content": (
            "You are a helpful assistant specializing in answering API questions, code generation, and API request execution.\n\n"
            f"Here is the API documentation you MUST use to answer user questions:\n\n"
            f"{doc_string}\n\n"
            "Always respond ONLY with a valid JSON object containing these fields: answer, endpoint, method, parameters, ready."
        )
    }


strict_system_rules = {
    "role": "system",
    "content": """You are a helpful assistant that specializes in answering questions about API documentation, code generation, and API request execution.
You must always return a JSON object with:
- "answer": A **complete** and **self-contained** string response that does not depend on other fields. This is the **only feedback** the user receives, so it must include everything needed, including endpoint names of asked. You must always provide a response to the user even if you are just chatting about the API or greeting them.
- "endpoint": The identified API endpoint only if the user asked for the request for one, or an empty string.
- "method": The HTTP method (GET, POST, etc.), of the respective endpoint, or an empty string.
- "parameters": A dictionary of query parameters the user provided for the requested parameter.
- "ready": A flag indicating if the request is ready to be executed and the user specificaly asked for you to make a request. Set to True if all required parameters are filled in and if the user asked to make a request, otherwise False.

Behaviors:
- Answer API questions with complete explanations in writting to assist the user the best you can, dont just present the documentation.
- If you are asked to generate code, you must provide full Python code requests in the "answers" key with the "Authorization: Token" placeholder in the header, and parameter placeholders when the user did not provide the real ones.
- The parameters in the code must not be added into the endpoint URL, but rather in the payload or params dictionary. The code must be formatted as a Python script with the requests library.
- Do not ask questions to the user if he asked for code generation, just provide the code with the placeholders.
- Assist with API request execution by by asking about the parameter values and endpoint if not provided.
- When the user asks for a request you must make sure to ask for all the required parameters if they exist and endpoint, and then set the "ready" flag to True if all required parameters are provided. If no parameters are necessary, set "ready" to True immediately if the user asked for a request for a given endpoint.
- When the flag is activated the request will be sent to the API so your actions and compliance matter, you are not just pretending to send the request, it will really happen. In this case you must formally inform the user that the request will be sent and that they will receive the API's response in the chat.
- Only use the description of the endpoints to know what they do, do not ask the user for something written in the description if there are no parameters about it. You should not worry about the security of the parameters, just ask for them.
- Do not generate code when the user asks for a request nor when you are executing one, the code is exclusive to when the user asks for it.

Respond in JSON format only. Your answer must always be valid JSON with all required keys."""
}

bootstrap_prompt = {
    "role": "system",
    "content": (
        "You are a helpful assistant that specializes in answering questions about API documentation, code generation, and API request execution.\n"
        "The OpenAPI documentation is missing.\n"
        "Ask the user for the URL to a JSON or YAML OpenAPI specification.\n\n"
        "Respond ONLY using this strict JSON format:\n"
        "{\n"
        '  "answer": "your full message to the user",\n'
        '  "endpoint": "",\n'
        '  "method": "",\n'
        '  "params": {},\n'
        '  "ready": false,\n'
        '  "url": "include the user-provided URL if available, otherwise empty"\n'
        "}\n\n"
        "Do not include any other text. Always clearly ask the user to provide the OpenAPI spec URL."
    )
}