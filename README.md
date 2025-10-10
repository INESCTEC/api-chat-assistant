# API Assistant

**Description**:  This project is a conversational assistant that helps users interact with any RESTful API using natural language. It uses OpenAPI documentation to:
- Answer questions about the API  
- Generate example requests  
- Execute real API calls  
- Return results in a user-friendly format  

Designed to simplify API exploration and usage without writing code.


# Project Status

🚧 - This project is currently in **development**. Core functionalities are working, but improvements are ongoing.

# Technology Stack

**Language:**  
- Python  

**Frameworks & Libraries:**  
- **Streamlit** – interactive web interface  
- **Requests** – API communication  
- **Ollama** – local LLM interface and runtime  
- **OpenAI** – GPT model integration  
- **Google Generative AI** – text and response generation

## Dependencies

All required Python packages are listed in the [`requirements.txt`](./requirements.txt) file.

To install them, run:

```bash
pip install -r requirements.txt
```

## Installation

Follow these steps to set up and run the project:

1. **Clone the repository**

   ```bash
   git clone https://github.com/INESCTEC/api-chat-assistant.git
   cd api-chat-assistant
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install Ollama and pull the models**
  Download and install Ollama from https://ollama.com/download
  Pull the default model used by this project:
   ```bash
   ollama pull llama3.1:8b-instruct-q8_0
   ```

5. **Set up your environment variables**  
   Create a `.env` file (or rename .env.example to .env) with the following variables:

   ```env
   # API keys
   GENAI_API_KEY=         # Required for evaluation (always needed) 
   OPENAI_API_KEY=        # Required only if LLM_PROVIDER="openai"

   # LLM provider configuration
   LLM_PROVIDER="ollama"  # Options: "gemini", "ollama", or "openai"
                          # - "gemini": Gemini is used for both assistant + evaluation
                          # - "ollama" or "openai": Gemini is still used for evaluation

   # API access (for the external API defined in the OpenAPI documentation)
   API_TOKEN=             # Leave empty if no authentication is required
   AUTH_SCHEME="Token"    # Options: "Token", "Bearer", "X-API-Key", or "none"

   # OpenAPI documentation file
   DOCUMENTATION_FILE="documentation"  
                         # Name of the JSON documentation file (without .json extension) located inside ./Files directory (defaults to "documentation")

## Usage

To run the software, use the following command:

```sh
streamlit run app.py
```
Then open the URL shown in the terminal in your browser to use the app.

## Project Organization

The repository is structured as follows:

```sh
request_chat_llm/
|
├── app.py                    # Main entry point of the application
├── core.py                   # Core chat logic and model tools
├── documentation.py          # OpenAPI specification parsing and restructuring
├── evaluation.py             # Response evaluation utilities
├── llm_utils.py              # LLM interaction utilities (prompting, inferencing, error handling)
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── LICENSE.md                # Project license information
├── Files/                    # Stores documentation, evaluation data, and generated files
│   ├── documentation.json    # Placeholder OpenAPI specification
│   ├── questions.json        # Stored user questions or test prompts
```

## Known issues

Large API documentations may impact performance significantly, as processing them requires powerful GPUs and substantial memory. 

To address this, it is possible to use open-source models on less powerful machines. However, this project has been primarily tested and optimized for the default Ollama model (`llama3.1:8b-instruct-q8_0`). 

Using alternative models may lead to reduced feature reliability and performance, as full compatibility is not guaranteed.

## Open source licensing info

See [LICENSE.md](LICENSE.md) for details on usage rights and licensing.


### Contacts

* Alexandre Marques: alexandre.s.marques@inesctec.pt
* Carlos Silva: carlos.silva@inesctec.pt
* Ricardo Bessa: ricardo.j.bessa@inesctec.pt