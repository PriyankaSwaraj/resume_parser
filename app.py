import os
from flask import Flask
from flask import request
from flask import render_template

from pypdf import PdfReader
from resumeparser import ats_extractor

UPLOAD_PATH = "__DATA__"

os.makedirs(
    UPLOAD_PATH,
    exist_ok=True
)

app = Flask(__name__)


@app.route("/")
def index():

    return render_template(
        "index.html"
    )

@app.route("/process", methods=["POST"])
def process():

    doc = request.files["pdf_doc"]

    filepath = os.path.join(
        UPLOAD_PATH,
        "resume.pdf"
    )

    doc.save(filepath)

    text = read_pdf(
    filepath
)

    parsed = ats_extractor(
        text
    )

    ordered_sections = [
        ("Name", parsed.get("name")),

        ("Education",
         parsed.get("education", [])),

        ("Experience",
         parsed.get("experience", [])),

        ("Projects",
         parsed.get("projects", [])),

        ("Certifications",
         parsed.get("certifications", [])),

        ("Achievements",
         parsed.get("achievements", [])),

        ("Links",
         parsed.get("links", {}))
    ]
    return render_template(
    "index.html",
    data=parsed,
    sections=ordered_sections
)

def read_pdf(path):

    reader = PdfReader(path)

    text = ""

    extracted_links = []

    for page in reader.pages:

        # Extract normal text
        content = page.extract_text()

        if content:
            text += content + "\n"

        # Extract clickable links
        annots = page.get("/Annots")

        if annots:

            for annot in annots:

                obj = annot.get_object()

                action = obj.get("/A")

                if action and "/URI" in action:

                    extracted_links.append(
                        action["/URI"]
                    )

    extracted_links = list(
        set(extracted_links)
    )

    if extracted_links:

        text += "\n\nLinks:\n"

        for link in extracted_links:

            text += link + "\n"

    return text


if __name__ == "__main__":

    app.run(
        debug=True,
        port=8000
    )