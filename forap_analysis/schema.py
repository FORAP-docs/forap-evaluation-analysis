from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    match: str
    kind: str
    construct: str | None = None
    scale: str | None = None
    pii: bool = False


AGREEMENT = {
    "strongly disagree": 1,
    "disagree": 2,
    "neutral": 3,
    "agree": 4,
    "strongly agree": 5,
}
USEFULNESS = {
    "not useful": 1,
    "slightly useful": 2,
    "moderately useful": 3,
    "very useful": 4,
    "extremely useful": 5,
}
EFFECTIVENESS = {
    "not effective": 1,
    "slightly effective": 2,
    "moderately effective": 3,
    "very effective": 4,
    "extremely effective": 5,
}
EXPERIENCE = {"none": 0, "limited": 1, "moderate": 2, "extensive": 3}
SCALE_MAPS = {
    "agreement": AGREEMENT,
    "usefulness": USEFULNESS,
    "effectiveness": EFFECTIVENESS,
    "experience": EXPERIENCE,
}


def _f(
    key: str,
    label: str,
    match: str,
    kind: str,
    construct: str | None = None,
    scale: str | None = None,
    pii: bool = False,
) -> Field:
    return Field(key, label, match, kind, construct, scale, pii)


FIELDS: tuple[Field, ...] = (
    _f("timestamp", "Submission timestamp", "Timestamp", "datetime"),
    _f("consent", "Informed consent", "Informed Consent", "category"),
    _f("years_experience", "Years of experience", "How many years of experience", "ordinal"),
    _f("institution_type", "Institution type", "What type of institution", "category"),
    _f("roles", "Role", "Please specify your primary role", "multi"),
    _f("pjbl_taught", "PjBL teaching", "[Taught courses using PjBL]", "ordinal", "PjBL experience", "experience"),
    _f("pjbl_researched", "PjBL research", "[Researched PjBL]", "ordinal", "PjBL experience", "experience"),
    _f("pjbl_designed", "PjBL design", "[Designed PjBL projects for my course]", "ordinal", "PjBL experience", "experience"),
    _f("pjbl_adopted", "PjBL adoption", "[Adopted PjBL projects developed by others]", "ordinal", "PjBL experience", "experience"),
    _f("pjbl_assessed", "PjBL assessment", "[Assessed student work in PjBL]", "ordinal", "PjBL experience", "experience"),
    _f("course_levels", "Course level", "typical levels of the courses", "multi"),
    _f("computing_areas", "Area", "primary computing areas", "multi"),
    _f("clarity_purpose", "Purpose and intended use are clear", "[The intended use and purpose", "likert", "Clarity", "agreement"),
    _f("clarity_components", "Major components are clearly defined", "[The major components of FORAP", "likert", "Clarity", "agreement"),
    _f("clarity_relationships", "Relationships among components are clear", "[The relationships among FORAP components", "likert", "Clarity", "agreement"),
    _f("clarity_terminology", "Terminology is understandable", "[The terminology used in FORAP", "likert", "Clarity", "agreement"),
    _f("clarity_structure", "Structure and organization are easy to follow", "[The structure and organization of FORAP", "likert", "Clarity", "agreement"),
    _f("clarity_comments", "Comments on clarity", "comments on your Clarity ratings", "text"),
    _f("complete_major_components", "Includes major computing PjBL components", "[Includes the major components needed", "likert", "Completeness", "agreement"),
    _f("complete_principles", "Covers key PjBL principles", "[Adequately covers the key PjBL principles", "likert", "Completeness", "agreement"),
    _f("complete_reusable", "Covers goals for reusable packaging", "[Adequately covers the major design goals needed for reusable", "likert", "Completeness", "agreement"),
    _f("complete_adaptable", "Covers goals for adaptable packaging", "[Adequately covers the major design goals needed for adaptable", "likert", "Completeness", "agreement"),
    _f("complete_instructor", "Covers instructor support", "[Adequately covers instructor support", "likert", "Completeness", "agreement"),
    _f("complete_student", "Covers student support", "[Adequately covers student support", "likert", "Completeness", "agreement"),
    _f("complete_assessment", "Covers assessment support", "[Adequately covers assessment support", "likert", "Completeness", "agreement"),
    _f("complete_attributes", "Includes key project attributes", "[Includes the key project attributes", "likert", "Completeness", "agreement"),
    _f("missing_components", "Missing components", "important additional project components", "text"),
    _f("completeness_comments", "Comments on completeness", "comments on your Completeness ratings", "text"),
    _f("use_design", "Facilitates designing new projects", "[Facilitates the design of new projects", "likert", "Overall usefulness", "agreement"),
    _f("use_find", "Facilitates finding fitting projects", "[Facilitates finding projects", "likert", "Overall usefulness", "agreement"),
    _f("use_reuse", "Facilitates reusing projects", "[Facilitates reusing existing projects", "likert", "Overall usefulness", "agreement"),
    _f("use_adapt", "Facilitates adapting projects", "[Facilitates adapting existing projects", "likert", "Overall usefulness", "agreement"),
    _f("usefulness_comments", "Comments on design and adoption usefulness", "comments on how FORAP may or may not facilitate", "text"),
    _f("instructor_overview", "Project overview", "[Project Overview", "likert", "Instructor support", "usefulness"),
    _f("instructor_solutions", "Sample solutions", "[Sample Solutions", "likert", "Instructor support", "usefulness"),
    _f("instructor_notes", "Instructor notes", "[Instructor Notes", "likert", "Instructor support", "usefulness"),
    _f("instructor_reference", "Reference course", "[Reference Course", "likert", "Instructor support", "usefulness"),
    _f("instructor_comments", "Comments on instructor support", "comments on the usefulness of including the instructor support", "text"),
    _f("student_scaffolding", "Task scaffolding", "[Task Scaffolding", "likert", "Student support", "usefulness"),
    _f("student_installation", "Installation guidelines", "[Installation Guidelines", "likert", "Student support", "usefulness"),
    _f("student_labs", "Laboratory exercises", "[Laboratory Exercises", "likert", "Student support", "usefulness"),
    _f("student_resources", "Resources", "[Resources", "likert", "Student support", "usefulness"),
    _f("student_comments", "Comments on student support", "comments on the usefulness of including the student support", "text"),
    _f("assessment_milestones", "Phased milestones", "[Phased Milestones", "likert", "Assessment support", "usefulness"),
    _f("assessment_transfer", "Transfer-oriented design problems", "[Transfer-oriented Design Problems", "likert", "Assessment support", "usefulness"),
    _f("assessment_rubric", "Detailed rubric", "[Detailed Rubric", "likert", "Assessment support", "usefulness"),
    _f("assessment_comments", "Comments on assessment support", "comments on the usefulness of including the assessment support", "text"),
    _f("attribute_greenfield", "Greenfield vs brownfield", "[Greenfield vs Brownfield", "likert", "Project attributes", "effectiveness"),
    _f("attribute_duration", "Expected duration/scope", "[Expected Duration/Scope", "likert", "Project attributes", "effectiveness"),
    _f("attribute_complexity", "Technical complexity", "[Level of Technical Complexity", "likert", "Project attributes", "effectiveness"),
    _f("attribute_domain", "Domain/discipline", "[Domain/Discipline", "likert", "Project attributes", "effectiveness"),
    _f("attribute_competency", "Competency specification", "[Competency Specification", "likert", "Project attributes", "effectiveness"),
    _f("attribute_comments", "Comments on project attributes", "comments on the effectiveness of including the project attributes", "text"),
    _f("strengths", "Greatest strengths", "greatest strengths of the FORAP", "text"),
    _f("weaknesses", "Greatest weaknesses or limitations", "greatest weaknesses or limitations", "text"),
    _f("suggestions", "Suggestions for revisions or additions", "specific suggestions for revisions or additions", "text"),
    _f("followup_email", "Optional follow-up email", "open to being contacted", "pii", pii=True),
)

