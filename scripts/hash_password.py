"""Generate a MaterialHub password hash for .env."""

from getpass import getpass

from app.auth import hash_password


def main() -> None:
    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    print(hash_password(password))


if __name__ == "__main__":
    main()
