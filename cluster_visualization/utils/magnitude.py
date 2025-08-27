"""
Magnitude conversion utilities for CATRED data filtering.

This module provides functionality to convert flux measurements to magnitudes
and apply magnitude-based cuts on CATRED data.
"""

import numpy as np


class Magnitude:
    """Magnitude conversion and filtering utilities."""
    
    band = 'H'

    @staticmethod
    def band_to_reference_magnitude(band, unit):
        """!
        Associate a reference magnitude to a flux density in Jy

        Args:  band  The name of the band of which magnitude one need. Must be 'H'
        Args:  unit Unit as a multiple of Jy (possibilities are Jy, mJy and muJy)
        """

        # Current scheme (private conversation w Bolzonella):
        # reference magnitudes are the same for all bands. Currently, only H is implemented.

        band_refmags = {'Jy':8.9, 'mJy':16.4, 'muJy':23.9}
        all_refmags = {band: band_refmags}

        try:
            magnitude = all_refmags[band][unit]
        except KeyError:
            error_msg = ""
            if band not in all_refmags:
                error_msg += 'Reference magnitude of band ' + band + ' is not registered. '
            if unit not in band_refmags:
                error_msg += 'Unit ' + unit + ' not found. "unit" parameter should '\
                           'be one of the following : "Jy", "mJy", "muJy" '

            if not error_msg:
                error_msg = 'Unexpected KeyError. input band =' + band + ' and input unit = ' + unit

            raise KeyError(error_msg)

        return magnitude

    @staticmethod
    def flux_to_magnitude(flux, band, unit="muJy", error_ratio=0.3):
        """!
        Associate a reference magnitude to a flux density in Jy

        Args: flux The flux requiring conversion to a magnitude
        Args:  band  The name of the band of which magnitude one need. Must be 'H'
        Args:  unit The flux's unit as a multiple of Jy (possibilities are Jy, mJy and muJy). Default choice is muJy
        """
        reference_magnitude = Magnitude.band_to_reference_magnitude(band, unit)

        ratio_badFlux = np.sum(flux<=0)*1.0 / len(flux)
        if (ratio_badFlux >= error_ratio):
            print(f" WARNING: A significant fraction ({np.sum(flux<=0)}/ {len(flux)} >= {error_ratio}) of fluxes are <0.")

        # Replace low flux by NaN (to get NaN mag, not Inf)
        flux[flux<=0] = np.nan

        # compute magnitude (with up to a fraction error_ratio of non-computed magnitudes (flux<0))
        magnitude = -2.5 * np.log10(flux) + reference_magnitude

        return magnitude

    @staticmethod
    def apply_magnitude_cut(catred_data, maglim=24.0, flux_column='FLUX_H_2FWHM_APER', band='H', unit='muJy'):
        """
        Apply magnitude limit cut to CATRED data.
        
        Args:
            catred_data: CATRED data dictionary or astropy Table
            maglim: Magnitude limit (default: 24.0)
            flux_column: Name of flux column to use (default: 'FLUX_H_2FWHM_APER')
            band: Photometric band (default: 'H')
            unit: Flux unit (default: 'muJy')
            
        Returns:
            Filtered CATRED data with magnitude cut applied
        """
        try:
            # Check if flux column exists
            if hasattr(catred_data, 'colnames'):
                # astropy Table
                if flux_column not in catred_data.colnames:
                    print(f"Warning: Flux column '{flux_column}' not found. Available columns: {catred_data.colnames[:10]}...")
                    return catred_data
                flux = catred_data[flux_column]
            elif isinstance(catred_data, dict):
                # Dictionary format
                if flux_column not in catred_data:
                    print(f"Warning: Flux column '{flux_column}' not found in data dictionary")
                    return catred_data
                flux = catred_data[flux_column]
            else:
                print(f"Warning: Unsupported data format for magnitude cut")
                return catred_data
            
            # Convert flux to magnitude
            flux_array = np.array(flux)
            magnitudes = Magnitude.flux_to_magnitude(flux_array, band, unit)
            
            # Apply magnitude cut (keep sources brighter than magnitude limit)
            # Brighter sources have smaller magnitude values
            mask = ~np.isnan(magnitudes) & (magnitudes <= maglim)
            
            n_before = len(flux)
            n_after = np.sum(mask)
            print(f"Debug: Magnitude cut applied - {n_after}/{n_before} sources kept (mag <= {maglim})")
            
            # Apply mask to data
            if hasattr(catred_data, 'colnames'):
                # astropy Table
                return catred_data[mask]
            else:
                # Dictionary format
                filtered_data = {}
                for key, values in catred_data.items():
                    if isinstance(values, (list, np.ndarray)) and len(values) == n_before:
                        filtered_data[key] = np.array(values)[mask].tolist()
                    else:
                        filtered_data[key] = values
                return filtered_data
                
        except Exception as e:
            print(f"Error applying magnitude cut: {e}")
            return catred_data

    @staticmethod
    def get_available_flux_columns():
        """
        Get list of commonly available flux columns in CATRED data.
        
        Returns:
            List of flux column names
        """
        return [
            'FLUX_H_2FWHM_APER',      # H-band 2FWHM aperture (default)
            'FLUX_H_TEMPLFIT',        # H-band template fitting
            'FLUX_H_UNIF',            # H-band uniform
            'FLUX_J_2FWHM_APER',      # J-band 2FWHM aperture
            'FLUX_Y_2FWHM_APER',      # Y-band 2FWHM aperture
            'FLUX_VIS_2FWHM_APER',    # VIS-band 2FWHM aperture
            'FLUX_DETECTION_TOTAL',   # Total detection flux
        ]

    @staticmethod 
    def estimate_magnitude_range(catred_data, flux_column='FLUX_H_2FWHM_APER', band='H', unit='muJy'):
        """
        Estimate magnitude range in the CATRED data for slider configuration.
        
        Args:
            catred_data: CATRED data dictionary or astropy Table
            flux_column: Name of flux column to use
            band: Photometric band
            unit: Flux unit
            
        Returns:
            Tuple of (min_mag, max_mag) or (20, 26) if estimation fails
        """
        try:
            if hasattr(catred_data, 'colnames'):
                # astropy Table
                if flux_column not in catred_data.colnames:
                    return (20, 26)
                flux = catred_data[flux_column]
            elif isinstance(catred_data, dict):
                # Dictionary format
                if flux_column not in catred_data:
                    return (20, 26)
                flux = catred_data[flux_column]
            else:
                return (20, 26)
            
            # Convert flux to magnitude
            flux_array = np.array(flux)
            magnitudes = Magnitude.flux_to_magnitude(flux_array, band, unit)
            
            # Get valid magnitude range
            valid_mags = magnitudes[~np.isnan(magnitudes)]
            if len(valid_mags) > 0:
                min_mag = float(np.min(valid_mags))
                max_mag = float(np.max(valid_mags))
                # Round to reasonable values
                min_mag = max(15, int(min_mag))
                max_mag = min(30, int(max_mag) + 1)
                return (min_mag, max_mag)
            else:
                return (20, 26)
                
        except Exception as e:
            print(f"Error estimating magnitude range: {e}")
            return (20, 26)
