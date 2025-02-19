"""
Script to download JPAS data with corrected/uncorrected photometry, -- all J-filters
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

# List completa de filtros JPAS
filters = [
    "uJAVA", "J0378", "J0390", "J0400", "J0410", "J0420", "J0430", "J0440",
    "J0450", "J0460", "J0470", "J0480", "J0490", "J0500", "J0510", "J0520",
    "J0530", "J0540", "J0550", "J0560", "J0570", "J0580", "J0590", "J0600",
    "J0610", "J0620", "J0630", "J0640", "J0650", "J0660", "J0670", "J0680",
    "J0690", "J0700", "J0710", "J0720", "J0730", "J0740", "J0750", "J0760",
    "J0770", "J0780", "J0790", "J0800", "J0810", "J0820", "J0830", "J0840",
    "J0850", "J0860", "J0870", "J0880", "J0890", "J0900", "J0910", "J1007",
    "iSDSS"
]

# Create dinamic parts of the query
mag_lines = [f"mag_aper_cor_6_0[jpas::{filt}] AS mag_{filt}_cor" for filt in filters]
err_lines = [f"mag_err_aper_cor_6_0[jpas::{filt}] AS err_{filt}_cor" for filt in filters]
mag_part = ",\n    ".join(mag_lines)
err_part = ",\n    ".join(err_lines)

# Query that include all the J-filtros in the aperture 6 arcseconds
query = f"""
SELECT 
    NUMBER,
    alpha_j2000,
    delta_j2000,
    tile_id,
    {mag_part},
    {err_part},
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
        # Corregir nombre de columna (mag_iSDSS_cor en lugar de mag_isdss_cor)
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
