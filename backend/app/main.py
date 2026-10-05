from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import sqlite3, json, uuid, datetime, re, csv, io, os, requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
UP = DATA / "uploads"
UP.mkdir(parents=True, exist_ok=True)
DB = DATA / "calvad.db"
app = FastAPI(title="Calvad API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = db()
    c.executescript("""
 CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,question TEXT,created TEXT,status TEXT DEFAULT 'draft');
 CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,path TEXT,pages INTEGER,text_json TEXT);
 CREATE TABLE IF NOT EXISTS fields(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,type TEXT,position INTEGER);
 CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,project_id TEXT,document_id TEXT,field_id TEXT,value TEXT,evidence TEXT,page INTEGER,verified INTEGER,status TEXT,reason TEXT,model TEXT);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,ts TEXT,event TEXT,details TEXT);
 CREATE TABLE IF NOT EXISTS syntheses(project_id TEXT PRIMARY KEY,text TEXT,created TEXT,model TEXT);
 """)
    c.commit()
    c.close()

def ensure_evidence_validation_columns():
    c = db()

    columns = {
        row["name"]
        for row in c.execute(
            "PRAGMA table_info(evidence)"
        ).fetchall()
    }

    if "source_matched" not in columns:
        c.execute(
            "ALTER TABLE evidence "
            "ADD COLUMN source_matched INTEGER DEFAULT 0"
        )

    if "validated" not in columns:
        c.execute(
            "ALTER TABLE evidence "
            "ADD COLUMN validated INTEGER DEFAULT 0"
        )

    if "validation_reason" not in columns:
        c.execute(
            "ALTER TABLE evidence "
            "ADD COLUMN validation_reason TEXT"
        )

    c.commit()
    c.close()

init()

ensure_evidence_validation_columns()

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def audit(pid, event, details=""):
    c = db()
    c.execute(
        "INSERT INTO audit(project_id,ts,event,details) VALUES(?,?,?,?)",
        (pid, now(), event, details),
    )
    c.commit()
    c.close()


def ollama(prompt, model="qwen2.5:7b", json_mode=False, schema=None):
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0
            }
        }

        if schema is not None:
            payload["format"] = schema
        elif json_mode:
            payload["format"] = "json"

        r = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=300
        )

        r.raise_for_status()
        return r.json()["response"]

    except requests.exceptions.Timeout:
        raise HTTPException(
            503,
            f"Ollama timed out while running {model}."
        )

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            503,
            f"Ollama unavailable: {e}"
        )

EXTRACTION_SCHEMA = {
"type": "object",
"properties": {
    "found": {
        "type": "boolean"
    },
    "value": {
        "type": ["string", "number", "null"]
    },
    "evidence": {
        "type": ["string", "null"]
    }
},
"required": [
    "found",
    "value",
    "evidence"
],
"additionalProperties": False
}

class ProjectIn(BaseModel):
    name: str
    question: str


class FieldsIn(BaseModel):
    fields: list[dict]


class RunIn(BaseModel):
    model: str = "qwen2.5:7b"

class ReviewIn(BaseModel):
    action: str
    value: str | None = None
    reason: str | None = None


@app.get("/health")
def health():
    ok = False
    try:
        ok = requests.get("http://localhost:11434/api/tags", timeout=1).ok
    except:
        pass
    return {"ok": True, "ollama": ok}


@app.get("/projects")
def projects():
    c = db()
    rows = [dict(r) for r in c.execute("SELECT * FROM projects ORDER BY created DESC")]
    for r in rows:
        r["documents"] = c.execute(
            "SELECT count(*) FROM documents WHERE project_id=?", (r["id"],)
        ).fetchone()[0]
        r["validated"] = c.execute(
            """
            SELECT count(*)
            FROM evidence
            WHERE project_id=?
            AND source_matched=1
            AND validated=1
            """,
            (r["id"],),
        ).fetchone()[0]
    c.close()
    return rows


@app.post("/projects")
def create_project(p: ProjectIn):
    pid = str(uuid.uuid4())
    c = db()
    c.execute(
        "INSERT INTO projects(id,name,question,created) VALUES(?,?,?,?)",
        (pid, p.name, p.question, now()),
    )
    c.commit()
    c.close()
    audit(pid, "Project created", p.question)
    return {"id": pid}

