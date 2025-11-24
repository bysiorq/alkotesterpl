import os
import os.path
from dotenv import load_dotenv

load_dotenv()

serverKatalog = os.path.dirname(__file__)

konfig = {
    "login_admina": os.environ.get("ADMIN_USERNAME", "admin"),
    "haslo_admina": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "haslo": os.environ.get("TOKEN", "admin123"),
    "mongo_uri": os.environ.get("MONGO_URI", ""),
    "nazwa_bazy_mongo": os.environ.get("MONGODB_DB_NAME", "alkotester"),
    "plik_pracownicy": os.path.join(serverKatalog, "..", "dane", "pracownicy.json"),
    "folder_logi": os.path.join(serverKatalog, "..", "logi"),
    "port_admina": int(os.environ.get("PORT", 5000)),
}
