import os
import os.path

serverKatalog = os.path.dirname(__file__)

config = {
    "admin_username": os.environ.get("ADMIN_USERNAME", "admin"),
    "admin_password": os.environ.get("ADMIN_PASSWORD", "admin"),
    "mongo_uri": os.environ.get("MONGO_URI", ""),
    "mongodb_db_name": os.environ.get("MONGODB_DB_NAME", "alkotester"),
    "employees_json": os.path.join(serverKatalog, "employees.json"),
    "logs_dir": os.path.join(serverKatalog, "logs"),
    "admin_port": 80,
}
