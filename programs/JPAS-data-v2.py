"""
Script to download JPAS data with corrected/uncorrected photometry
Luis. A. Gutiérrez Soto
"""
import pyvo.dal
from pyvo.auth import authsession, securitymethods
import getpass
import requests
import pyvo
from astropy.table import Table
import warnings
import os

# Ignorar warnings
warnings.simplefilter("ignore")

# Crear directorio Data si no existe
if not os.path.exists("Data"):
    os.makedirs("Data")

# URL del servicio TAP de JPAS
tap_url = "https://archive.cefca.es/catalogues/vo/tap/jpas-idr202406"

# Login (credenciales CEFCA)
user = input("Username: ")
pwd = getpass.getpass("Password: ")
archive_login_url = "https://archive.cefca.es/catalogues/login"
login_args = {"login": user, "password": pwd, "submit": "Sign+In"}
login_header = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}

# Configurar sesión autenticada
pyvo.dal.tap.s = requests.Session()
response = pyvo.dal.tap.s.post(archive_login_url, data=login_args, headers=login_header)
response.raise_for_status()

auth = authsession.AuthSession()
auth.credentials.set(securitymethods.ANONYMOUS, pyvo.dal.tap.s)

# Conectar al servicio TAP
service = pyvo.dal.TAPService(tap_url, session=auth)

# Consulta modificada para incluir ambas fotometrías
query = """
SELECT 
    NUMBER,
    alpha_j2000,
    delta_j2000,
    tile_id,
    mag_aper_cor_6_0[jpas::J0600] AS mag_J0600_cor,
    mag_aper_cor_6_0[jpas::J0610] AS mag_J0610_cor,
    mag_aper_cor_6_0[jpas::J0620] AS mag_J0620_cor,
    mag_aper_cor_6_0[jpas::J0630] AS mag_J0630_cor,
    mag_aper_cor_6_0[jpas::J0640] AS mag_J0640_cor,
    mag_aper_cor_6_0[jpas::J0650] AS mag_J0650_cor,
    mag_err_aper_cor_6_0[jpas::J0600] AS err_J0600_cor,
    mag_err_aper_cor_6_0[jpas::J0610] AS err_J0610_cor,
    mag_err_aper_cor_6_0[jpas::J0620] AS err_J0620_cor,
    mag_err_aper_cor_6_0[jpas::J0630] AS err_J0630_cor,
    mag_err_aper_cor_6_0[jpas::J0640] AS err_J0640_cor,
    mag_err_aper_cor_6_0[jpas::J0650] AS err_J0650_cor,
    mag_aper_cor_6_0[jpas::J0660] AS mag_J0660_cor,
    mag_aper_cor_6_0[jpas::iSDSS] AS mag_iSDSS_cor,
    mag_err_aper_cor_6_0[jpas::J0660] AS err_J0660_cor,
    mag_err_aper_cor_6_0[jpas::iSDSS] AS err_iSDSS_cor,
    flags[jpas::J0660] AS flags_J0660,
    flags[jpas::iSDSS] AS flags_iSDSS,
    mask_flags[jpas::J0660] AS mask_J0660,
    mask_flags[jpas::iSDSS] AS mask_iSDSS,
    class_star
FROM 
    jpas.MagABDualObj 
WHERE 
    mag_err_aper_cor_6_0[jpas::J0600] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0610] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0620] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0630] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0640] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0650] < 0.4
    AND mag_err_aper_cor_6_0[jpas::J0660] < 0.4
    AND mag_err_aper_cor_6_0[jpas::iSDSS] < 0.4
    AND mask_flags[jpas::J0660] = 0 
    AND mask_flags[jpas::iSDSS] = 0          
    AND flags[jpas::J0660] <= 3
    AND flags[jpas::iSDSS] <= 3
"""

try:
    # Ejecutar consulta
    job = service.run_async(query)
    table = job.to_table()
    # Verificar nombres de columnas
    print("Columnas disponibles:", table.colnames)
except pyvo.DALQueryError as e:
    print(f"Error en la consulta: {e}")
    exit()

# Definir los bins de magnitud
bins = [
    (13.0, 16.0),
    (16.0, 17.5),
    (17.5, 18.5),
    (18.5, 19.5),
    (19.5, 23.0),
    (23.0, 24.0)
]

# Guardar cada bin en archivos separados con limpieza de metadatos
for i, (min_mag, max_mag) in enumerate(bins, start=1):
    try:
        mask = (table["mag_isdss_cor"] >= min_mag) & (table["mag_isdss_cor"] < max_mag)
        bin_data = table[mask]
        
        # Limpiar metadatos problemáticos
        bin_data.meta = {}  # Limpiar metadatos de la tabla
        for col in bin_data.columns:
            if 'description' in bin_data[col].meta:
                del bin_data[col].meta['description']
        
        filename = f"Data/jpas_bin_{i}_{min_mag}to{max_mag}i.fits"
        bin_data.write(filename, overwrite=True, format='fits')
        print(f"Bin {i} ({min_mag} ≤ i < {max_mag}): {len(bin_data)} objetos guardados en {filename}")
    
    except KeyError as ke:
        print(f"Error en bin {i}: {ke}")
        print("Verifica los nombres de las columnas en la tabla")
        print("Columnas disponibles:", table.colnames)
        exit()


