"""Seed the database (safe to re-run).

    python seed.py          staff accounts, domains and levels, sample questions and test slots. No students.
    python seed.py --demo   the above, plus demo students with a made-up test history
"""
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app import models
from app.database import Base, SessionLocal, engine
from app.rules import COMMON_DOMAIN_NAME, DEFAULT_LEVELS as LEVELS
from app.security import hash_password

PASSWORD = "Password@123"
DOMAINS = [
    "Full Stack Development", "Data Science", "AI / Machine Learning",
    "Cloud & DevOps", "Cyber Security", "Embedded & IoT",
]
STAFF = [
    ("Ms. Anitha", "admin@college.edu", "admin"),
    ("Dr. Meena", "owner@college.edu", "owner"),
    ("Mr. Suresh", "invigilator@college.edu", "invigilator"),
]

# Sample questions: (text, options, answer_index, difficulty, topic)
QUESTIONS_L1 = [
    ("Which HTML tag is used for the largest heading?", ["<h6>", "<h1>", "<head>", "<header>"], 1, "easy", "Web basics"),
    ("Which CSS property changes the text colour?", ["font-style", "color", "background", "text-decoration"], 1, "easy", "Web basics"),
    ("Which keyword declares a block-scoped variable that can be reassigned?", ["var", "let", "const", "static"], 1, "easy", "JavaScript"),
    ("What does === check in JavaScript?", ["Value only", "Type only", "Value and type", "Memory address only"], 2, "easy", "JavaScript"),
    ("Which Git command records staged changes as a snapshot?", ["git push", "git commit", "git clone", "git fetch"], 1, "easy", "Version control"),
    ("What does SQL stand for?", ["Structured Query Language", "Simple Question Language", "Sequential Query Logic", "Stored Query Library"], 0, "easy", "Databases"),
    ("Which HTTP status code means the client is not authenticated?", ["200", "301", "401", "503"], 2, "medium", "Web basics"),
    ("What does Array.prototype.map return?", ["The original array, mutated", "A new array of transformed items", "A single value", "undefined"], 1, "medium", "JavaScript"),
    ("What does 'git branch feature' do?", ["Deletes a branch", "Creates a new branch", "Merges a branch", "Switches to the branch"], 1, "medium", "Version control"),
    ("Which SQL clause filters rows before they are grouped?", ["HAVING", "GROUP BY", "WHERE", "ORDER BY"], 2, "medium", "Databases"),
]
QUESTIONS_L3 = [
    ("Which HTTP method is idempotent and used to replace a resource?", ["POST", "PUT", "PATCH", "CONNECT"], 1, "easy", "API design"),
    ("Which SQL feature speeds up lookups on a column?", ["View", "Trigger", "Index", "Sequence"], 2, "easy", "Database indexing"),
    ("In React, which hook holds local component state?", ["useRef", "useState", "useMemo", "useContext"], 1, "easy", "State management"),
    ("Which status code means the resource was not found?", ["200", "401", "404", "500"], 2, "easy", "Error handling"),
    ("What does a signed JWT NOT provide by itself?", ["Integrity", "Confidentiality", "Claims about the user", "An expiry time"], 1, "medium", "Authentication"),
    ("A composite index on (a, b) is most useful for queries that filter on:", ["b only", "a only, or a and b", "neither column", "a OR b only"], 1, "medium", "Database indexing"),
    ("Why do you lift state up in React?", ["To make components faster", "To share state between sibling components", "To avoid using props", "To persist data to localStorage"], 1, "medium", "State management"),
    ("Which status code should a successful resource creation return?", ["200", "201", "204", "302"], 1, "medium", "API design"),
    ("What is the best way for a REST API to report a validation error?", ["200 with an error message", "400 or 422 with details", "Crash the server", "500 Internal Server Error"], 1, "medium", "Error handling"),
    ("Where should a server-side signing secret be stored?", ["In front-end code", "In a public repository", "In server environment configuration", "In the URL"], 2, "medium", "Authentication"),
    ("Which query is LEAST likely to use a B-tree index on column name?", ["WHERE name = 'x'", "WHERE name LIKE 'x%'", "WHERE name LIKE '%x'", "ORDER BY name"], 2, "hard", "Database indexing"),
    ("What commonly causes an infinite render loop with useEffect?", ["An empty dependency array", "Setting state in an effect that depends on that state, with no guard", "Using useRef", "Returning a cleanup function"], 1, "hard", "State management"),
]
QUESTIONS_S1 = [  # Semester 1 common assessment: Coding, Aptitude, Basic domain
    ("What is the output of print(2 + 3 * 4) in Python?", ["20", "14", "24", "Error"], 1, "easy", "Coding"),
    ("Which data structure follows Last-In-First-Out order?", ["Queue", "Stack", "Array", "Tree"], 1, "medium", "Coding"),
    ("What is the time complexity of binary search on a sorted array of n items?", ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1, "medium", "Coding"),
    ("After x = [1, 2, 3]; y = x; y.append(4), what does len(x) return?", ["3", "4", "Error", "None"], 1, "hard", "Coding"),
    ("What is 15% of 200?", ["20", "25", "30", "35"], 2, "easy", "Aptitude"),
    ("A train 100 m long passes a pole in 10 seconds. What is its speed?", ["5 m/s", "10 m/s", "15 m/s", "100 m/s"], 1, "medium", "Aptitude"),
    ("Find the next number: 2, 6, 12, 20, 30, ?", ["36", "40", "42", "44"], 2, "medium", "Aptitude"),
    ("6 workers finish a job in 10 days. How many days will 4 workers take at the same rate?", ["12", "15", "18", "20"], 1, "hard", "Aptitude"),
    ("What is the binary representation of decimal 5?", ["101", "110", "011", "111"], 0, "easy", "Basic domain"),
    ("Which unit is used to measure electric current?", ["Volt", "Ampere", "Ohm", "Watt"], 1, "easy", "Basic domain"),
    ("Which of these is an input device?", ["Monitor", "Printer", "Keyboard", "Speaker"], 2, "medium", "Basic domain"),
    ("Which logic gate outputs 1 only when both inputs are 1?", ["OR", "AND", "XOR", "NOT"], 1, "medium", "Basic domain"),
]
QUESTIONS_S2 = [  # Semester 2 common assessment
    ("Which loop is best when the number of iterations is known in advance?", ["while", "for", "do-while", "goto"], 1, "easy", "Coding"),
    ("Which Python structure stores unique elements only?", ["list", "tuple", "set", "str"], 2, "medium", "Coding"),
    ("What is the time complexity of accessing an array element by index?", ["O(n)", "O(log n)", "O(1)", "O(n^2)"], 2, "medium", "Coding"),
    ("What is the worst-case time complexity of bubble sort?", ["O(n)", "O(n log n)", "O(n^2)", "O(log n)"], 2, "hard", "Coding"),
    ("What is the average of 10, 20 and 30?", ["15", "20", "25", "30"], 1, "easy", "Aptitude"),
    ("The ratio of boys to girls is 3:2. If there are 30 boys, how many girls are there?", ["15", "18", "20", "25"], 2, "medium", "Aptitude"),
    ("A shop gives a 20% discount on a Rs 500 item. What is the selling price?", ["Rs 380", "Rs 400", "Rs 420", "Rs 450"], 1, "medium", "Aptitude"),
    ("Two pipes fill a tank in 12 and 6 hours. Working together, how long do they take?", ["3 hours", "4 hours", "6 hours", "9 hours"], 1, "hard", "Aptitude"),
    ("Which number system uses only the digits 0 and 1?", ["Decimal", "Octal", "Binary", "Hexadecimal"], 2, "easy", "Basic domain"),
    ("Which component is called the brain of the computer?", ["RAM", "CPU", "Hard disk", "Monitor"], 1, "easy", "Basic domain"),
    ("What does HTTP stand for?", ["HyperText Transfer Protocol", "High Transfer Text Process", "HyperText Transmission Program", "Host Transfer Type Protocol"], 0, "medium", "Basic domain"),
    ("Which type of memory is volatile?", ["ROM", "RAM", "SSD", "Hard disk"], 1, "medium", "Basic domain"),
]
SLOTS = [  # (day in Oct 2026, UTC hour, UTC minute, venue, capacity)
    (12, 4, 30, "Block A - Lab 2", 30),
    (12, 8, 30, "Block A - Lab 3", 30),
    (13, 4, 30, "Block C - Seminar Hall", 60),
]
GAPS = {  # skill gaps recorded on failed demo attempts, by level number
    1: [{"topic": "Web basics", "score": 30}, {"topic": "JavaScript", "score": 40}],
    2: [{"topic": "JavaScript", "score": 35}, {"topic": "API design", "score": 45}],
    3: [{"topic": "Database indexing", "score": 30}, {"topic": "State management", "score": 50}],
}


