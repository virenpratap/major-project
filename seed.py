import json
from app import create_app
from app.extensions import db
from app.models import User, Profile, Department, Batch, Post, Event, Tag, UserTag, Job
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, timezone

app = create_app()

def seed():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        print("Seeding departments...")
        depts_data = [
            {'name': 'Computer Science & Engineering', 'code': 'CSE', 'hod': 'Dr. Alan Turing'},
            {'name': 'Electronics & Communication', 'code': 'ECE', 'hod': 'Dr. Nikola Tesla'},
            {'name': 'Mechanical Engineering', 'code': 'ME', 'hod': 'Dr. James Watt'},
            {'name': 'Information Technology', 'code': 'IT', 'hod': 'Dr. Ada Lovelace'},
            {'name': 'Management Studies', 'code': 'MBA', 'hod': 'Dr. Peter Drucker'}
        ]
        
        depts = {}
        for d in depts_data:
            dept = Department(name=d['name'], code=d['code'], head_name=d['hod'], head_email=f"hod.{d['code'].lower()}@college.edu")
            db.session.add(dept)
            db.session.flush()
            depts[d['code']] = dept

        print("Seeding batches...")
        years = [2023, 2024, 2025, 2026]
        batches = {}
        for code, dept in depts.items():
            for year in years:
                batch = Batch(year=year, department_id=dept.id, total_strength=60, is_passed_out=(year < 2025))
                db.session.add(batch)
                db.session.flush()
                batches[f"{code}_{year}"] = batch

        print("Seeding admin...")
        admin = User(email='admin@alumni.net', username='admin', password_hash=generate_password_hash('admin123'), role='admin', is_approved=True)
        db.session.add(admin)
        db.session.flush()
        admin_profile = Profile(user_id=admin.id, full_name='System Admin', first_name='System', last_name='Admin')
        db.session.add(admin_profile)

        print("Seeding faculty...")
        faculty = User(email='faculty@alumni.net', username='faculty', password_hash=generate_password_hash('faculty123'), role='faculty', is_approved=True)
        db.session.add(faculty)
        db.session.flush()
        fac_profile = Profile(user_id=faculty.id, full_name='Prof. Jane Smith', first_name='Jane', last_name='Smith', department_id=depts['CSE'].id, title='Senior Professor')
        db.session.add(fac_profile)

        print("Seeding alumni...")
        alumni_data = [
            {'name': 'Rahul Sharma', 'email': 'rahul@example.com', 'company': 'Google', 'title': 'SDE II', 'dept': 'CSE', 'year': 2023},
            {'name': 'Priya Patel', 'email': 'priya@example.com', 'company': 'Microsoft', 'title': 'Product Manager', 'dept': 'IT', 'year': 2023},
            {'name': 'Amit Verma', 'email': 'amit@example.com', 'company': 'Tesla', 'title': 'Hardware Engineer', 'dept': 'ECE', 'year': 2024}
        ]
        for a in alumni_data:
            u = User(email=a['email'], username=a['name'].lower().replace(' ', '.'), password_hash=generate_password_hash('alumni123'), role='alumni', is_approved=True)
            db.session.add(u)
            db.session.flush()
            p = Profile(
                user_id=u.id, full_name=a['name'], first_name=a['name'].split()[0], last_name=a['name'].split()[1],
                company=a['company'], title=a['title'], department_id=depts[a['dept']].id, 
                batch_id=batches[f"{a['dept']}_{a['year']}"].id, graduation_year=a['year'],
                is_mentor_available=True
            )
            db.session.add(p)

        print("Seeding students...")
        students_data = [
            {'name': 'Hazel Verma', 'email': 'Hazel@example.com', 'dept': 'CSE', 'year': 2026, 'id': '2022CSE001'},
            {'name': 'Anjali Singh', 'email': 'anjali@example.com', 'dept': 'ECE', 'year': 2026, 'id': '2022ECE045'},
            {'name': 'Suresh Kumar', 'email': 'suresh@example.com', 'dept': 'ME', 'year': 2025, 'id': '2021ME012'}
        ]
        for s in students_data:
            u = User(email=s['email'], username=s['name'].lower().replace(' ', '.'), password_hash=generate_password_hash('student123'), role='student', is_approved=True)
            db.session.add(u)
            db.session.flush()
            p = Profile(
                user_id=u.id, full_name=s['name'], first_name=s['name'].split()[0], last_name=s['name'].split()[1],
                department_id=depts[s['dept']].id, batch_id=batches[f"{s['dept']}_{s['year']}"].id,
                graduation_year=s['year'], enrollment_number=s['id']
            )
            db.session.add(p)

        print("Seeding pending registrations...")
        pending_data = [
            {'name': 'Karan Johar', 'email': 'karan@example.com', 'role': 'student', 'dept': 'MBA'},
            {'name': 'Deepika P', 'email': 'deepika@example.com', 'role': 'alumni', 'dept': 'CSE'}
        ]
        for p_user in pending_data:
            u = User(email=p_user['email'], username=p_user['name'].lower().replace(' ', '.'), password_hash=generate_password_hash('user123'), role=p_user['role'], is_approved=False)
            db.session.add(u)
            db.session.flush()
            p = Profile(user_id=u.id, full_name=p_user['name'], department_id=depts[p_user['dept']].id)
            db.session.add(p)

        print("Seeding posts...")
        rahul = User.query.filter_by(email='rahul@example.com').first()
        p1 = Post(author_id=rahul.id, content="Excited to share that we are hiring for SDE interns at Google! Check the jobs portal. #hiring #google", scope='global')
        db.session.add(p1)
        
        Hazel = User.query.filter_by(email='Hazel@example.com').first()
        p2 = Post(author_id=Hazel.id, content="Looking for resources on Distributed Systems. Any recommendations? #help #cse", scope='department', department_id=depts['CSE'].id)
        db.session.add(p2)

        print("Seeding events...")
        now = datetime.now(timezone.utc)
        e1 = Event(
            title='Annual Alumni Meet 2026', description='Join us for the grand reunion of all batches!',
            event_type='reunion', created_by=admin.id, start_time=now + timedelta(days=10, hours=10),
            location='Main Auditorium', is_virtual=False
        )
        db.session.add(e1)
        
        e2 = Event(
            title='CSE Career Roadmap Webinar', description='Interactive session with senior alumni from Top Tech companies.',
            event_type='webinar', created_by=faculty.id, department_id=depts['CSE'].id,
            start_time=now + timedelta(days=2, hours=18), is_virtual=True, meeting_link='https://meet.google.com/abc-defg-hij'
        )
        db.session.add(e2)

        print("Seeding jobs...")
        j1 = Job(
            posted_by=rahul.id,
            title="Senior Software Engineer",
            company="Google",
            description="Looking for talented engineers to join our cloud platform team. Focus on scalability and performance.",
            location="Bangalore / Remote",
            job_type="full-time",
            skills_required=json.dumps(['python', 'distributed systems', 'cloud', 'go'])
        )
        db.session.add(j1)
        db.session.commit()
        print("Database seeded successfully!")

if __name__ == '__main__':
    seed()
