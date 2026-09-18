"""
Database Initialization Script - Create Default Roles
Orang 4 - Security Module

Script untuk membuat default roles di database.
Run sekali setelah database migration.

Usage:
    python -m security.init_roles
"""

from shared.db import SessionLocal
from shared.models import Role


def create_default_roles():
    """Create default roles jika belum ada."""
    
    db = SessionLocal()
    
    try:
        # Define default roles dengan permissions
        default_roles = [
            {
                "name": "admin",
                "permissions": {
                    "* *": True  # Full access: all methods, all endpoints
                }
            },
            {
                "name": "user",
                "permissions": {
                    "GET /service-a/*": True,
                    "GET /service-b/*": True,
                    "GET /service-c/*": True,
                    "POST /service-a/items": True,
                    "POST /service-b/items": True,
                    "POST /service-c/items": True,
                }
            },
            {
                "name": "readonly",
                "permissions": {
                    "GET *": True,  # Read-only: GET ke semua endpoints
                    "HEAD *": True
                }
            },
            {
                "name": "service",
                "permissions": {
                    "* /service-a/*": True,  # Service-to-service: full access ke internal services
                    "* /service-b/*": True,
                    "* /service-c/*": True,
                }
            }
        ]
        
        created_count = 0
        existing_count = 0
        
        for role_data in default_roles:
            # Check jika role sudah exists
            existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
            
            if existing_role:
                print(f"✓ Role '{role_data['name']}' already exists")
                existing_count += 1
            else:
                # Create new role
                role = Role(
                    name=role_data["name"],
                    permissions=role_data["permissions"]
                )
                db.add(role)
                print(f"✓ Created role '{role_data['name']}'")
                created_count += 1
        
        # Commit semua changes
        db.commit()
        
        print("\n" + "="*60)
        print(f"Role initialization complete!")
        print(f"  - Created: {created_count} roles")
        print(f"  - Existing: {existing_count} roles")
        print("="*60)
        
        # Display role permissions
        print("\nDefault Role Permissions:")
        for role_data in default_roles:
            print(f"\n{role_data['name'].upper()}:")
            for perm_key, perm_value in role_data['permissions'].items():
                print(f"  - {perm_key}: {perm_value}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error creating roles: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    print("="*60)
    print("Security Module - Role Initialization")
    print("="*60)
    print()
    
    success = create_default_roles()
    
    if success:
        print("\n✅ Role initialization successful!")
        print("\nNext steps:")
        print("1. Create test users dengan: python -m security.create_test_users")
        print("2. Test login API: curl -X POST http://localhost:8000/auth/login")
    else:
        print("\n❌ Role initialization failed!")
        print("Check error messages above and try again.")
