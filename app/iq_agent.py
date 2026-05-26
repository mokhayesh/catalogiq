import json
from openai import OpenAI

class IQDataStewardAgent:

    def __init__(self, api_key=None, model="gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

        self.system_prompt = """
You are “IQ Data Steward Agent,” a senior enterprise data governance architect.
Your responsibilities include:

- Metadata enrichment (friendly name, description, glossary mapping)
- PII detection and classification
- Data quality rule generation
- Regex pattern inference
- Policy recommendation (privacy, retention, access)
- Attestation creation
- Profiling interpretation
- Governance remediation recommendations
- Steward task automation

Your outputs MUST be:
- Accurate
- Business-friendly
- Non-hallucinated
- Compliant with GDPR/CCPA best practices
- Based only on the provided schema and examples

You ALWAYS return structured JSON in this exact format:

{
  "field": "",
  "friendly_name": "",
  "description": "",
  "classification": "",
  "pii_type": "",
  "policy": "",
  "attestation": "",
  "regex": "",
  "dq_rules": [],
  "notes": ""
}

If you do not know something, return an empty string.
Do not invent fictional business logic.
Do not guess values outside the provided context.
"""
    
    def analyze_field(self, field_name, example, dtype):
        """Process a single field."""
        user_prompt = f"""
Analyze this field and produce metadata.

Field Name: {field_name}
Example Value: {example}
Data Type: {dtype}

Return JSON ONLY.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        try:
            return json.loads(response.choices[0].message["content"])
        except:
            return {"error": "Invalid JSON returned."}

    def analyze_batch(self, fields):
        """
        fields = list of dicts:
        [
          {"field": "Email", "example": "john@example.com", "dtype": "object"},
          ...
        ]
        """
        batch_prompt = {
            "fields": fields
        }

        user_prompt = f"""
Analyze every field inside this dataset. For EACH field, return a JSON entry in an array.
Input Fields:
{json.dumps(batch_prompt, indent=2)}

Return ONLY a JSON array of field metadata objects.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        try:
            return json.loads(response.choices[0].message["content"])
        except:
            return {"error": "Invalid JSON"}
