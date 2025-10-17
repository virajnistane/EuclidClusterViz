"""
Data loading and caching module for cluster visualization.

This module handles all data loading operations including:
- Merged cluster detection catalogs
- Individual tile data
- CATRED file information and polygons
- SNR range calculations
- Data validation and caching
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from astropy.io import fits
from typing import Dict, Any, Optional


class DataLoader:
    """Handles loading and caching of cluster detection data."""
    
    def __init__(self, config=None):
        """
        Initialize DataLoader with configuration.
        
        Args:
            config: Configuration object with path information
        """
        self.config = config
        self.data_cache = {}
        
        # Import utilities from package structure
        try:
            from cluster_visualization.utils.myutils import get_xml_element
            self.get_xml_element = get_xml_element
            
        except ImportError as e:
            raise ImportError(f"Failed to import utilities: {e}")
    
    def load_data(self, select_algorithm: str = 'PZWAV') -> Dict[str, Any]:
        """
        Load and prepare all data for visualization.
        
        Args:
            select_algorithm: Algorithm choice ('PZWAV' or 'AMICO')
            
        Returns:
            Dict containing all loaded data:
            - data_detcluster_mergedcat: Merged cluster catalog
            - data_detcluster_by_cltile: Individual tile data by tile ID
            - catred_info: CATRED file information DataFrame
            - algorithm: Selected algorithm
            - snr_min/snr_max: SNR range for slider bounds
            - data_dir: Data directory path
            
        Raises:
            FileNotFoundError: If required data files are missing
            ValueError: If algorithm is not supported
        """
        # Check cache first
        if select_algorithm in self.data_cache:
            return self.data_cache[select_algorithm]
            
        print(f"Loading data for algorithm: {select_algorithm}")
        
        # Validate algorithm choice
        if select_algorithm not in ['PZWAV', 'AMICO']:
            print(f"Warning: Unknown algorithm '{select_algorithm}'. Using 'PZWAV' as default.")
            select_algorithm = 'PZWAV'
        
        # Get paths based on configuration
        paths = self._get_paths(select_algorithm)
        
        # Validate critical paths
        self._validate_paths(paths)
        
        # Load data components
        data_detcluster_mergedcat = self._load_data_detcluster_mergedcat(paths)
        data_detcluster_by_cltile = self._load_data_detcluster_by_cltile(paths)
        catred_fileinfo_df = self._load_catred_info(paths)
        effcovmask_fileinfo_df = self._load_effcovmask_info(paths)
        
        # Calculate SNR range for UI slider
        snr_min = float(data_detcluster_mergedcat['SNR_CLUSTER'].min())
        snr_max = float(data_detcluster_mergedcat['SNR_CLUSTER'].max())
        print(f"SNR range: {snr_min:.3f} to {snr_max:.3f}")

        # Calculate redshift range for UI slider
        z_min = float(data_detcluster_mergedcat['Z_CLUSTER'].min())
        z_max = float(data_detcluster_mergedcat['Z_CLUSTER'].max())
        print(f"Redshift range: {z_min:.3f} to {z_max:.3f}")

        # Assemble final data structure
        data = {
            'data_detcluster_mergedcat': data_detcluster_mergedcat,
            'data_detcluster_by_cltile': data_detcluster_by_cltile,
            'catred_info': catred_fileinfo_df,
            'effcovmask_info': effcovmask_fileinfo_df,
            'algorithm': select_algorithm,
            'snr_threshold_lower': None,  # Will be set by UI
            'snr_threshold_upper': None,  # Will be set by UI
            'snr_min': snr_min,
            'snr_max': snr_max,
            'z_min': z_min,
            'z_max': z_max,
            'data_dir': paths['data_dir']
        }
        
        # Cache the data for future requests
        self.data_cache[select_algorithm] = data
        return data
    
    def _get_paths(self, algorithm: str) -> Dict[str, str]:
        """Get file paths based on configuration or fallback."""
        assert self.config, "Configuration is not set"
        paths = {
            'mergedetcat_dir': self.config.mergedetcat_dir,
            'data_dir': self.config.mergedetcat_data_dir,
            'inputs_dir': self.config.mergedetcat_inputs_dir,
            'mergedetcat_xml': self.config.get_mergedetcat_xml(algorithm),
            'rr2_downloads_dir': self.config.rr2_downloads_dir,
            'mosaic_dir': self.config.mosaic_dir,
            'catred_fileinfo_csv': self.config.get_catred_fileinfo_csv(),
            'catred_polygon_pkl': self.config.get_catred_polygons_pkl(),
            'effcovmask_fileinfo_csv': self.config.get_effcovmask_fileinfo_csv(),
            'detfiles_list': self.config.get_detfiles_list(algorithm)
        }
        print("✓ Using configuration-based paths")
        return paths
    
    def _validate_paths(self, paths: Dict[str, str]) -> None:
        """Validate that critical paths exist."""
        critical_paths = ['mergedetcat_xml', 'data_dir']
        
        for path_key in critical_paths:
            path = paths[path_key]
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path_key.replace('_', ' ').title()} not found: {path}")
    
    def _load_data_detcluster_mergedcat(self, paths: Dict[str, str]) -> np.ndarray:
        """Load merged detection catalog from XML and FITS files."""
        det_xml = paths['mergedetcat_xml']
        if not os.path.exists(det_xml):
            raise FileNotFoundError(f"Merged detection XML not found: {det_xml}")
        
        # Extract FITS filename from XML
        fits_filename = self.get_xml_element(det_xml, 'Data/ClustersFile/DataContainer/FileName').text
        fitsfile = os.path.join(paths['data_dir'], fits_filename)
        
        print(f"Loading merged catalog from: {os.path.basename(fitsfile)}")
        with fits.open(fitsfile) as hdul:
            data_merged = hdul[1].data
        
        print(f"Loaded {len(data_merged)} merged clusters")
        return data_merged
    
    def _load_data_detcluster_by_cltile(self, paths: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Load individual tile detection data."""
        detfiles_list_path = paths['detfiles_list']
        if not os.path.exists(detfiles_list_path):
            raise FileNotFoundError(f"Detection files list not found: {detfiles_list_path}")
        
        with open(detfiles_list_path, 'r') as f:
            detfiles_list = json.load(f)
        
        data_by_tile = {}
        for file in detfiles_list:
            # Extract tile information from XML files
            xml_path = os.path.join(paths['inputs_dir'], file) if 'inputs/' not in file else os.path.join(paths['mergedetcat_dir'], file)
            tile_file = self.get_xml_element(xml_path, 'Data/SpatialInformation/DataContainer/FileName').text
            with open(os.path.join(paths['data_dir'], tile_file), 'r') as tf:
                tile_info = json.load(tf)
            tile_id = tile_info['TILE_ID']

            fits_file = self.get_xml_element(xml_path, 'Data/ClustersFile/DataContainer/FileName').text
            
            for i in os.listdir(paths['inputs_dir']):
                try:
                    assert 'DENSITIES' in self.get_xml_element(os.path.join(paths['inputs_dir'], i), 'Data/PZWavDensFile/DataContainer/FileName').text
                    assert self.get_xml_element(os.path.join(paths['inputs_dir'], i), 'Data/SpatialInformation/DataContainer/FileName').text ==  tile_file
                    dens_xml = i
                    dens_fits = self.get_xml_element(os.path.join(paths['inputs_dir'], i), 'Data/PZWavDensFile/DataContainer/FileName').text
                except:
                    dens_xml = None
                    dens_fits = None
                    pass

            # Load FITS data for this tile
            fits_path = os.path.join(paths['data_dir'], fits_file)
            with fits.open(fits_path) as hdul:
                tile_data = hdul[1].data
            
            data_by_tile[tile_id] = {
                'detxml_file': xml_path,
                'detfits_file': os.path.join(paths['data_dir'], fits_file),
                'cltiledef_file': os.path.join(paths['data_dir'], tile_file),
                'densxml_file': os.path.join(paths['inputs_dir'], dens_xml) if dens_xml else None,
                'densfits_file': os.path.join(paths['data_dir'], dens_fits) if dens_fits else None,
                'detfits_data': tile_data
            }
        
        data_by_tile = dict(sorted(data_by_tile.items()))
        print(f"Loaded {len(data_by_tile)} individual tiles")
        return data_by_tile
    
    def _load_catred_info(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Load CATRED file information and polygon data."""
        catred_fileinfo_csv = paths['catred_fileinfo_csv']
        catred_polygon_pkl = paths['catred_polygon_pkl']
        
        # Load CSV file info or generate it if it doesn't exist
        catred_fileinfo_df = pd.DataFrame()
        if os.path.exists(catred_fileinfo_csv):
            print(f'catred_fileinfo.csv already exists in {os.path.dirname(catred_fileinfo_csv)}')
            catred_fileinfo_df = pd.read_csv(catred_fileinfo_csv)
            catred_fileinfo_df.set_index('tileid', inplace=True)
            print("Loaded catred file info")
        else:
            print(f'catred_fileinfo.csv does not exist in {os.path.dirname(catred_fileinfo_csv)}')
            catred_fileinfo_df = self._generate_catred_fileinfo(paths)

        
        # Load polygon data or generate it if it doesn't exist
        if os.path.exists(catred_polygon_pkl) and not catred_fileinfo_df.empty:
            with open(catred_polygon_pkl, 'rb') as f:
                catred_fileinfo_dict = pickle.load(f)
            catred_fileinfo_df['polygon'] = pd.Series(catred_fileinfo_dict)
            print("Loaded catred polygons")
        elif not catred_fileinfo_df.empty:
            print(f"catred polygons not found at {catred_polygon_pkl}")
            catred_fileinfo_df = self._generate_catred_polygons(catred_fileinfo_df, paths)
        else:
            print("Warning: Cannot generate polygons - catred_fileinfo_df is empty")
        
        return catred_fileinfo_df
    
    def _generate_catred_fileinfo(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Generate catred_fileinfo.csv from XML files. """
        print('Processing catred XML files to create catred_fileinfo dictionary')
        
        # Get catred directory from config
        if self.config and hasattr(self.config, 'catred_dir'):
            catred_dir = self.config.catred_dir
        else:
            # Fallback to rr2_downloads/DpdLE3clFullInputCat
            catred_dir = os.path.join(os.path.dirname(paths['catred_fileinfo_csv']), 'DpdLE3clFullInputCat')
        
        if not os.path.exists(catred_dir):
            print(f"Warning: CATRED directory not found at {catred_dir}")
            return pd.DataFrame()
        
        # Get list of XML files
        catredxmlfiles = [i for i in os.listdir(catred_dir) if i.endswith('.xml')]
        
        if not catredxmlfiles:
            print(f"Warning: No XML files found in {catred_dir}")
            return pd.DataFrame()
        
        print(f"Found {len(catredxmlfiles)} CATRED XML files")
        
        catred_fileinfo = {}
        for catredxmlfile in catredxmlfiles:
            try:
                # Extract tile ID from XML
                mertileid = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), 
                    'Data/TileIndex'
                ).text
                
                catred_fileinfo[mertileid] = {}
                catred_fileinfo[mertileid]['xml_file'] = os.path.join(catred_dir, catredxmlfile)

                # Extract FITS file name from XML
                catred_fitsfile = self.get_xml_element(
                    os.path.join(catred_dir, catredxmlfile), 
                    'Data/Catalog/DataContainer/FileName'
                ).text
                catred_fileinfo[mertileid]['fits_file'] = os.path.join(catred_dir, catred_fitsfile)
                
            except Exception as e:
                print(f"Warning: Failed to process {catredxmlfile}: {e}")
                continue

        if not catred_fileinfo:
            print("Warning: No valid CATRED file information could be extracted")
            return pd.DataFrame()

        # Create DataFrame
        catred_fileinfo_df = pd.DataFrame.from_dict(catred_fileinfo, orient='index')
        catred_fileinfo_df.index.name = 'tileid'
        catred_fileinfo_df.index = catred_fileinfo_df.index.astype(int)
        catred_fileinfo_df = catred_fileinfo_df[['xml_file', 'fits_file']]
        
        print(f"Generated catred_fileinfo for {len(catred_fileinfo_df)} tiles")
        
        # Save the DataFrame to a CSV file
        output_csv = paths['catred_fileinfo_csv']
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        catred_fileinfo_df.to_csv(output_csv, index=True)
        print(f"Saved catred_fileinfo.csv to {output_csv}")
        
        return catred_fileinfo_df
    
    def _generate_catred_polygons(self, catred_fileinfo_df: pd.DataFrame, paths: Dict[str, str]) -> pd.DataFrame:
        """Generate catred_polygons_by_tileid.pkl from XML files (based on notebook cells 25-26)."""
        print('Extracting polygons from XML files and saving to catred_fileinfo_df')
        
        # Import shapely here to avoid import issues if not needed
        try:
            from shapely.geometry import Polygon as ShapelyPolygon
        except ImportError:
            print("Warning: Shapely not available - cannot generate polygon data")
            return catred_fileinfo_df
        
        def extract_polygon_from_xml(xml_file):
            """Extract polygon from CATRED XML file."""
            try:
                merpolygon = self.get_xml_element(xml_file, 'Data/SpatialCoverage/Polygon')
                catred_vertices = []
                vertices = merpolygon.findall('Vertex')
                for vertex in vertices:
                    coords = (float(vertex.find('C1').text), float(vertex.find('C2').text))
                    catred_vertices.append(coords)
                return ShapelyPolygon(catred_vertices)
            except Exception as e:
                print(f"Warning: Failed to extract polygon from {xml_file}: {e}")
                return None
        
        # Make sure the 'polygon' column exists in the DataFrame
        if 'polygon' not in catred_fileinfo_df.columns:
            catred_fileinfo_df['polygon'] = None
            
        # Apply the function to each row in the DataFrame to populate the 'polygon' column
        catred_fileinfo_df['polygon'] = catred_fileinfo_df['xml_file'].apply(extract_polygon_from_xml)
        
        # Remove rows where polygon extraction failed
        initial_count = len(catred_fileinfo_df)
        catred_fileinfo_df = catred_fileinfo_df.dropna(subset=['polygon'])
        final_count = len(catred_fileinfo_df)
        
        if final_count < initial_count:
            print(f"Warning: {initial_count - final_count} polygons could not be extracted")
        
        if final_count == 0:
            print("Error: No valid polygons could be extracted")
            return catred_fileinfo_df
        
        # Make a dict of polygon values and save it to a pickle file
        catred_fileinfo_dict = catred_fileinfo_df[['polygon']].to_dict(orient='index')
        for key, val in catred_fileinfo_dict.items():
            catred_fileinfo_dict[key] = val['polygon']  # Extract the ShapelyPolygon object from the dict
            
        output_pickle = paths['catred_polygon_pkl']
        os.makedirs(os.path.dirname(output_pickle), exist_ok=True)
        
        with open(output_pickle, 'wb') as f:
            pickle.dump(catred_fileinfo_dict, f)
            
        print(f"Generated and saved {final_count} catred polygons to {output_pickle}")
        
        return catred_fileinfo_df
    
    def _load_effcovmask_info(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Load effective coverage mask file info, generating if not exists (based on notebook cell 29)."""
        effcovmask_fileinfo_csv = paths['effcovmask_fileinfo_csv']
        
        # Check if CSV file exists
        if os.path.exists(effcovmask_fileinfo_csv):
            print(f"effcovmask_fileinfo.csv already exists in {os.path.dirname(effcovmask_fileinfo_csv)}")
            effcovmask_fileinfo_df = pd.read_csv(effcovmask_fileinfo_csv)
            effcovmask_fileinfo_df.set_index('tileid', inplace=True)
            print('effcovmask_fileinfo loaded from CSV file')
            return effcovmask_fileinfo_df
        else:
            print(f"effcovmask_fileinfo.csv not found at {effcovmask_fileinfo_csv}")
            return self._generate_effcovmask_fileinfo(paths)
    
    def _generate_effcovmask_fileinfo(self, paths: Dict[str, str]) -> pd.DataFrame:
        """Generate effcovmask_fileinfo.csv from XML files (based on notebook cell 29)."""
        print('Processing effective coverage mask XML files to create effcovmask_fileinfo dictionary')
        
        # Get effcov_mask_dir from config
        if self.config and hasattr(self.config, 'effcov_mask_dir'):
            effcov_mask_dir = self.config.effcov_mask_dir
        else:
            # Fallback to rr2_downloads/DpdHealpixEffectiveCoverageVMPZ
            effcov_mask_dir = os.path.join(os.path.dirname(paths['effcovmask_fileinfo_csv']), 'DpdHealpixEffectiveCoverageVMPZ')
        
        if not os.path.exists(effcov_mask_dir):
            print(f"Warning: Effective coverage mask directory not found at {effcov_mask_dir}")
            return pd.DataFrame()
        
        # Get list of XML files (based on notebook: files with 'DpdHealpixEffectiveCoverageVMPZ' in name)
        effcovxmlfiles = [i for i in os.listdir(effcov_mask_dir) if i.endswith('.xml') and 'DpdHealpixEffectiveCoverageVMPZ' in i]
        
        if not effcovxmlfiles:
            print(f"Warning: No effective coverage XML files found in {effcov_mask_dir}")
            return pd.DataFrame()
        
        print(f"Found {len(effcovxmlfiles)} effective coverage XML files")
        
        effcov_fileinfo = {}
        for effcovxmlfile in effcovxmlfiles:
            try:
                # Extract tile ID from XML (different path than catred)
                mertileid = self.get_xml_element(
                    os.path.join(effcov_mask_dir, effcovxmlfile), 
                    'Data/EffectiveCoverageMaskHealpixParams/PatchTileList/TileIndexList'
                ).text
                
                effcov_fileinfo[mertileid] = {}
                effcov_fileinfo[mertileid]['xml_file'] = os.path.join(effcov_mask_dir, effcovxmlfile)

                # Extract FITS file name from XML (different path than catred)
                effcov_fitsfile = self.get_xml_element(
                    os.path.join(effcov_mask_dir, effcovxmlfile), 
                    'Data/EffectiveCoverageMaskHealpix/DataContainer/FileName'
                ).text
                effcov_fileinfo[mertileid]['fits_file'] = os.path.join(effcov_mask_dir, effcov_fitsfile)
                
            except Exception as e:
                print(f"Warning: Failed to process {effcovxmlfile}: {e}")
                continue

        if not effcov_fileinfo:
            print("Warning: No valid effective coverage file information could be extracted")
            return pd.DataFrame()

        # Create DataFrame
        effcov_fileinfo_df = pd.DataFrame.from_dict(effcov_fileinfo, orient='index')
        effcov_fileinfo_df.index.name = 'tileid'
        effcov_fileinfo_df.index = effcov_fileinfo_df.index.astype(int)
        effcov_fileinfo_df = effcov_fileinfo_df[['xml_file', 'fits_file']]
        
        print(f"Generated effcovmask_fileinfo for {len(effcov_fileinfo_df)} tiles")
        
        # Save the DataFrame to a CSV file
        output_csv = paths['effcovmask_fileinfo_csv']
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
        effcov_fileinfo_df.to_csv(output_csv, index=True)
        print(f"Saved effcovmask_fileinfo.csv to {output_csv}")
        
        return effcov_fileinfo_df
    
    def regenerate_catred_fileinfo(self, algorithm: str = 'PZWAV', force: bool = False) -> pd.DataFrame:
        """
        Manually regenerate catred_fileinfo.csv file.
        
        Args:
            algorithm: Algorithm choice ('PZWAV' or 'AMICO')
            force: If True, regenerate even if file already exists
            
        Returns:
            Generated catred_fileinfo DataFrame
        """
        paths = self._get_paths(algorithm)
        catred_fileinfo_csv = paths['catred_fileinfo_csv']
        
        if os.path.exists(catred_fileinfo_csv) and not force:
            print(f"catred_fileinfo.csv already exists at {catred_fileinfo_csv}")
            print("Use force=True to regenerate anyway")
            return pd.read_csv(catred_fileinfo_csv).set_index('tileid')
        
        if force and os.path.exists(catred_fileinfo_csv):
            print(f"Force regenerating catred_fileinfo.csv (overwriting existing file)")
        
        return self._generate_catred_fileinfo(paths)
    
    def regenerate_effcovmask_fileinfo(self, algorithm: str = 'PZWAV', force: bool = False) -> pd.DataFrame:
        """
        Manually regenerate effcovmask_fileinfo.csv file.
        
        Args:
            algorithm: Algorithm choice ('PZWAV' or 'AMICO')
            force: If True, regenerate even if file already exists
            
        Returns:
            Generated effcovmask_fileinfo DataFrame
        """
        paths = self._get_paths(algorithm)
        effcovmask_fileinfo_csv = paths['effcovmask_fileinfo_csv']
        
        if os.path.exists(effcovmask_fileinfo_csv) and not force:
            print(f"effcovmask_fileinfo.csv already exists at {effcovmask_fileinfo_csv}")
            print("Use force=True to regenerate anyway")
            return pd.read_csv(effcovmask_fileinfo_csv).set_index('tileid')
        
        if force and os.path.exists(effcovmask_fileinfo_csv):
            print(f"Force regenerating effcovmask_fileinfo.csv (overwriting existing file)")
        
        return self._generate_effcovmask_fileinfo(paths)
    
    def clear_cache(self) -> None:
        """Clear the data cache to free memory."""
        self.data_cache.clear()
        print("Data cache cleared")
    
    def get_cached_algorithms(self) -> list:
        """Get list of currently cached algorithms."""
        return list(self.data_cache.keys())
