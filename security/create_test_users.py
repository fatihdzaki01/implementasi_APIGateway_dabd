from shared.db import SessionLocal
from shared.models import User, Role
from security.auth import hash_password


def create_test_users():
    db = SessionLocal()

    try:
        test_users = [
            {"username": "admin_test",    "password": "Admin123!",   "role_name": "admin"},
            {"username": "user_test",     "password": "User123!",    "role_name": "user"},
            {"username": "readonly_test", "password": "Read123!",    "role_name": "readonly"},
            {"username": "service_test",  "password": "Service123!", "role_name": "service"},
        ]

        created_count = 0
        existing_count = 0

        print("Creating test users...")
        print()

        for user_data in test_users:
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()

            if existing_user:
                print(f"User '{user_data['username']}' already exists")
                existing_count += 1
                continue

            role = db.query(Role).filter(Role.name == user_data["role_name"]).first()

            if not role:
                print(f"Role '{user_data['role_name']}' not found. Run init_roles.py first.")
                continue

            user = User(
                username=user_data["username"],
                password_hash=hash_password(user_data["password"]),
                role_id=role.id,
                is_active=True
            )
            db.add(user)
            print(f"Created user '{user_data['username']}' with role '{user_data['role_name']}'")
            created_count += 1

        db.commit()

        print(f"\nTest user creation complete — created: {created_count}, existing: {existing_count}")
        print()
        print("Test User Credentials:")
        print()
        for user_data in test_users:
            print(f"  {user_data['username']} ({user_data['role_name']}): {user_data['password']}")
        print()
        print("Login example:")
        print("  curl -X POST http://localhost:8000/auth/login \\")
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"username":"admin_test","password":"Admin123!"}\'')

        return True

    except Exception as e:
        db.rollback()
        print(f"Error creating test users: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    print("Security Module - Test User Creation")
    print()
    success = create_test_users()
    if not success:
        print("Test user creation failed. Make sure to run init_roles.py first.")
