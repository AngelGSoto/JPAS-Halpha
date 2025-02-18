from __future__ import print_function
import numpy as np
from astropy.io import fits
from astropy.table import Table
from astropy.stats import sigma_clip
from astropy.modeling import models, fitting
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Selección de emisores Hα en JPAS")
    parser.add_argument("input_fits", help="Archivo FITS de entrada")
    parser.add_argument("--varianceApproach", choices=["Maguio", "Mine", "Fratta"], 
                       default="Fratta", help="Método de cálculo de varianza")
    parser.add_argument("-o", "--output", default="halpha_emitters.csv", 
                       help="Archivo de salida CSV")

    args = parser.parse_args()

    # Leer datos y convertir a pandas
    with fits.open(args.input_fits) as hdul:
        df = Table(hdul[1].data).to_pandas()

    # 1. Calcular pseudo-r y errores (media simple)
    r_bands = ['mag_j0600_cor', 'mag_j0610_cor', 'mag_j0620_cor',
              'mag_j0630_cor', 'mag_j0640_cor', 'mag_j0650_cor']
    r_errors = ['err_j0600_cor', 'err_j0610_cor', 'err_j0620_cor',
               'err_j0630_cor', 'err_j0640_cor', 'err_j0650_cor']
    
    df['pseudo_r'] = df[r_bands].mean(axis=1)
    df['e_pseudo_r'] = np.sqrt(df[r_errors].pow(2).sum(axis=1)) / 6  # Error de la media

    # 2. Calcular colores y sus errores
    df['x_color'] = df['pseudo_r'] - df['mag_isdss_cor']  # (pseudo-r - iSDSS)
    df['y_color'] = df['pseudo_r'] - df['mag_j0660_cor']  # (pseudo-r - J0660)
    
    df['e_x_color'] = np.sqrt(df['e_pseudo_r']**2 + df['err_isdss_cor']**2)
    df['e_y_color'] = np.sqrt(df['e_pseudo_r']**2 + df['err_j0660_cor']**2)

    # 3. Procesar por campo (tile_id)
    results = []
    
    for tile_id, tile_data in df.groupby('tile_id'):
        # A. Ajuste del locus estelar con sigma-clipping
        fitter = fitting.LinearLSQFitter()
        line_init = models.Linear1D()
        
        # Ajuste iterativo (5 iteraciones, sigma=4)
        fitted_line, mask = fitting.FittingWithOutlierRemoval(
            fitter, sigma_clip, sigma=4.0, niter=5)(line_init,
                                                    tile_data['x_color'],
                                                    tile_data['y_color'])
        
        # B. Calcular parámetros clave
        residuals = tile_data['y_color'] - fitted_line(tile_data['x_color'])
        sigma = np.std(residuals)
        m = fitted_line.slope.value
        
        # C. Calcular varianza según método seleccionado
        if args.varianceApproach == "Maguio":
            variance = (
                sigma**2 + 
                (m**2 * tile_data['err_isdss_cor']**2) +
                ((1 - m)**2 * tile_data['e_pseudo_r']**2) +
                tile_data['err_j0660_cor']**2
            )
        elif args.varianceApproach == "Mine":
            variance = (
                sigma**2 +
                (m**2 * tile_data['e_x_color']**2) +
                ((1 - m)**2 * tile_data['e_y_color']**2)
            )
        else:  # Fratta
            variance = (
                sigma**2 +
                (m**2 * tile_data['e_x_color']**2) +
                tile_data['e_y_color']**2
            )
        
        # D. Aplicar criterio de selección (5σ)
        threshold = 5 * np.sqrt(variance)
        ha_mask = residuals >= threshold
        
        # E. Guardar candidatos
        candidates = tile_data[ha_mask].copy()
        candidates['sigma_residual'] = residuals[ha_mask].values
        candidates['variance_method'] = args.varianceApproach
        results.append(candidates)

    # 4. Consolidar y guardar resultados
    final_df = pd.concat(results, ignore_index=True)
    
    # Ordenar columnas y guardar
    output_cols = [
        'number', 'alpha_j2000', 'delta_j2000', 'tile_id',
        'pseudo_r', 'mag_isdss_cor', 'mag_j0660_cor',
        'x_color', 'y_color', 'sigma_residual', 'variance_method',
        'e_pseudo_r', 'err_isdss_cor', 'err_j0660_cor',
        'flags_j0660', 'flags_isdss', 'class_star'
    ]
    
    final_df[output_cols].to_csv(args.output, index=False, float_format="%.4f")
    print(f"Selección completada: {len(final_df)} candidatos guardados en {args.output}")

if __name__ == "__main__":
    main()
