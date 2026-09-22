# Data dictionary

The template uses the field keys below as column headers. All non-email headers are required. Values may be blank. Recognized questionnaire fragments are provided for compatibility with existing Google Forms exports.

| Field key | Description | Type or scale | Construct | Recognized questionnaire fragment |
| --- | --- | --- | --- | --- |
| `timestamp` | Submission timestamp | datetime |  | `Timestamp` |
| `consent` | Informed consent | category |  | `Informed Consent` |
| `years_experience` | Years of experience | ordinal |  | `How many years of experience` |
| `institution_type` | Institution type | category |  | `What type of institution` |
| `roles` | Role | multi |  | `Please specify your primary role` |
| `pjbl_taught` | PjBL teaching | experience | PjBL experience | `[Taught courses using PjBL]` |
| `pjbl_researched` | PjBL research | experience | PjBL experience | `[Researched PjBL]` |
| `pjbl_designed` | PjBL design | experience | PjBL experience | `[Designed PjBL projects for my course]` |
| `pjbl_adopted` | PjBL adoption | experience | PjBL experience | `[Adopted PjBL projects developed by others]` |
| `pjbl_assessed` | PjBL assessment | experience | PjBL experience | `[Assessed student work in PjBL]` |
| `course_levels` | Course level | multi |  | `typical levels of the courses` |
| `computing_areas` | Area | multi |  | `primary computing areas` |
| `clarity_purpose` | Purpose and intended use are clear | agreement | Clarity | `[The intended use and purpose` |
| `clarity_components` | Major components are clearly defined | agreement | Clarity | `[The major components of FORAP` |
| `clarity_relationships` | Relationships among components are clear | agreement | Clarity | `[The relationships among FORAP components` |
| `clarity_terminology` | Terminology is understandable | agreement | Clarity | `[The terminology used in FORAP` |
| `clarity_structure` | Structure and organization are easy to follow | agreement | Clarity | `[The structure and organization of FORAP` |
| `clarity_comments` | Comments on clarity | text |  | `comments on your Clarity ratings` |
| `complete_major_components` | Includes major computing PjBL components | agreement | Completeness | `[Includes the major components needed` |
| `complete_principles` | Covers key PjBL principles | agreement | Completeness | `[Adequately covers the key PjBL principles` |
| `complete_reusable` | Covers goals for reusable packaging | agreement | Completeness | `[Adequately covers the major design goals needed for reusable` |
| `complete_adaptable` | Covers goals for adaptable packaging | agreement | Completeness | `[Adequately covers the major design goals needed for adaptable` |
| `complete_instructor` | Covers instructor support | agreement | Completeness | `[Adequately covers instructor support` |
| `complete_student` | Covers student support | agreement | Completeness | `[Adequately covers student support` |
| `complete_assessment` | Covers assessment support | agreement | Completeness | `[Adequately covers assessment support` |
| `complete_attributes` | Includes key project attributes | agreement | Completeness | `[Includes the key project attributes` |
| `missing_components` | Missing components | text |  | `important additional project components` |
| `completeness_comments` | Comments on completeness | text |  | `comments on your Completeness ratings` |
| `use_design` | Facilitates designing new projects | agreement | Overall usefulness | `[Facilitates the design of new projects` |
| `use_find` | Facilitates finding fitting projects | agreement | Overall usefulness | `[Facilitates finding projects` |
| `use_reuse` | Facilitates reusing projects | agreement | Overall usefulness | `[Facilitates reusing existing projects` |
| `use_adapt` | Facilitates adapting projects | agreement | Overall usefulness | `[Facilitates adapting existing projects` |
| `usefulness_comments` | Comments on design and adoption usefulness | text |  | `comments on how FORAP may or may not facilitate` |
| `instructor_overview` | Project overview | usefulness | Instructor support | `[Project Overview` |
| `instructor_solutions` | Sample solutions | usefulness | Instructor support | `[Sample Solutions` |
| `instructor_notes` | Instructor notes | usefulness | Instructor support | `[Instructor Notes` |
| `instructor_reference` | Reference course | usefulness | Instructor support | `[Reference Course` |
| `instructor_comments` | Comments on instructor support | text |  | `comments on the usefulness of including the instructor support` |
| `student_scaffolding` | Task scaffolding | usefulness | Student support | `[Task Scaffolding` |
| `student_installation` | Installation guidelines | usefulness | Student support | `[Installation Guidelines` |
| `student_labs` | Laboratory exercises | usefulness | Student support | `[Laboratory Exercises` |
| `student_resources` | Resources | usefulness | Student support | `[Resources` |
| `student_comments` | Comments on student support | text |  | `comments on the usefulness of including the student support` |
| `assessment_milestones` | Phased milestones | usefulness | Assessment support | `[Phased Milestones` |
| `assessment_transfer` | Transfer-oriented design problems | usefulness | Assessment support | `[Transfer-oriented Design Problems` |
| `assessment_rubric` | Detailed rubric | usefulness | Assessment support | `[Detailed Rubric` |
| `assessment_comments` | Comments on assessment support | text |  | `comments on the usefulness of including the assessment support` |
| `attribute_greenfield` | Greenfield vs brownfield | effectiveness | Project attributes | `[Greenfield vs Brownfield` |
| `attribute_duration` | Expected duration/scope | effectiveness | Project attributes | `[Expected Duration/Scope` |
| `attribute_complexity` | Technical complexity | effectiveness | Project attributes | `[Level of Technical Complexity` |
| `attribute_domain` | Domain/discipline | effectiveness | Project attributes | `[Domain/Discipline` |
| `attribute_competency` | Competency specification | effectiveness | Project attributes | `[Competency Specification` |
| `attribute_comments` | Comments on project attributes | text |  | `comments on the effectiveness of including the project attributes` |
| `strengths` | Greatest strengths | text |  | `greatest strengths of the FORAP` |
| `weaknesses` | Greatest weaknesses or limitations | text |  | `greatest weaknesses or limitations` |
| `suggestions` | Suggestions for revisions or additions | text |  | `specific suggestions for revisions or additions` |
| `followup_email` | Optional follow-up email | pii |  | `open to being contacted` |
