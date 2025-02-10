import pyvo
import requests
from pyvo.auth import authsession, securitymethods
import getpass
import time

class JPASClient:
    def __init__(self):
        self.session = requests.Session()
        self.tap_url = "https://archive.cefca.es/catalogues/vo/tap/jpas-idr202406"
        self.service = None
        
    def login(self):
        user = input("CEFCA Username: ")
        pwd = getpass.getpass("CEFCA Password: ")
        
        # Autenticación persistente
        auth = authsession.AuthSession()
        auth.credentials.set(
            securitymethods.USER_PWD,
            {"username": user, "password": pwd}
        )
        
        self.session.post(
            "https://archive.cefca.es/catalogues/login",
            data={"login": user, "password": pwd, "submit": "Sign+In"},
            headers={"Content-type": "application/x-www-form-urlencoded"}
        )
        
        self.service = pyvo.dal.TAPService(
            self.tap_url,
            session=auth.credentials
        )
    
    def force_clean(self):
        """Eliminación agresiva de trabajos incluyendo los bloqueados"""
        jobs = self.service.search_jobs()
        print(f"Encontrados {len(jobs)} trabajos en el historial")
        
        for job in jobs:
            try:
                print(f"Eliminando {job.job_id} ({job.phase})...")
                job.delete()
                time.sleep(3)  # Mayor tiempo entre eliminaciones
            except Exception as e:
                print(f"Fallo eliminación {job.job_id}: {str(e)}")
                # Forzar eliminación vía API
                try:
                    del_url = f"{self.tap_url}/async/{job.job_id}"
                    self.session.delete(del_url)
                except Exception as api_error:
                    print(f"Error API: {str(api_error)}")

# Uso
client = JPASClient()
client.login()
client.force_clean()
