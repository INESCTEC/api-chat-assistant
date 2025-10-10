import os
import random
import json
from dotenv import load_dotenv
from rich import print
import google.generativeai as genai
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from llm_utils import ask_model
from documentation import OpenAPIDocumentation

# ========== CONFIG ========== #
load_dotenv()
genai.configure(api_key=os.getenv("GENAI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def get_model():
    return model

# ========== LOADERS ========== #
def load_question_templates(filepath):
    with open(filepath, "r") as file:
        return json.load(file)

# ========== HELPERS ========== #
def extract_methods_from_question(question_text):
    http_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
    return [word for word in question_text.split() if word in http_methods]

# ========== QUESTION GENERATOR ========== #
def generate_question_from_template(spec, template):
    category = template["type"]
    question_template = template["question"]

    required_methods = extract_methods_from_question(question_template)
    endpoints = spec.get_all_endpoints()
    valid_endpoints = [
        ep for ep in endpoints if all(m in spec.get_methods_for_endpoint(ep) for m in required_methods)
    ]
    if valid_endpoints:
        endpoint = random.choice(valid_endpoints)
    else:
        endpoint = random.choice(endpoints)

    methods = spec.get_methods_for_endpoint(endpoint) or ["GET"]
    parameters = spec.get_parameters_for_endpoint(endpoint)
    param_name = parameters[0]["name"] if parameters else "data"

    formatted_question = question_template.format(
        endpoint=endpoint,
        method=methods[0],
        parameter_name=param_name
    )

    return formatted_question, category

# ========== EVALUATOR ========== #
def evaluate_answer(model, context, question, proposed_answer):
    prompt = f"""
    Given the context, determine if the proposed answer is correct. 
    Respond in this JSON format:

    {{
      "answer": "correct" or "incorrect",
      "justification": "Brief explanation."
    }}

    Context: {context}
    Question: {question}
    Proposed Answer: {proposed_answer}
    """
    response = model.generate_content(prompt)
    cleaned = response.text.strip().split("\n", 1)[1].rsplit("\n", 1)[0]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"answer": "unknown", "justification": "Failed to parse response."}

# ========== PLOTTER ========== #
def plot_evaluation_results(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)

    category_data = defaultdict(list)
    for entry in data:
        category = entry.get('category', 'unknown')
        category_data[category].append(entry)

    categories = []
    eval_correct_pcts = []
    human_correct_pcts = []
    both_correct_pcts = []
    eval_correct_counts = []
    human_correct_counts = []
    both_correct_counts = []
    total_counts = []

    for category, entries in category_data.items():
        total = len(entries)
        eval_correct = sum(1 for e in entries if e['evaluation'].lower() == 'correct')
        human_correct = sum(1 for e in entries if e.get('human_evaluation', '').lower() == 'correct')
        both_correct = sum(1 for e in entries if e['evaluation'].lower() == 'correct' and e.get('human_evaluation', '').lower() == 'correct')

        categories.append(f"{category} (n={total})")
        eval_correct_pcts.append((eval_correct / total) * 100 if total > 0 else 0)
        human_correct_pcts.append((human_correct / total) * 100 if total > 0 else 0)
        both_correct_pcts.append((both_correct / total) * 100 if total > 0 else 0)
        eval_correct_counts.append(eval_correct)
        human_correct_counts.append(human_correct)
        both_correct_counts.append(both_correct)
        total_counts.append(total)

    x = np.arange(len(categories))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.barh(x - width, eval_correct_pcts, width, label='Model Evaluation', color='royalblue')
    bars2 = ax.barh(x, human_correct_pcts, width, label='Human Evaluation', color='seagreen')
    bars3 = ax.barh(x + width, both_correct_pcts, width, label='Both Correct', color='darkorange')

    ax.set_xlabel('Percentage Correct (%)')
    ax.set_xlim(0, 110)
    ax.set_yticks(x)
    ax.set_yticklabels(categories)
    ax.set_title('Evaluation Accuracy by Category')
    ax.legend()

    for i in range(len(categories)):
        ax.text(eval_correct_pcts[i] + 2, x[i] - width,
                f"{eval_correct_pcts[i]:.1f}% ({eval_correct_counts[i]})",
                va='center', fontsize=9, color='navy')
        ax.text(human_correct_pcts[i] + 2, x[i],
                f"{human_correct_pcts[i]:.1f}% ({human_correct_counts[i]})",
                va='center', fontsize=9, color='darkgreen')
        ax.text(both_correct_pcts[i] + 2, x[i] + width,
                f"{both_correct_pcts[i]:.1f}% ({both_correct_counts[i]})",
                va='center', fontsize=9, color='darkorange')

    plt.tight_layout()
    plt.savefig("Files/evaluation_plot.png")  # Save plot to a file

# ========== MAIN LOOP ========== #
def generate_and_evaluate_questions(question_templates, spec, model, output_file, verbose=False ):
    category_accuracy = {}
    evaluations = []

    total_questions = len(question_templates)
    total_questions = 10

    for i in range(total_questions):
        print(f"[bold blue]Processing question {i+1}/{total_questions}...[/]")

        template = question_templates[i]
        question, category = generate_question_from_template(spec, template)

        answer_str = ask_model(question, [], spec)
        answer = json.loads(answer_str).get("answer", "No answer provided")

        filters = {"method": None, "parameters": None, "method_description": None, "endpoint": None}
        context = spec.get_api_info() + "\n" + spec.get_documentation(filters)
        evaluation = evaluate_answer(model, context, question, answer)

        if verbose:
            print(f"[yellow]Q:[/] {question}")
            print(f"[green]A:[/] {answer}")
            print(f"[magenta]Evaluation:[/] {evaluation}")

        evaluations.append({
            "question": question,
            "category": category,
            "answer": answer,
            "evaluation": evaluation["answer"],
            "justification": evaluation["justification"]
        })

        if category not in category_accuracy:
            category_accuracy[category] = {"correct": 0, "total": 0}
        if evaluation["answer"] == "correct":
            category_accuracy[category]["correct"] += 1
        category_accuracy[category]["total"] += 1

    with open(output_file, "w") as f:
        json.dump(evaluations, f, indent=4)

    total = len(evaluations)
    correct = sum(1 for e in evaluations if e["evaluation"] == "correct")
    overall_accuracy = (correct / total) * 100 if total else 0

    category_accuracies = {
        cat: (acc["correct"] / acc["total"]) * 100
        for cat, acc in category_accuracy.items() if acc["total"] > 0
    }

    return overall_accuracy, category_accuracies

# ========== RUN ========== #
if __name__ == "__main__":
    FILE_PATH = "Files/Sentinel.json"
    QUESTIONS_FILE = "Files/questions.json"
    EVALUATION_FILE = "Files/evaluation.json"

    print("[bold green]Initializing...[/]")

    spec = OpenAPIDocumentation(FILE_PATH)
    question_templates = load_question_templates(QUESTIONS_FILE)
    model = get_model()

    acc, cat_acc = generate_and_evaluate_questions(
        question_templates,
        spec,
        model,
        EVALUATION_FILE,
        verbose=True,
    )

    print(f"[bold green]Overall Accuracy:[/] {acc:.2f}%")
    print(f"[bold cyan]Category Accuracies:[/] {cat_acc}")

    # Save evaluation results
    plot_evaluation_results(EVALUATION_FILE)