import os
from azure.identity import DefaultAzureCredential
from azure.ai.evaluation import evaluate, GroundednessEvaluator, RelevanceEvaluator, CoherenceEvaluator, FluencyEvaluator, SimilarityEvaluator, F1ScoreEvaluator
from custom_eval._helpfulness import HelpfulnessEvaluator
from response import generate_answer
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import json

credential = DefaultAzureCredential()

# Load environment variables
def load_environment_variables():
    load_dotenv()
    azure_ai_project = {
        "subscription_id": os.environ.get("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.environ.get("AZURE_RESOURCE_GROUP"),
        "project_name": os.environ.get("AZURE_PROJECT_NAME"),
    }
    model_config = {
        "azure_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
        "azure_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION"),
    }
    return azure_ai_project, model_config

# Initialzing evaluators
"""
Groundedness:   measures how well the generated response aligns with the given context in a retrieval-augmented generation scenario, focusing on its relevance and accuracy with respect to the context.
Relevance:      measures how effectively a response addresses a query. It assesses the accuracy, completeness, and direct relevance of the response based solely on the given query
Coherence:      measures the logical and orderly presentation of ideas in a response, allowing the reader to easily follow and understand the writer's train of thought. 
Fluency:        measures the effectiveness and clarity of written communication, focusing on grammatical accuracy, vocabulary range, sentence complexity, coherence, and overall readability.
Similarity:     measures the degrees of similarity between the generated text and its ground truth with respect to a query.
F1 Score:       measures the similarity by shared tokens between the generated text and the ground truth, focusing on both precision and recall.
Helpfulness:    measures how well the generated response helps the user in addressing their query.
"""
def initialize_evaluators(model_config):
    groundedness_eval = GroundednessEvaluator(model_config)
    relevance_eval = RelevanceEvaluator(model_config)
    coherence_eval = CoherenceEvaluator(model_config)
    fluency_eval = FluencyEvaluator(model_config)
    similarity_eval = SimilarityEvaluator(model_config)
    f1score_eval = F1ScoreEvaluator()
    helpfulness_eval = HelpfulnessEvaluator(model_config)
    return {
        "groundedness": groundedness_eval,
        "relevance": relevance_eval,
        "coherence": coherence_eval,
        "fluency": fluency_eval,
        "similarity": similarity_eval,
        "f1score": f1score_eval,
        "helpfulness": helpfulness_eval
    }

# Convert a CSV file to a JSONL file
def csv_to_jsonl(csv_file_path, jsonl_file_path):
    df = pd.read_csv(csv_file_path)
    df = df.fillna('')
    if 'response' in df.columns:
        df = df.drop(columns=['response'])
    with open(jsonl_file_path, 'w') as jsonl_file:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            json_str = json.dumps(row_dict)
            jsonl_file.write(json_str + '\n')

if __name__ == '__main__':

    azure_ai_project, model_config = load_environment_variables()
    evaluators = initialize_evaluators(model_config)
    
    # Convert CSV to JSONL
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(current_dir, 'dataset', 'dataset.csv')
    jsonl_file_path = os.path.join(current_dir, 'dataset', 'dataset.jsonl')
    csv_to_jsonl(csv_file_path, jsonl_file_path)

    # Define the models to be evaluated
    models = ["gpt-4", "gpt-4o"]
    
    for model in models:

        evaluation_name = f"{model}_"+datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        """
        Query: the query sent in to the generative AI application
        Response: the response to the query generated by the generative AI application
        Context: the source on which generated response is based (that is, the grounding documents)
        Ground truth: the response generated by user/human as the true answer
        Conversation: a list of messages of user and assistant turns. See more in the next section.
        """
        result = evaluate(
            evaluation_name=evaluation_name,
            data=jsonl_file_path, # provide your data here
            target=generate_answer(**model_config, model=model),
            evaluators=evaluators,
            # column mapping
            evaluator_config={
                "groundedness": {
                    "column_mapping": {
                        "query": "${data.query}",
                        "context": "${data.user_instructions}"+"\n"+"${data.context}",
                        "response": "${target.response}"
                    } 
                },
                "relevance": {
                    "column_mapping": {
                        "query": "${data.query}",
                        "response": "${target.response}"
                    } 
                },
                "coherence": {
                    "column_mapping": {
                        "query": "${data.query}",
                        "response": "${target.response}"
                    } 
                },
                "fluency": {
                    "column_mapping": {
                        "response": "${target.response}"
                    } 
                },
                "similarity": {
                    "column_mapping": {
                        "query": "${data.query}",
                        "response": "${target.response}",
                        "ground_truth": "${data.ground_truth}"
                    } 
                },
                "f1score": {
                    "column_mapping": {
                        "response": "${target.response}",
                        "ground_truth": "${data.ground_truth}"
                    } 
                },
                "helpfulness": {
                    "column_mapping": {
                        "query": "${data.query}",
                        "context": "${data.user_instructions}"+"\n"+"${data.context}",
                        "response": "${target.response}"
                    } 
                }
                # Add other evaluator configurations here if needed
            },
            # Optionally provide your Azure AI project information to track your evaluation results in your Azure AI project
            azure_ai_project=azure_ai_project,
            # Optionally provide an output path to dump a json of metric summary, row level data and metric and Azure AI project URL
            output_path = os.path.join(current_dir, f"results_{evaluation_name}.json")
        )