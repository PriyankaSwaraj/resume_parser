import ollama
import json
from collections import OrderedDict


def ats_extractor(resume_data):

    prompt = """
You are an ATS Resume Parser.

Extract resume information.

Rules:
- Return ONLY valid JSON
- Preserve EXACT order of fields
- Missing text → null
- Missing sections → []
- Extract FULL URLs
- Do not invent values
- Keep original wording

Output format:

{
    "name": "",

    "links": {
        "linkedin": "",
        "github": "",
        "portfolio": ""
    },

    "education": [
        {
            "degree": "",
            "specialization": "",
            "college": "",
            "cpi": null
        }
    ],

    "experience": [
        {
            "company": "",
            "role": "",
            "duration": ""
        }
    ],

    "projects": [
        {
            "project_name": "",
            "technologies": []
        }
    ],

    "certifications": [],

    "achievements": []
}
"""

    try:

        response = ollama.chat(
            model="llama3.1",
            format="json",
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": resume_data
                }
            ]
        )

        result = json.loads(
            response["message"]["content"]
        )

        ordered = OrderedDict([
            ("name", result.get("name")),

            ("links", result.get("links", {})),

            ("education",
             result.get("education", [])),

            ("experience",
             result.get("experience", [])),

            ("projects",
             result.get("projects", [])),

            ("certifications",
             result.get("certifications", [])),

            ("achievements",
             result.get("achievements", []))
        ])

        return ordered

    except Exception as e:

        return {
            "error": str(e)
        }