@app.delete('/projects/{pid}')
def delete_project(pid):
 c=db()

 project=c.execute(
  'SELECT * FROM projects WHERE id=?',
  (pid,)
 ).fetchone()

 if not project:
  c.close()
  raise HTTPException(404,'Project not found')

 documents=c.execute(
  'SELECT path FROM documents WHERE project_id=?',
  (pid,)
 ).fetchall()

 # Remove database records belonging to the project.
 c.execute('DELETE FROM evidence WHERE project_id=?',(pid,))
 c.execute('DELETE FROM fields WHERE project_id=?',(pid,))
 c.execute('DELETE FROM syntheses WHERE project_id=?',(pid,))
 c.execute('DELETE FROM audit WHERE project_id=?',(pid,))
 c.execute('DELETE FROM documents WHERE project_id=?',(pid,))
 c.execute('DELETE FROM projects WHERE id=?',(pid,))

 c.commit()
 c.close()

 # Remove uploaded PDF files from disk.
 for document in documents:
  try:
   path=Path(document['path'])
   if path.exists():
    path.unlink()
  except Exception:
   # A missing/unremovable file should not prevent database deletion.
   pass

 # Remove generated exports if they exist.
 for suffix in ['-evidence.csv','-evidence.json']:
  export_path=DATA/f'{pid}{suffix}'
  try:
   if export_path.exists():
    export_path.unlink()
  except Exception:
   pass

 return {'ok':True}

@app.get("/projects/{pid}")
def project(pid):
    c = db()
    p = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not p:
        raise HTTPException(404, "Project not found")
    out = dict(p)
    out["documents"] = [
        dict(x)
        for x in c.execute(
            "SELECT id,name,pages FROM documents WHERE project_id=?", (pid,)
        )
    ]
    out["fields"] = [
        dict(x)
        for x in c.execute(
            "SELECT id,name,type,position FROM fields WHERE project_id=? ORDER BY position",
            (pid,),
        )
    ]
    c.close()
    return out


@app.post("/projects/{pid}/documents")
async def upload(pid, files: list[UploadFile] = File(...)):
    c = db()
    added = []
    for f in files:
        did = str(uuid.uuid4())
        path = UP / f"{did}.pdf"
        path.write_bytes(await f.read())
        reader = PdfReader(str(path))
        pages = []
        for i, p in enumerate(reader.pages):
            pages.append({"page": i + 1, "text": p.extract_text() or ""})
        c.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?)",
            (did, pid, f.filename, str(path), len(pages), json.dumps(pages)),
        )
        added.append({"id": did, "name": f.filename, "pages": len(pages)})
    c.commit()
    c.close()
    audit(pid, "Documents parsed", f"{len(added)} PDF(s) added with page mapping")
    return added

@app.delete('/projects/{pid}/documents/{did}')
def delete_document(pid,did):
 c=db()

 document=c.execute(
  'SELECT * FROM documents WHERE id=? AND project_id=?',
  (did,pid)
 ).fetchone()

 if not document:
  c.close()
  raise HTTPException(404,'Document not found')

 # Evidence derived from this document is no longer valid.
 c.execute(
  'DELETE FROM evidence WHERE document_id=? AND project_id=?',
  (did,pid)
 )

 # Any previous synthesis may contain evidence from this document,
 # so invalidate it.
 c.execute(
  'DELETE FROM syntheses WHERE project_id=?',
  (pid,)
 )

 c.execute(
  'DELETE FROM documents WHERE id=? AND project_id=?',
  (did,pid)
 )

 c.commit()
 c.close()

 # Remove the actual uploaded PDF.
 try:
  path=Path(document['path'])
  if path.exists():
   path.unlink()
 except Exception:
  pass

 audit(
  pid,
  'Document removed',
  f"{document['name']} removed; derived evidence and synthesis invalidated"
 )

 return {'ok':True}

