"""
Script to download JPAS data with corrected/uncorrected photometry
Luis A. Gutiérrez Soto
"""
import pyvo.dal
from pyvo.auth import authsession, securitymethods
import getpass
import requests
import pyvo
from astropy.table import Table
import warnings
import os

# Configuración inicial
warnings.simplefilter("ignore")
output_dir = "Data"
os.makedirs(output_dir, exist_ok=True)

# ==================== AUTENTICACIÓN ====================
tap_url = "https://archive.cefca.es/catalogues/vo/tap/jpas-idr202406"

# Credenciales CEFCA
user = input("Username: ")
pwd = getpass.getpass("Password: ")

# Configurar sesión
pyvo.dal.tap.s = requests.Session()
response = pyvo.dal.tap.s.post(
    "https://archive.cefca.es/catalogues/login",
    data={"login": user, "password": pwd, "submit": "Sign+In"},
    headers={"Content-type": "application/x-www-form-urlencoded"}
)
response.raise_for_status()

# ==================== CONSULTA PRINCIPAL ====================
service = pyvo.dal.TAPService(tap_url, session=authsession.AuthSession().set_credentials(
    securitymethods.ANONYMOUS, pyvo.dal.tap.s
))

query = """
SELECT 
    tile_id,
    number,
    alpha_j2000,
    delta_j2000,
    x_image,
    y_image,
    fwhm_world,
    isoarea_world,
    mu_max,
    petro_radius,
    kron_radius,
    mag_aper_cor_6_0[jpas::J0430] AS mag_J0430,  -- Alternativa 1 para pseudo-r
    mag_err_aper_cor_6_0[jpas::J0430] AS err_J0430_cor,
    mag_aper_cor_6_0[jpas::J0450] AS mag_J0450,  -- Alternativa 2 para pseudo-r
    mag_err_aper_cor_6_0[jpas::J0450] AS err_J0450_cor,
    mag_aper_cor_6_0[jpas::J0515] AS mag_J0510,  -- Componente pseudo-r
    mag_err_aper_cor_6_0[jpas::J0515] AS err_J0510_cor,
    mag_aper_cor_6_0[jpas::J0660] AS mag_J0660,  -- Hα
    mag_err_aper_cor_6_0[jpas::J0660] AS err_J0660_cor,
    mag_aper_6_0[jpas::iSDSS] AS mag_i,
    mag_aper_cor_6_0[jpas::iSDSS] AS mag_i_cor,
    mag_err_aper_6_0[jpas::iSDSS] AS err_i,
    mag_err_aper_cor_6_0[jpas::iSDSS] AS err_i_cor,
    mag_aper_6_0,          -- Array de magnitudes sin corregir (56 filtros)
    mag_aper_cor_6_0,      -- Array de magnitudes corregidas (56 filtros)
    mag_err_aper_6_0,      -- Array de errores sin corregir
    mag_err_aper_cor_6_0,  -- Array de errores corregidos
    class_star,
    flags[jpas::J0660] AS flags_J0660,  -- Flags específicos para J0660
    flags[jpas::iSDSS] AS flags_iSDSS    -- Flags específicos para iSDSS
FROM jpas.MagABDualObj
WHERE
    mag_err_aper_6_0[jpas::J0660] < 0.4     -- Error en Hα < 0.4 mag
    AND mag_err_aper_6_0[jpas::iSDSS] < 0.4 -- Error en iSDSS < 0.4 mag
    AND mask_flags[jpas::J0660] = 0         -- Sin máscaras en J0660
    AND mask_flags[jpas::iSDSS] = 0         -- Sin máscaras en iSDSS
    AND flags[jpas::J0660] <= 3             -- Flags aceptables en J0660
    AND flags[jpas::iSDSS] <= 3             -- Flags aceptables en iSDSS
    AND mag_aper_cor_6_0[jpas::iSDSS] BETWEEN 13 AND 23  -- Rango útil
"""

try:
    main_data = service.run_async(query).to_table()
except pyvo.DALQueryError as e:
    print(f"Error detallado: {e.msg}")  # Muestra el mensaje completo del error
    print(f"Consulta problemática:\n{query}")  # Imprime la consulta para debug
    exit(1)

# ==================== BINS DE MAGNITUD ====================
bins = [(13.0,16.0), (16.0,17.5), (17.5,18.5), (18.5,19.5), (19.5,23.0)]

for i, (min_mag, max_mag) in enumerate(bins, 1):
    mask = (main_data["mag_i"] >= min_mag) & (main_data["mag_i"] < max_mag)  # Cambiado mag_iSDSS → mag_i
    main_data[mask].write(
        f"{output_dir}/jpas_bin_{i}_{min_mag}to{max_mag}i.fits", 
        overwrite=True
    )

# ==================== METADATOS DE FILTROS ====================
filter_meta = service.run_async("""
    SELECT filter_id, name, wavelength AS lambda_c, 
           width, kx, color_representation
    FROM jpas.Filter 
    ORDER BY wavelength
""").to_table()

filter_meta.write(f"{output_dir}/jpas_filters_metadata.fits", overwrite=True)

print("""
Descarga completada exitosamente.
Los datos se encuentran organizados en:
- Directorio: Data/
- Archivos principales: jpas_bin_*_*i.fits
- Metadatos de filtros: jpas_filters_metadata.fits
""")
