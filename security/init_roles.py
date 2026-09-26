from shared.db import SessionLocal
from shared.models import Role


def create_default_roles():
    db = SessionLocal()

    try:
        default_roles = [
            {
                "name": "admin",
                "permissions": {
                    "* *": True
                }
            },
            {
                "name": "user",
                "permissions": {
                    "GET /service-a/*": True,
                    "GET /service-b/*": True,
                    "GET /service-c/*": True,
                    "POST /service-a/*": True,
                    "POST /service-b/*": True,
                    "POST /service-c/*": True,
                }
            },
            {
                "name": "readonly",
                "permissions": {
                    "GET *": True,
                    "HEAD *": True
                }
            },
            {
                "name": "service",
                "permissions": {
                    "* /service-a/*": True,
                    "* /service-b/*": True,
                    "* /service-c/*": True,
                }
            }
        ]

        created_count = 0
        existing_count = 0

        for role_data in default_roles:
            existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()

            if existing_role:
                existing_role.permissions = role_data["permissions"]
                db.add(existing_role)
                print(f"Updated permissions for role '{role_data['name']}'")
                existing_count += 1
            else:
                role = Role(
                    name=role_data["name"],
                    permissions=role_data["permissions"]
                )
                db.add(role)
                print(f"Created role '{role_data['name']}'")
                created_count += 1

        db.commit()

        print(f"\nRole initialization complete — created: {created_count}, updated: {existing_count}")
        return True

    except Exception as e:
        db.rollback()
        print(f"Error creating roles: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    print("Security Module - Role Initialization")
    success = create_default_roles()
    if not success:
        print("Role initialization failed.")