@app.post("/projects/{pid}/plan/generate")
def generate_plan(pid, body: RunIn):
    c = db()
    p = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    c.close()
    prompt = f"""You design evidence extraction schemas for research literature. Research question: {p['question']}\nReturn JSON only: {{"fields":[{{"name":"Study design","type":"categorical"}}]}}. Propose 6-9 concise fields. Include Study design and Sample size when relevant."""
    raw = ollama(prompt, body.model, True)
    try:
        fields = json.loads(raw)["fields"]
    except:
        fields = [
            {"name": "Study design", "type": "categorical"},
            {"name": "Sample size (N)", "type": "numeric"},
            {"name": "Population", "type": "text"},
            {"name": "Intervention", "type": "text"},
            {"name": "Comparator", "type": "text"},
            {"name": "Follow-up", "type": "text"},
            {"name": "Primary outcome", "type": "text"},
            {"name": "Main result", "type": "text"},
        ]
    audit(pid, "Extraction plan generated", f"Model: {body.model}")
    return {"fields": fields}


@app.put("/projects/{pid}/plan")
def save_plan(pid, b: FieldsIn):
    c = db()
    c.execute("DELETE FROM fields WHERE project_id=?", (pid,))
    for i, f in enumerate(b.fields):
        c.execute(
            "INSERT INTO fields VALUES(?,?,?,?,?)",
            (str(uuid.uuid4()), pid, f["name"], f.get("type", "text"), i),
        )
    c.execute("UPDATE projects SET status='planned' WHERE id=?", (pid,))
    c.commit()
    c.close()
    audit(pid, "Extraction plan approved", f"{len(b.fields)} fields")
    return {"ok": True}


def normalize_source_text(text):
    text = text.lower()

    # Normalize all whitespace.
    text = re.sub(r"\s+", " ", text)

    # PDF extraction and LLM quotations often disagree about
    # spaces immediately around punctuation.
    text = re.sub(r"\s*([:;,])\s*", r"\1", text)

    # Normalize spaces around parentheses.
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)

    return text.strip()


def locate(pages, evidence):
    ne = normalize_source_text(evidence)

    if len(ne) < 8:
        return None

    for p in pages:
        nt = normalize_source_text(p["text"])

        # Preferred: full normalized quotation exists.
        if ne in nt:
            return p["page"]

        # Conservative fallback for small PDF extraction differences.
        prefix = ne[:min(120, len(ne))]

        if len(prefix) > 40 and prefix in nt:
            return p["page"]

    return None

def retrieve_passages(pages, field_name, max_passages=8):
    """
    Deterministically retrieve small source passages that are likely
    to contain evidence for a requested extraction field.

    This does NOT decide the answer. It only narrows the source text
    that will be given to the model.
    """

    field = field_name.strip().lower()

    keyword_map = {
        "study design": [
            "randomized",
            "randomised",
            "controlled trial",
            "clinical trial",
            "trial",
            "prospective",
            "retrospective",
            "cohort",
            "case-control",
            "cross-sectional",
            "study design",
            "randomly assigned",
            "randomly allocated",
        ],

        "sample size": [
            "patients",
            "participants",
            "subjects",
            "enrolled",
            "included",
            "recruited",
            "randomized",
            "randomised",
            "assigned",
            "sample",
            "n =",
            "n=",
        ],

        "population": [
            "patients",
            "participants",
            "subjects",
            "diagnosed",
            "diagnosis",
            "inclusion",
            "eligibility",
            "eligible",
            "hospitalized",
            "hospitalised",
            "men",
            "women",
            "age",
        ],

        "intervention": [
            "intervention",
            "training",
            "exercise",
            "treatment",
            "therapy",
            "received",
            "assigned",
            "program",
            "programme",
            "session",
        ],

        "control": [
            "placebo",
            "placebo group",
            "control group",
            "comparison group",
            "comparator",
            "randomly assigned",
            "randomly allocated",
            "stretching",
            "relaxation",
        ],

        "comparator": [
            "placebo",
            "placebo group",
            "control group",
            "comparison group",
            "comparator",
            "randomly assigned",
            "randomly allocated",
            "stretching",
            "relaxation",
        ],

        "intervention duration": [
            "days",
            "day",
            "weeks",
            "week",
            "months",
            "month",
            "training started",
            "training period",
            "training programme",
            "exercise programme",
            "sessions",
            "session",
            "daily",
            "every day",
            "10 days",
        ]
    }

    # Match exact field first, then tolerate names such as
    # "Sample Size (N)" or "Study Design".
    keywords = None

    for key, values in keyword_map.items():
        if key in field:
            keywords = values
            break

    # Generic fallback for user-created extraction fields.
    if keywords is None:
        keywords = [
            word
            for word in re.findall(r"[a-zA-Z]+", field)
            if len(word) >= 4
        ]

    candidates = []

    for page in pages:
        # References often contain field keywords such as
        # "randomized controlled trial" but describe OTHER studies.
        # Heavily deprioritize the reference section.
        page_text_lower = page["text"].lower()

        likely_references_page = (
            "references" in page_text_lower
            or (
                page["page"] == len(pages)
                and len(re.findall(r"\b\d+\s+[A-Z][a-z]+", page["text"])) > 5
            )
        )
        # PDF extraction often produces line breaks in odd places.
        # Normalize whitespace before splitting into passages.
        text = re.sub(r"\s+", " ", page["text"]).strip()

        if not text:
            continue

        # Split approximately by sentence boundaries.
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()

            matched = [
                keyword
                for keyword in keywords
                if keyword in sentence_lower
            ]

            bonus = 0

            # Numbers next to time units are especially informative
            # for duration fields.
            if "duration" in field:
                if re.search(
                    r"\b\d+\s*(day|days|week|weeks|month|months)\b",
                    sentence_lower
                ):
                    bonus += 5

            if not matched:
                continue

            # Give the model a little context around the matching sentence.
            start = max(0, i - 1)
            end = min(len(sentences), i + 2)

            passage = " ".join(sentences[start:end]).strip()

            if len(passage) < 30:
                continue

            score = len(matched) + bonus

            if likely_references_page:
                score -= 5

            candidates.append({
                "page": page["page"],
                "text": passage,
                "score": score,
            })

    # Prefer passages containing several field-specific keywords.
    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    selected = []
    seen = set()

    for candidate in candidates:
        normalized = re.sub(
            r"\s+",
            " ",
            candidate["text"]
        ).strip().lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        selected.append(candidate)

        if len(selected) >= max_passages:
            break

    return selected

