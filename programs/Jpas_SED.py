"""
Script definitivo para Generar SEDs JPAS
Autor: Luis A. Gutiérrez Soto
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import argparse
import os
import re

# Configuración de estilo
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 12

def validate_color(color):
    """Valida y corrige el formato del color"""
    color = color.strip().upper()
    if re.match(r'^#[A-F0-9]{6}$', color):
        return color
    elif re.match(r'^[A-F0-9]{6}$', color):
        return f'#{color}'
    elif re.match(r'^#[A-F0-9]{3}$', color):
        return f'#{color[1]*2}{color[2]*2}{color[3]*2}'
    elif re.match(r'^[A-F0-9]{3}$', color):
        return f'#{color[0]*2}{color[1]*2}{color[2]*2}'
    return '#FF0000'  # default color

def load_jpas_filters(filter_file):
    """Carga y valida los filtros JPAS desde CSV"""
    try:
        filters = pd.read_csv(filter_file, dtype={'color_representation': str})
        filters['color_representation'] = filters['color_representation'].apply(validate_color)
        return filters
    
    except Exception as e:
        print(f"❌ Error en archivo de filtros: {str(e)}")
        print("Ejemplo de formato válido: #FF0000")
        raise SystemExit(1)

def mag_to_flux(mag, mag_err, wavelength, zp=2.41):
    """Conversión precisa de magnitud a flujo"""
    c = (10**(-zp/2.5)) / wavelength**2
    flux = c * 10**(-mag/2.5)
    flux_err = (c * 10**(-mag/2.5) * np.log(10)/2.5 ) * mag_err
    return flux, flux_err

def create_sed_plot(row, filters, output_dir, zp):
    """Genera y guarda un gráfico SED individual"""
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.spines[["top", "right"]].set_visible(False)
    
    # Recolectar datos
    wavelengths, fluxes, flux_errs, colors = [], [], [], []
    
    for _, f in filters.iterrows():
        band = f['name'].lower().replace(' ', '')
        mag_col = f"mag_{band}_cor"
        err_col = f"err_{band}_cor"
        
        if mag_col not in row or err_col not in row:
            continue
            
        mag, mag_err = row[mag_col], row[err_col]
        if pd.isna(mag) or pd.isna(mag_err):
            continue
            
        try:
            flux, flux_err = mag_to_flux(mag, mag_err, f['wavelength'], zp)
            wavelengths.append(f['wavelength'])
            fluxes.append(flux)
            flux_errs.append(flux_err)
            colors.append(f['color_representation'])
        except Exception as e:
            print(f"Error al convertir magnitud a flujo: {e}")
            continue
    
    # Validación de consistencia
    assert len(wavelengths) == len(fluxes) == len(flux_errs) == len(colors), "Datos inconsistentes!"
    
    # Graficar
    try:
        ax.errorbar(
            x=wavelengths,
            y=fluxes,
            yerr=flux_errs,
            fmt='o',
            markersize=8,
            ecolor=colors,
            elinewidth=2,
            capsize=4,
            markerfacecolor='white',
            markeredgecolor=colors,
            markeredgewidth=1.5
        )
    except Exception as e:
        print(f"❌ Error al graficar: {str(e)}")
        plt.close()
        return
    
    # Configuración de ejes
    ax.set_xlabel(r'Longitud de onda ($\AA$)', fontsize=14)
    ax.set_ylabel(r'Flujo (erg s$^{-1}$ cm$^{-2}$ $\AA^{-1}$)', fontsize=14)
    ax.set_xlim(3000, 9500)
    ax.set_yscale('log')
    
    # Metadatos
    title_parts = []
    if 'number' in row and pd.notnull(row['number']):
        title_parts.append(f"ID: {row['number']}")
    if 'alpha_j2000' in row and 'delta_j2000' in row:
        title_parts.append(f"({row['alpha_j2000']:.5f}, {row['delta_j2000']:.5f})")
    
    if title_parts:
        ax.set_title("\n".join(title_parts), pad=15, fontsize=12)
    
    # Configurar ticks
    ax.xaxis.set_major_locator(MultipleLocator(1000))
    ax.xaxis.set_minor_locator(MultipleLocator(250))
    ax.yaxis.set_major_formatter(plt.FormatStrFormatter('%.1e'))
    
    # Guardar
    filename = f"sed_{row['number'] if 'number' in row else row.name}.pdf"
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename), bbox_inches='tight')
    plt.close()

def main():
    parser = argparse.ArgumentParser(
        description="Generador de SEDs para datos JPAS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input_csv", help="Archivo CSV con datos JPAS")
    parser.add_argument("-f", "--filters", default="../JPAS-filters.csv",
                      help="Archivo CSV de definición de filtros")
    parser.add_argument("-o", "--output", default="../jpas_seds",
                      help="Directorio de salida para PDFs")
    parser.add_argument("--zp", type=float, default=2.41,
                      help="Zero point para conversión de magnitud")
    
    args = parser.parse_args()
    
    try:
        os.makedirs(args.output, exist_ok=True)
        df = pd.read_csv(args.input_csv)
        filters = load_jpas_filters(args.filters)
        
        print(f"🔄 Procesando {len(df)} objetos...")
        success = 0
        for idx, row in df.iterrows():
            try:
                create_sed_plot(row, filters, args.output, args.zp)
                success += 1
                if success % 50 == 0:
                    print(f"📈 Progreso: {success}/{len(df)} ({success/len(df):.1%})")
            except Exception as e:
                print(f"❌ Error en fila {idx}: {str(e)}")
        
        print(f"\n🎉 Resultado final: {success}/{len(df)} SEDs generados")
        print(f"📂 Directorio de salida: {os.path.abspath(args.output)}")
    
    except Exception as e:
        print(f"\n🔥 Error crítico: {str(e)}")
        print("Solución: Verifique los archivos de entrada y ejecute:")
        print("pip install matplotlib==3.7.1 --force-reinstall")

if __name__ == "__main__":
    main()
    
