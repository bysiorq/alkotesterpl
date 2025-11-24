import os
import os.path
from dotenv import load_dotenv

load_dotenv()

serverKatalog = os.path.dirname(__file__)

konfig = {
    "admin_login": os.environ.get("ADMIN_USERNAME", "admin"),
    "admin_haslo": os.environ.get("ADMIN_PASSWORD", "admin"),
    "mongo_uri": os.environ.get("MONGO_URI", ""),
    "nazwa_bazy_mongo": os.environ.get("MONGODB_DB_NAME", "alkotester"),
    "plik_pracownicy": os.path.join(serverKatalog, "employees.json"),
    "folder_logi": os.path.join(serverKatalog, "logs"),
    "port_admina": 80,
}