def validate_candidate(field_name, field_type, value, evidence):
    """
    Deterministic validation of an extracted candidate.

    This does NOT prove semantic correctness.
    It checks whether the extracted value has basic structural and
    textual support appropriate for the requested field.

    Returns:
        (True, reason)
        or
        (False, reason)
    """

    field = field_name.strip().lower()
    value_text = str(value).strip()
    evidence_text = str(evidence).strip()

    value_lower = value_text.lower()
    evidence_lower = evidence_text.lower()

    if not value_text:
        return False, "Extracted value is empty."

    if not evidence_text:
        return False, "Evidence is empty."

    # ---------------------------------------------------------
    # SAMPLE SIZE
    # ---------------------------------------------------------

    if "sample" in field:

        if "%" in value_text:
            return False, "Sample size cannot be a percentage."

        match = re.fullmatch(r"\d+", value_text)

        if not match:
            return False, "Sample size must be an integer."

        if value_text not in evidence_text:
            return False, (
                "Sample-size value does not occur in the evidence."
            )

        suspicious = [
            "was sufficient",
            "would be sufficient",
            "should be sufficient",
            "minimum of",
            "required",
            "power calculation",
            "statistical power",
            "sample size calculation",
        ]

        if any(term in evidence_lower for term in suspicious):
            return False, (
                "Evidence appears to describe a sample-size or "
                "power calculation rather than the actual study N."
            )

        return True, "Integer participant count is directly supported."

    # ---------------------------------------------------------
    # INTERVENTION DURATION
    # ---------------------------------------------------------

    if "duration" in field:

        duration_pattern = (
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:minute|minutes|hour|hours|day|days|"
            r"week|weeks|month|months|year|years)\b"
        )

        value_duration = re.search(
            duration_pattern,
            value_lower
        )

        if not value_duration:
            return False, (
                "Duration value does not contain a number "
                "and time unit."
            )

        normalized_duration = re.sub(
            r"\s+",
            " ",
            value_duration.group(0)
        ).strip()

        normalized_evidence = re.sub(
            r"\s+",
            " ",
            evidence_lower
        )

        if normalized_duration not in normalized_evidence:
            return False, (
                "Duration value does not occur in the evidence."
            )

        return True, "Duration is directly supported by evidence."

    # ---------------------------------------------------------
    # STUDY DESIGN
    # ---------------------------------------------------------

    if "study design" in field or field == "design":

        design_terms = [
            "randomised",
            "randomized",
            "controlled",
            "trial",
            "prospective",
            "retrospective",
            "cohort",
            "case-control",
            "cross-sectional",
            "systematic review",
            "meta-analysis",
        ]

        if not any(
            term in value_lower
            for term in design_terms
        ):
            return False, (
                "Value does not contain recognised "
                "study-design terminology."
            )

        if not any(
            term in evidence_lower
            for term in design_terms
        ):
            return False, (
                "Evidence does not contain study-design terminology."
            )

        return True, "Study-design terminology is supported."

    # ---------------------------------------------------------
    # TEXT FIELDS
    # ---------------------------------------------------------

    # For Population, Intervention, Control, and other text fields,
    # require meaningful lexical overlap between value and evidence.

    value_words = {
        word
        for word in re.findall(r"[a-zA-Z]+", value_lower)
        if len(word) >= 4
    }

    evidence_words = {
        word
        for word in re.findall(r"[a-zA-Z]+", evidence_lower)
        if len(word) >= 4
    }

    if value_words:

        overlap = value_words & evidence_words
        overlap_ratio = len(overlap) / len(value_words)

        if overlap_ratio < 0.5:
            return False, (
                f"Insufficient textual support for value "
                f"(word overlap {overlap_ratio:.0%})."
            )

    return True, "Value has direct textual support in the evidence."


