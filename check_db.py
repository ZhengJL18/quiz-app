from app.db.engine import SessionLocal
from app.db.models import Chapter, Subject
db = SessionLocal()
chs = db.query(Chapter).filter(Chapter.description != None, Chapter.description != "").limit(5).all()
for c in chs:
    subj = db.query(Subject).filter_by(id=c.subject_id).first()
    uname = subj.user_id if subj else "?"
    sname = subj.name if subj else "?"
    print(f"Ch{c.id} user={uname} subj={sname} ch={c.name} desc={c.description[:80]}")
print("---")
count = db.query(Chapter).filter(Chapter.description.like("knowledge/%")).count()
print(f"Chapters with vault path: {count}")
count2 = db.query(Chapter).filter(Chapter.description != None, Chapter.description != "", ~Chapter.description.like("knowledge/%")).count()
print(f"Chapters with legacy content: {count2}")
db.close()