def seed_staff(db) -> None:
    for name, email, role in STAFF:
        if db.scalar(select(models.User).where(models.User.email == email)) is None:
            db.add(models.User(name=name, email=email, role=role, password_hash=hash_password(PASSWORD)))
    db.commit()


def seed_domains(db) -> None:
    if db.scalar(select(models.Domain).limit(1)):
        return
    owner = db.scalar(select(models.User).where(models.User.email == "owner@college.edu"))
    for i, name in enumerate(DOMAINS):
        domain = models.Domain(name=name, owner_id=owner.id if i == 0 else None)
        db.add(domain)
        db.flush()
        for n, (lname, q, pm, dur) in enumerate(LEVELS, start=1):
            db.add(models.Level(
                domain_id=domain.id, number=n, name=f"Level {n} · {lname}",
                question_count=q, pass_mark=pm, duration_min=dur,
            ))
    db.commit()


def add_slots(db, domain_id: int) -> None:
    for day, hour, minute, venue, capacity in SLOTS:
        db.add(models.Slot(
            domain_id=domain_id, starts_at=datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc),
            venue=venue, capacity=capacity,
        ))


def seed_common(db) -> None:
    """The Semester 1-2 common assessments: a special track with one level per semester."""
    common = db.scalar(select(models.Domain).where(models.Domain.is_common.is_(True)))
    if common is None:
        common = models.Domain(name=COMMON_DOMAIN_NAME, is_common=True)
        db.add(common)
        db.flush()
        for n in (1, 2):
            db.add(models.Level(
                domain_id=common.id, number=n, name=f"Semester {n} \u00b7 Common Assessment",
                question_count=12, pass_mark=50, duration_min=30,
            ))
        db.commit()
        db.refresh(common)
    for level, questions in zip(common.levels, (QUESTIONS_S1, QUESTIONS_S2)):
        if db.scalar(select(models.Question.id).where(models.Question.level_id == level.id)) is None:
            for text, options, answer, difficulty, topic in questions:
                db.add(models.Question(
                    level_id=level.id, text=text, options=options, answer_index=answer,
                    difficulty=difficulty, topic=topic,
                ))
    if db.scalar(select(models.Slot.id).where(models.Slot.domain_id == common.id)) is None:
        add_slots(db, common.id)
    db.commit()