@app.post("/projects/{pid}/run")
def run(pid, b: RunIn):
    c = db()

    project = c.execute(
        "SELECT * FROM projects WHERE id=?",
        (pid,)
    ).fetchone()

    docs = c.execute(
        "SELECT * FROM documents WHERE project_id=?",
        (pid,)
    ).fetchall()

    fields = c.execute(
        "SELECT * FROM fields WHERE project_id=? ORDER BY position",
        (pid,)
    ).fetchall()

    c.close()

    if not docs or not fields:
        raise HTTPException(
            400,
            "Add documents and approve an extraction plan first."
        )

    audit(
        pid,
        "Extraction started",
        f"{len(docs)} documents · {len(fields)} fields · model {b.model}"
    )

    # Remove results from an earlier extraction run.
    c = db()
    c.execute(
        "DELETE FROM evidence WHERE project_id=?",
        (pid,)
    )
    c.commit()
    c.close()

    for document in docs:

        pages = json.loads(document["text_json"])

        print("\n" + "=" * 80)
        print("CALVAD DOCUMENT:", document["name"])
        print("PAGES:", len(pages))
        print(
            "EXTRACTED CHARACTERS:",
            sum(len(p["text"]) for p in pages)
        )
        print("=" * 80)

        # Extract ONE field at a time.
        #
        # This is deliberately slower than asking the model for every
        # field simultaneously, but is much more reliable for the MVP.
        for field in fields:

            best_candidate = None

                # Retrieve field-specific passages before asking the model.
            passages = retrieve_passages(
                pages,
                field["name"],
                max_passages=8
            )

            print("\n" + "-" * 80)
            print("FIELD:", field["name"])
            print("MODEL:", b.model)
            print("RETRIEVED PASSAGES:", len(passages))

            for i, passage in enumerate(passages, start=1):
                preview = passage["text"][:180].replace("\n", " ")
                print(
                    f"  [{i}] page {passage['page']} "
                    f"score={passage['score']} | {preview}"
                )

            if not passages:
                print(
                    "NO RETRIEVAL CANDIDATES:",
                    field["name"]
                )

            # Give Qwen only the passages Calvad retrieved for this field.
            source = "\n\n".join(
                f"[PASSAGE {i + 1} | PAGE {passage['page']}]\n"
                f"{passage['text']}"
                for i, passage in enumerate(passages)
            )

            if passages:

                prompt = f"""
    You are extracting ONE field from a scientific research paper.

    RESEARCH QUESTION:
    {project['question']}

    FIELD TO EXTRACT:
    {field['name']}

    FIELD TYPE:
    {field['type']}

    You have been given a small set of passages retrieved from the
    scientific paper because they may contain evidence relevant to this field.

    RULES:

    1. Extract ONLY the requested field.

    2. "value" must be the value actually reported by this study.

    3. "evidence" must be a short EXACT quotation copied from the
    retrieved source passages.

    4. Do not paraphrase the evidence.

    5. The evidence must directly support the value for THIS FIELD.

    6. A passage being present does NOT mean that it contains the answer.

    7. If none of the passages directly supports the requested field,
    return found=false.

    8. Never infer or guess.

    9. Never use 0 to represent missing information.

    10. For Sample Size:
        return the actual number of participants in the study.
        Do not return percentages, response rates, power calculations,
        required sample sizes, or unrelated subgroup counts.

    11. For Study Design:
        return the actual study design, such as randomized controlled
        trial, cohort study, case-control study, or cross-sectional study.

    12. For Population:
        return who the actual study participants were.

    13. For Intervention:
        return the intervention actually administered.

    14. For Control or Comparator:
        identify the comparison, control, or placebo group and return the
        treatment, placebo, activity, usual care, or other condition that
        participants in that group actually received.

        A group does NOT need to be explicitly called "control".
        A placebo group counts as the comparison group.

        For example, if the paper says participants were assigned to
        "placebo (low-intensity stretching and relaxation exercises)",
        the Control value is:
        "low-intensity stretching and relaxation exercises".

    15. For Intervention Duration:
        return how long the intervention itself lasted, not follow-up
        duration or hospitalization duration.

    RETRIEVED SOURCE PASSAGES:

    {source}
    """

                print("\n--- EXTRACTION DEBUG ---")
                print("FIELD SENT TO MODEL:", field["name"])
                print("MODEL:", b.model)
                print("PASSAGES SENT:", len(passages))
                print("--- END EXTRACTION DEBUG ---")

                raw = ollama(
                    prompt,
                    model=b.model,
                    schema=EXTRACTION_SCHEMA
                )

                print("RAW OLLAMA RESPONSE:")
                print(raw)

                try:
                    candidate = json.loads(raw)
                except json.JSONDecodeError as exc:
                    print("DROPPED: invalid JSON:", exc)
                    candidate = None

                if candidate is not None:

                    expected_keys = {
                        "found",
                        "value",
                        "evidence"
                    }

                    if set(candidate.keys()) != expected_keys:
                        print(
                            "DROPPED: response does not match "
                            "extraction schema:",
                            candidate.keys()
                        )
                        candidate = None

                if (
                    candidate is not None
                    and candidate["found"] is True
                ):

                    value = candidate["value"]
                    evidence_text = candidate["evidence"]

                    if value is None or evidence_text is None:
                        print(
                            "DROPPED: found=true but value "
                            "or evidence is missing"
                        )

                    else:

                        value = str(value).strip()
                        evidence_text = str(evidence_text).strip()

                        if not value or not evidence_text:
                            print(
                                "DROPPED: empty value or evidence"
                            )

                        else:

                            field_name = field["name"].lower()

                            # Reject missing-value placeholders.
                            if (
                                field["type"] != "numeric"
                                and value.lower()
                                in {
                                    "0",
                                    "0.0",
                                    "null",
                                    "none",
                                    "n/a"
                                }
                            ):
                                print(
                                    "DROPPED PLACEHOLDER VALUE:",
                                    value
                                )

                            else:

                                rejected_by_field_rule = False

                                # Basic deterministic value/type checks.
                                if field["type"] == "numeric":

                                    # Percentages are not valid values for
                                    # ordinary numeric extraction fields such
                                    # as total Sample Size.
                                    if "%" in value:
                                        print(
                                            "DROPPED TYPE MISMATCH:",
                                            field["name"],
                                            "=",
                                            value,
                                            "(percentage returned for "
                                            "numeric field)"
                                        )

                                        rejected_by_field_rule = True

                                # Prevent the specific sample-size failure
                                # observed in our earlier test.
                                if (
                                    not rejected_by_field_rule
                                    and "sample" in field_name
                                ):
                                    evidence_lower = (
                                        evidence_text.lower()
                                    )

                                    suspicious_sample_phrases = [
                                        "was sufficient",
                                        "would be sufficient",
                                        "should be sufficient",
                                        "required sample",
                                        "sample size required",
                                        "required to detect",
                                        "power calculation",
                                        "statistical power",
                                    ]

                                    if any(
                                        phrase in evidence_lower
                                        for phrase
                                        in suspicious_sample_phrases
                                    ):
                                        print(
                                            "DROPPED SAMPLE SIZE "
                                            "CANDIDATE:",
                                            value,
                                            "- likely power/sample-size "
                                            "calculation"
                                        )

                                        rejected_by_field_rule = True

                        if not rejected_by_field_rule:

                            # Gate 1: prove that the quoted evidence exists
                            # in the original source document.
                            source_page = locate(
                                pages,
                                evidence_text
                            )

                            if source_page is not None:

                                print(
                                    "SOURCE MATCHED:",
                                    field["name"],
                                    "=",
                                    value,
                                    "page",
                                    source_page,
                                )

                                # Gate 2: deterministic field/value validation.
                                valid, validation_reason = validate_candidate(
                                    field["name"],
                                    field["type"],
                                    value,
                                    evidence_text
                                )

                                if valid:

                                    print(
                                        "VALIDATED:",
                                        field["name"],
                                        "=",
                                        value,
                                        "|",
                                        validation_reason
                                    )

                                    best_candidate = {
                                        "value": value,
                                        "evidence": evidence_text,
                                        "page": source_page,
                                        "source_matched": 1,
                                        "validated": 1,
                                        "validation_reason": validation_reason,
                                    }

                                else:

                                    print(
                                        "DROPPED BY VALIDATION:",
                                        field["name"],
                                        "=",
                                        value,
                                        "|",
                                        validation_reason
                                    )

                            else:

                                print(
                                    "DROPPED: SOURCE NOT FOUND:",
                                    field["name"],
                                    "=",
                                    value
                                )

                elif (
                    candidate is not None
                    and candidate["found"] is not True
                ):
                    print(
                        "MODEL FOUND NO SUPPORTED VALUE:",
                        field["name"]
                    )

            c = db()
            if best_candidate:

                c.execute(
                    """
                    INSERT INTO evidence(
                        id,
                        project_id,
                        document_id,
                        field_id,
                        value,
                        evidence,
                        page,
                        verified,
                        status,
                        reason,
                        model,
                        source_matched,
                        validated,
                        validation_reason
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        pid,
                        document["id"],
                        field["id"],
                        best_candidate["value"],
                        best_candidate["evidence"],
                        best_candidate["page"],

                        # Legacy compatibility field.
                        1,

                        # Human review has not happened yet.
                        "pending",
                        None,

                        # Model used for extraction.
                        b.model,

                        # Deterministic gates.
                        best_candidate["source_matched"],
                        best_candidate["validated"],
                        best_candidate["validation_reason"],
                    )
                )

            else:

                c.execute(
                    """
                    INSERT INTO evidence(
                        id,
                        project_id,
                        document_id,
                        field_id,
                        value,
                        evidence,
                        page,
                        verified,
                        status,
                        reason,
                        model,
                        source_matched,
                        validated,
                        validation_reason
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),
                        pid,
                        document["id"],
                        field["id"],
                        "",
                        "",
                        None,
                        0,
                        "missing",
                        "No candidate passed source matching and deterministic validation.",
                        b.model,
                        0,
                        0,
                        None,
                    )
                )

            c.commit()
            c.close()

    c = db()

    source_matched_count = c.execute(
        """
        SELECT count(*)
        FROM evidence
        WHERE project_id=?
        AND source_matched=1
        """,
        (pid,),
    ).fetchone()[0]

    validated_count = c.execute(
        """
        SELECT count(*)
        FROM evidence
        WHERE project_id=?
        AND validated=1
        """,
        (pid,),
    ).fetchone()[0]

    missing_count = c.execute(
        """
        SELECT count(*)
        FROM evidence
        WHERE project_id=?
        AND status='missing'
        """,
        (pid,),
    ).fetchone()[0]

    c.execute(
        "UPDATE projects SET status='extracted' WHERE id=?",
        (pid,)
    )

    c.commit()
    c.close()

    audit(
        pid,
        "Extraction validation completed",
        (
            f"{source_matched_count} source matched · "
            f"{validated_count} validated · "
            f"{missing_count} missing"
        )
    )

    return {
        "source_matched": source_matched_count,
        "validated": validated_count,
        "missing": missing_count
    }


