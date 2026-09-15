"""
Create Test Users Script
Orang 4 - Security Module

Script untuk membuat test users untuk development/testing.
JANGAN run di production!

Usage:
    python -m security.create_test_users
"""

from shared.db import SessionLocal
from shared.models import User, Role
from security.auth import hash_password


def create_test_users():
    """Create test users untuk setiap role."""
    
    db = SessionLocal()
    
    try:
        # Define test users
        test_users = [
            {
                "username": "admin_test",
                "password": "Admin123!",
                "role_name": "admin"
            },
            {
                "username": "user_test",
                "password": "User123!",
                "role_name": "user"
            },
            {
                "username": "readonly_test",
                "password": "Read123!",
                "role_name": "readonly"
            },
            {
                "username": "service_test",
                "password": "Service123!",
                "role_name": "service"
            }
        ]
        
        created_count = 0
        existing_count = 0
        
        print("Creating test users...")
        print()
        
        for user_data in test_users:
            # Check if user already exists
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            
            if existing_user:
                print(f"✓ User '{user_data['username']}' already exists")
                existing_count += 1
            else:
                # Get role
                role = db.query(Role).filter(Role.name == user_data["role_name"]).first()
                
                if not role:
                    print(f"✗ Role '{user_data['role_name']}' not found! Run init_roles.py first.")
                    continue
                
                # Create user
                user = User(
                    username=user_data["username"],
                    password_hash=hash_password(user_data["password"]),
                    role_id=role.id,
                    is_active=True
                )
                db.add(user)
                print(f"✓ Created user '{user_data['username']}' with role '{user_data['role_name']}'")
                created_count += 1
        
        # Commit
        db.commit()
        
        print("\n" + "="*60)
        print(f"Test user creation complete!")
        print(f"  - Created: {created_count} users")
        print(f"  - Existing: {existing_count} users")
        print("="*60)
        
        # Display credentials
        print("\nTest User Credentials:")
        print()
        for user_data in test_users:
            print(f"{user_data['username']} ({user_data['role_name']}):")
            print(f"  Username: {user_data['username']}")
            print(f"  Password: {user_data['password']}")
            print()
        
        print("⚠️  WARNING: These are TEST users with weak passwords!")
        print("   DO NOT use in production!")
        print()
        print("Test login:")
        print("  curl -X POST http://localhost:8000/auth/login \\")
        print('    -H "Content-Type: application/json" \\')
        print('    -d \'{"username":"admin_test","password":"Admin123!"}\'')
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error creating test users: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    print("="*60)
    print("Security Module - Test User Creation")
    print("="*60)
    print()
    
    success = create_test_users()
    
    if not success:
        print("\n❌ Test user creation failed!")
        print("Make sure to run init_roles.py first!")
