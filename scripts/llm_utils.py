"""
llm_utils.py

Helper functions for using large language models (LLMs) to infer
standardized dependent variable names from raw column labels.
Designed for experimentation with GPT-based models in the DV Standardization Tool.
"""

import openai
import os

# Load your OpenAI API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")


def infer_dv_name(raw_column_name, context=None, model="gpt-4", temperature=0.2):
    """
    Infer a standardized DV name using an LLM.

    Args:
        raw_column_name (str): Column name from a dataset.
        context (str, optional): Additional description or usage context.
        model (str): OpenAI model to use.
        temperature (float): Sampling temperature for the generation.

    Returns:
        str: Suggested standardized DV name.
    """
    prompt = f"""
You are an HCI research assistant helping standardize dataset variable names.
Given the raw column name "{raw_column_name}", suggest a canonical dependent variable (DV) name.
{f"Context: {context}" if context else ""}
Return only the standardized name.
"""

    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=20
    )

    return response['choices'][0]['message']['content'].strip()