@app.get("/projects/{pid}/evidence")
def evidence(pid):
    c = db()
    rows = [
        dict(r)
        for r in c.execute(
            """SELECT e.*,d.name document_name,f.name field_name,f.position FROM evidence e JOIN documents d ON d.id=e.document_id JOIN fields f ON f.id=e.field_id WHERE e.project_id=? ORDER BY d.name,f.position""",
            (pid,),
        )
    ]
    c.close()
    return rows


@app.get("/documents/{did}/page/{page}")
def docpage(did, page: int):
    c = db()
    d = c.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone()
    c.close()
    if not d:
        raise HTTPException(404)
    pages = json.loads(d["text_json"])
    match = next((x for x in pages if x["page"] == page), None)
    return {"name": d["name"], "page": page, "text": match["text"] if match else ""}


@app.post("/evidence/{eid}/review")
def review(eid, b: ReviewIn):
    c = db()
    e = c.execute("SELECT * FROM evidence WHERE id=?", (eid,)).fetchone()
    if not e:
        raise HTTPException(404)
    if b.action == "correct":
        c.execute(
            "UPDATE evidence SET value=?,status='corrected' WHERE id=?", (b.value, eid)
        )
        details = f"Value corrected to {b.value}"
    elif b.action == "reject":
        c.execute("UPDATE evidence SET status='rejected' WHERE id=?", (eid,))
        details = "Value rejected"
    else:
        c.execute("UPDATE evidence SET status='accepted' WHERE id=?", (eid,))
        details = "Value accepted"
    c.commit()
    c.close()
    audit(e["project_id"], "Evidence reviewed", details)
    return {"ok": True}


