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

# Ignorar warnings
warnings.simplefilter("ignore")

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
    obj_id,
    alpha_j2000,
    delta_j2000,
    tile_id,
    mag_aper_6_0[jpas::iSDSS] AS mag_iSDSS,       -- Magnitud sin corregir
    mag_aper_cor_6_0[jpas::iSDSS] AS mag_iSDSS_cor,  -- Magnitud corregida
    mag_err_aper_6_0[jpas::iSDSS] AS err_iSDSS,      -- Error sin corregir
    mag_err_aper_cor_6_0[jpas::iSDSS] AS err_iSDSS_cor, -- Error corregido
    mag_aper_6_0,          -- Array de magnitudes sin corregir (56 filtros)
    mag_aper_cor_6_0,      -- Array de magnitudes corregidas (56 filtros)
    mag_err_aper_6_0,      -- Array de errores sin corregir
    mag_err_aper_cor_6_0,  -- Array de errores corregidos
    class_star,
    flags,
    mask_flags
FROM 
    jpas.MagABDualObj 
WHERE 
    mag_err_aper_6_0[jpas::J0660] < 0.4   -- Filtramos por error sin corregir (o corregido, según prefieras)
    AND mag_err_aper_6_0[jpas::iSDSS] < 0.4
    AND mask_flags = 0 
    AND flags <= 3
"""

try:
    # Ejecutar consulta
    job = service.run_async(query)
    table = job.to_table()
except pyvo.DALQueryError as e:
    print(f"Error en la consulta: {e}")
    exit()

# Definir los bins de magnitud (usando magnitudes sin corregir, pero puedes elegir las corregidas)
bins = [
    (13.0, 16.0),
    (16.0, 17.5),
    (17.5, 18.5),
    (18.5, 19.5),
    (19.5, 23.0)
]

# Guardar cada bin en archivos separados
for i, (min_mag, max_mag) in enumerate(bins, start=1):
    mask = (table["mag_iSDSS"] >= min_mag) & (table["mag_iSDSS"] < max_mag)
    bin_data = table[mask]
    filename = f"Data/jpas_bin_{i}_{min_mag}to{max_mag}i.fits"
    bin_data.write(filename, overwrite=True)
    print(f"Bin {i} ({min_mag} ≤ i < {max_mag}): {len(bin_data)} objetos guardados en {filename}")

# Descargar metadatos de filtros
try:
    filter_query = "SELECT name, central, width FROM jpas.Filter ORDER BY central"
    filter_job = service.run_async(filter_query)
    filter_table = filter_job.to_table()
    filter_table.write("Data/jpas_filters.fits", overwrite=True)
    print("Metadatos de filtros guardados en jpas_filters.fits")
except pyvo.DALQueryError as e:
    print(f"Error al descargar metadatos de filtros: {e}")