FIELD_BY_KEY = {field.key: field for field in FIELDS}
ANALYSIS_FIELDS = tuple(field for field in FIELDS if not field.pii)
ITEM_FIELDS = tuple(field for field in FIELDS if field.kind == "likert")
OPEN_TEXT_FIELDS = tuple(field for field in FIELDS if field.kind == "text")
BACKGROUND_FIELDS = tuple(
    field
    for field in FIELDS[2:12]
    if field.kind in {"category", "multi", "ordinal"}
)
BACKGROUND_CATEGORY_OPTIONS: dict[str, tuple[str, ...]] = {
    "years_experience": (
        "Beginner (e.g., <= 5 years)",
        "Intermediate (e.g., 6-10 years)",
        "Experienced (e.g., 11+ years)",
    ),
    "institution_type": (
        "Research university",
        "Teaching-focused college or university",
        "Community college / two-year college",
        "Polytechnic / institute of technology",
        "Industry / private sector",
        "Government / nonprofit organization",
        "Independent researcher / consultant",
    ),
    "roles": (
        "Instructor/Teacher",
        "Curriculum Designer",
        "Education Researcher",
        "Graduate Teaching Assistant",
    ),
    "course_levels": (
        "Introductory undergraduate",
        "Intermediate undergraduate",
        "Advanced undergraduate",
        "Graduate",
        "Not applicable",
    ),
    "computing_areas": (
        "Software Engineering",
        "Programming Fundamentals",
        "Web / Mobile Development",
        "Data Science / Machine Learning / AI",
        "Cybersecurity",
        "Systems / Networking / Cloud Computing",
        "Database / Information Systems",
        "Human-Computer Interaction",
        "Embedded systems / IoT",
    ),
}
CONSTRUCTS = tuple(dict.fromkeys(field.construct for field in ITEM_FIELDS if field.construct))


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().casefold()


def split_multi(value: object) -> list[str]:
    if value is None:
        return []
    return [part.strip() for part in re.split(r"[,;]", str(value)) if part.strip()]