@app.post("/projects/{pid}/synthesis")
def synthesis(pid, b: RunIn):
    c = db()
    p = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    rows = c.execute(
        """
        SELECT
            d.name document,
            f.name field,
            e.value,
            e.evidence,
            e.page
        FROM evidence e
        JOIN documents d
            ON d.id=e.document_id
        JOIN fields f
            ON f.id=e.field_id
        WHERE e.project_id=?
        AND e.source_matched=1
        AND e.validated=1
        AND e.status IN ('accepted', 'corrected')
        AND e.value!=''
        ORDER BY d.name, f.position
        """,
        (pid,),
    ).fetchall()
    c.close()
    data = [dict(r) for r in rows]
    if not data:
        raise HTTPException(
            400,
            "No accepted or corrected validated evidence is available for synthesis."
        )
    prompt = (
        f"""Research question: {p['question']}\nWrite a concise research synthesis using ONLY the evidence records below. Do not add outside facts. Cite records inline using [E1], [E2], etc. Mention limitations when evidence is missing.\nEVIDENCE:\n"""
        + "\n".join(
            f"[E{i+1}] {x['document']} | {x['field']}: {x['value']} | source: {x['evidence']}"
            for i, x in enumerate(data)
        )
    )
    text = ollama(prompt, b.model, False)
    c = db()
    c.execute(
        "INSERT OR REPLACE INTO syntheses VALUES(?,?,?,?)", (pid, text, now(), b.model)
    )
    c.commit()
    c.close()
    audit(
        pid,
        "Synthesis generated",
        f"Based on {len(data)} validated and human-reviewed evidence records",
    )
    return {"text": text, "records": len(data)}