def seed_content(db) -> None:
    """Sample content for Full Stack: question banks and slots so a new student can sit a test."""
    domain = db.scalar(select(models.Domain).where(models.Domain.name == DOMAINS[0]))
    for level, questions in ((domain.levels[0], QUESTIONS_L1), (domain.levels[2], QUESTIONS_L3)):
        if db.scalar(select(models.Question.id).where(models.Question.level_id == level.id)) is None:
            for text, options, answer, difficulty, topic in questions:
                db.add(models.Question(
                    level_id=level.id, text=text, options=options, answer_index=answer,
                    difficulty=difficulty, topic=topic,
                ))
    if db.scalar(select(models.Slot.id).where(models.Slot.domain_id == domain.id)) is None:
        add_slots(db, domain.id)
    db.commit()


def seed_demo_students(db) -> None:
    """Made-up students with test history, for demonstrating the owner and admin dashboards."""
    domain = db.scalar(select(models.Domain).where(models.Domain.name == DOMAINS[0]))
    lv = {level.number: level for level in domain.levels}
    if db.scalar(select(models.Slot.id).where(models.Slot.domain_id == domain.id)) is None:
        add_slots(db, domain.id)

    # (name, email, reg_no, dept, sem, current_level, status, points, attempts[(level, no, score, passed)])
    people = [
        ("Arun Kumar", "arun@college.edu", "22CS101", "CSE", 4, 3, "active", 40,
         [(1, 1, 88, True), (2, 1, 45, False), (2, 2, 72, True), (3, 1, 41, False)]),
        ("Divya S", "divya@college.edu", "22CS114", "CSE", 4, 2, "active", 30,
         [(1, 1, 82, True), (2, 1, 40, False)]),
        ("Karthik R", "karthik@college.edu", "22CS127", "CSE", 4, 3, "active", 60,
         [(1, 1, 75, True), (2, 1, 70, True), (3, 1, 30, False), (3, 2, 38, False)]),
        ("Naveen T", "naveen@college.edu", "22IT056", "IT", 4, 1, "removed", 0,
         [(1, 1, 20, False), (1, 2, 30, False), (1, 3, 35, False)]),
        ("Meera P", "meera@college.edu", "21CS088", "CSE", 6, 6, "active", 150,
         [(n, 1, 85, True) for n in range(1, 6)]),
    ]
    for name, email, reg, dept, sem, cur, st, pts, atts in people:
        if db.scalar(select(models.User).where(models.User.email == email)):
            continue
        u = models.User(name=name, email=email, reg_no=reg, role="student", department=dept,
                        semester=sem, password_hash=hash_password(PASSWORD))
        db.add(u)
        db.flush()
        db.add(models.Enrollment(user_id=u.id, domain_id=domain.id, current_level=cur, status=st, points=pts))
        for level_no, no, score, passed in atts:
            db.add(models.Attempt(
                user_id=u.id, level_id=lv[level_no].id, attempt_no=no, score=score, passed=passed,
                skill_gaps=None if passed else GAPS[level_no],
            ))
            if passed:
                db.add(models.Certificate(
                    user_id=u.id, level_id=lv[level_no].id, code=f"CERT-{domain.id}-{level_no}-{u.id}", first_attempt=no == 1,
                ))
    db.commit()


def main() -> None:
    demo = "--demo" in sys.argv
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_staff(db)
        seed_domains(db)
        seed_common(db)
        seed_content(db)
        if demo:
            seed_demo_students(db)
    print(f"Seeded{' with demo students' if demo else ''}. Staff logins (password {PASSWORD}): "
          "admin@college.edu, owner@college.edu, invigilator@college.edu")


if __name__ == "__main__":
    main()
