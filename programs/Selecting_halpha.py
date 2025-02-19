"""
Script para selección de emisores Hα en JPAS
Autor: Luis A. Gutiérrez Soto
Versión: 1.1 (JPAS adaptado)
Requisitos: Python 3.8+, astropy, numpy, pandas
"""

from __future__ import print_function
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.table import Table
from astropy.stats import sigma_clip
from astropy.modeling import models, fitting
import argparse
import os

def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description="Selección de emisores Hα en JPAS usando metodología adaptada de S-PLUS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("input_fits", 
                      help="Ruta al archivo FITS de entrada de JPAS")
    parser.add_argument("-o", "--output", 
                      default="./resultados/halpha_candidates.csv",
                      help="Ruta completa para el archivo de salida CSV")
    parser.add_argument("--variance_method", 
                      choices=["Maguio", "Mine", "Fratta"], 
                      default="Fratta",
                      help="Método de cálculo de varianza")
    parser.add_argument("--sigma_threshold", 
                      type=float, default=5.0,
                      help="Umbral de selección en sigmas")
    
    args = parser.parse_args()

    # Crear directorio de salida si no existe
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)

    # 1. Cargar y preparar datos ==============================================
    print(f"\nCargando datos desde: {args.input_fits}")
    with fits.open(args.input_fits) as hdul:
        df = Table(hdul[1].data).to_pandas()

    # 2. Filtros de calidad JPAS ==============================================
    print("Aplicando filtros de calidad...")
    df = df.query(
        "flags_j0660 <= 3 and "
        "mask_j0660 == 0 and "
        "flags_isdss <= 3 and "
        "mask_isdss == 0"
    )

    # 3. Calcular pseudo-r y colores ==========================================
    print("Calculando pseudo-r y colores...")
    
    # Configuración de filtros
    r_bands = ['mag_j0600_cor', 'mag_j0610_cor', 'mag_j0620_cor',
              'mag_j0630_cor', 'mag_j0640_cor', 'mag_j0650_cor']
    r_errors = ['err_j0600_cor', 'err_j0610_cor', 'err_j0620_cor',
               'err_j0630_cor', 'err_j0640_cor', 'err_j0650_cor']
    
    # Calcular pseudo-r con promedio ponderado por SNR²
    weights = 1 / (df[r_errors].values**2)
    df['pseudo_r'] = np.average(df[r_bands].values, axis=1, weights=weights)
    df['e_pseudo_r'] = np.sqrt(1 / np.sum(weights, axis=1))
    
    # Calcular colores y errores
    df['color_x'] = df['pseudo_r'] - df['mag_isdss_cor']  # pseudo-r - iSDSS
    df['color_y'] = df['pseudo_r'] - df['mag_j0660_cor']  # pseudo-r - J0660
    
    df['e_color_x'] = np.sqrt(df['e_pseudo_r']**2 + df['err_isdss_cor']**2)
    df['e_color_y'] = np.sqrt(df['e_pseudo_r']**2 + df['err_j0660_cor']**2)

    # 4. Procesamiento por tile ===============================================
    print("Procesando por tile...")
    all_candidates = []
    
    for tile_id, tile_data in df.groupby('tile_id'):
        # A. Ajuste del locus estelar
        fitter = fitting.LinearLSQFitter()
        model = models.Linear1D()
        
        # Ajuste con sigma-clipping (4σ, 5 iteraciones)
        fitted_model, mask = fitting.FittingWithOutlierRemoval(
            fitter, 
            sigma_clip, 
            sigma=4.0, 
            niter=5
        )(model, tile_data['color_x'], tile_data['color_y'])
        
        # B. Calcular parámetros clave
        residuals = tile_data['color_y'] - fitted_model(tile_data['color_x'])
        sigma_int = np.std(residuals[mask])
        m = fitted_model.slope.value
        b = fitted_model.intercept.value
        
        # C. Calcular varianza total
        if args.variance_method == "Maguio":
            var = (
                sigma_int**2 + 
                m**2 * tile_data['e_color_x']**2 + 
                (1 - m)**2 * tile_data['e_color_y']**2 +
                tile_data['err_j0660_cor']**2
            )
        elif args.variance_method == "Mine":
            var = (
                sigma_int**2 +
                m**2 * tile_data['e_color_x']**2 +
                (1 - m)**2 * tile_data['e_color_y']**2
            )
        else:  # Fratta
            var = (
                sigma_int**2 + 
                m**2 * tile_data['e_color_x']**2 + 
                tile_data['e_color_y']**2
            )
        
        threshold = args.sigma_threshold * np.sqrt(var)
        
        # D. Seleccionar candidatos
        ha_mask = residuals >= threshold
        candidates = tile_data[ha_mask].copy()
        
        # Añadir metadatos del ajuste
        candidates['slope'] = m
        candidates['intercept'] = b
        candidates['sigma_int'] = sigma_int
        candidates['tile_id'] = tile_id
        
        all_candidates.append(candidates)

    # 5. Consolidar y guardar resultados ======================================
    print("\nGuardando resultados...")
    final_df = pd.concat(all_candidates, ignore_index=True)
    
    # Columnas de salida
    output_cols = [
        'number', 'alpha_j2000', 'delta_j2000', 'tile_id',
        'pseudo_r', 'mag_isdss_cor', 'mag_j0660_cor',
        'color_x', 'color_y', 'sigma_int', 'slope', 'intercept',
        'e_pseudo_r', 'err_isdss_cor', 'err_j0660_cor',
        'flags_j0660', 'flags_isdss', 'class_star'
    ]
    
    # Guardar con formato
    final_df[output_cols].to_csv(
        args.output,
        index=False,
        float_format="%.4f",
        encoding='utf-8'
    )
    
    print(f"\n✅ Proceso completado! {len(final_df)} candidatos guardados en:")
    print(f"📄 {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