@app.get("/projects/{pid}/synthesis")
def get_syn(pid):
    c = db()
    r = c.execute("SELECT * FROM syntheses WHERE project_id=?", (pid,)).fetchone()
    c.close()
    return dict(r) if r else None


@app.get("/projects/{pid}/audit")
def audits(pid):
    c = db()
    r = [
        dict(x)
        for x in c.execute(
            "SELECT * FROM audit WHERE project_id=? ORDER BY id DESC", (pid,)
        )
    ]
    c.close()
    return r


@app.get("/projects/{pid}/export.csv")
def export_csv(pid):
    rows = evidence(pid)
    out = io.StringIO()
    w = csv.DictWriter(
        out,
        fieldnames=[
            "document_name",
            "field_name",
            "value",
            "page",
            "source_matched",
            "validated",
            "validation_reason",
            "status",
            "evidence",
            "model",
        ],
    )
    w.writeheader()
    [w.writerow({k: r.get(k) for k in w.fieldnames}) for r in rows]
    path = DATA / f"{pid}-evidence.csv"
    path.write_text(out.getvalue())
    return FileResponse(path, filename="calvad-evidence.csv")


@app.get("/projects/{pid}/export.json")
def export_json(pid):
    path = DATA / f"{pid}-evidence.json"
    path.write_text(
        json.dumps({"evidence": evidence(pid), "audit": audits(pid)}, indent=2)
    )
    return FileResponse(path, filename="calvad-evidence.json")