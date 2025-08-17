"""
Data processing utilities for multiarrangement experiments.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Union, Any, Optional
import json


class DataProcessor:
    """Handles data processing and analysis for multiarrangement experiments."""
    
    def __init__(self):
        """Initialize the data processor."""
        pass
        
    def calculate_distance_matrix(self, positions: Dict[str, Tuple[float, float]]) -> np.ndarray:
        """
        Calculate pairwise distance matrix from spatial positions.
        
        Args:
            positions: Dictionary mapping item names to (x, y) positions
            
        Returns:
            Symmetric distance matrix
        """
        items = list(positions.keys())
        n_items = len(items)
        
        distance_matrix = np.zeros((n_items, n_items))
        
        for i, item_i in enumerate(items):
            for j, item_j in enumerate(items):
                if i != j:
                    pos_i = positions[item_i]
                    pos_j = positions[item_j]
                    distance = np.sqrt((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2)
                    distance_matrix[i, j] = distance
                    
        return distance_matrix
        
    def create_rdm_dataframe(self, video_names: List[str]) -> pd.DataFrame:
        """
        Create an empty RDM (Representational Dissimilarity Matrix) dataframe.
        
        Args:
            video_names: List of video names
            
        Returns:
            DataFrame with video names as both rows and columns
        """
        df = pd.DataFrame(columns=video_names, index=video_names, dtype=float)
        np.fill_diagonal(df.values, 0.0)
        return df
        
    def update_rdm_with_distances(self, rdm_df: pd.DataFrame, 
                                 video_positions: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
        """
        Update RDM dataframe with new distance measurements.
        
        Args:
            rdm_df: Existing RDM dataframe
            video_positions: Dictionary mapping video names to positions
            
        Returns:
            Updated RDM dataframe
        """
        video_names = list(video_positions.keys())
        
        # Calculate pairwise distances
        for i in range(len(video_names)):
            for j in range(i + 1, len(video_names)):
                video_i = video_names[i]
                video_j = video_names[j]
                
                pos_i = video_positions[video_i]
                pos_j = video_positions[video_j]
                
                # Calculate Euclidean distance
                distance = np.sqrt((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2)
                
                # Handle multiple measurements by averaging
                current_value = rdm_df.loc[video_i, video_j]
                
                if pd.isna(current_value):
                    # First measurement
                    rdm_df.loc[video_i, video_j] = distance
                    rdm_df.loc[video_j, video_i] = distance
                else:
                    # Average with existing measurement(s)
                    if isinstance(current_value, list):
                        current_value.append(distance)
                        avg_distance = np.mean(current_value)
                    else:
                        avg_distance = np.mean([current_value, distance])
                    
                    rdm_df.loc[video_i, video_j] = avg_distance
                    rdm_df.loc[video_j, video_i] = avg_distance
                    
        return rdm_df
        
    def normalize_rdm(self, rdm_df: pd.DataFrame, method: str = 'minmax') -> pd.DataFrame:
        """
        Normalize the RDM using specified method.
        
        Args:
            rdm_df: RDM dataframe
            method: Normalization method ('minmax', 'zscore', 'unit')
            
        Returns:
            Normalized RDM dataframe
        """
        normalized_df = rdm_df.copy()
        
        if method == 'minmax':
            # Scale to 0-1 range
            min_val = rdm_df.values[rdm_df.values > 0].min()
            max_val = rdm_df.values.max()
            normalized_df = (rdm_df - min_val) / (max_val - min_val)
            
        elif method == 'zscore':
            # Z-score normalization
            values = rdm_df.values[rdm_df.values > 0]  # Exclude diagonal
            mean_val = np.mean(values)
            std_val = np.std(values)
            normalized_df = (rdm_df - mean_val) / std_val
            
        elif method == 'unit':
            # Unit vector normalization
            values = rdm_df.values
            norm = np.linalg.norm(values[values > 0])
            normalized_df = rdm_df / norm
            
        else:
            raise ValueError(f"Unknown normalization method: {method}")
            
        # Ensure diagonal remains zero
        np.fill_diagonal(normalized_df.values, 0.0)
        
        return normalized_df
        
    def save_results(self, rdm_df: pd.DataFrame, output_dir: Union[str, Path], 
                    participant_id: str, include_normalized: bool = True) -> Dict[str, Path]:
        """
        Save experimental results in multiple formats.
        
        Args:
            rdm_df: RDM dataframe
            output_dir: Output directory
            participant_id: Participant identifier
            include_normalized: Whether to save normalized versions
            
        Returns:
            Dictionary mapping format names to file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        base_filename = f"participant_{participant_id}"
        saved_files = {}
        
        # Save raw Excel file
        excel_path = output_dir / f"{base_filename}_results.xlsx"
        rdm_df.to_excel(excel_path)
        saved_files['excel'] = excel_path
        
        # Save raw CSV file
        csv_path = output_dir / f"{base_filename}_results.csv"
        rdm_df.to_csv(csv_path)
        saved_files['csv'] = csv_path
        
        # Save NumPy array
        rdm_array = rdm_df.values.astype(float)
        npy_path = output_dir / f"{base_filename}_rdm.npy"
        np.save(npy_path, rdm_array)
        saved_files['numpy'] = npy_path
        
        if include_normalized:
            # Save normalized versions
            for method in ['minmax', 'zscore']:
                try:
                    normalized_df = self.normalize_rdm(rdm_df, method)
                    
                    norm_excel_path = output_dir / f"{base_filename}_results_{method}.xlsx"
                    normalized_df.to_excel(norm_excel_path)
                    saved_files[f'excel_{method}'] = norm_excel_path
                    
                    norm_npy_path = output_dir / f"{base_filename}_rdm_{method}.npy"
                    np.save(norm_npy_path, normalized_df.values.astype(float))
                    saved_files[f'numpy_{method}'] = norm_npy_path
                    
                except Exception as e:
                    print(f"Warning: Could not save normalized data ({method}): {e}")
                    
        return saved_files
        
    def load_results(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load experimental results from file.
        
        Args:
            file_path: Path to results file
            
        Returns:
            RDM dataframe
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Results file not found: {file_path}")
            
        if file_path.suffix.lower() == '.xlsx':
            return pd.read_excel(file_path, index_col=0)
        elif file_path.suffix.lower() == '.csv':
            return pd.read_csv(file_path, index_col=0)
        elif file_path.suffix.lower() == '.npy':
            # Load numpy array and create dataframe with generic labels
            array = np.load(file_path)
            n_items = array.shape[0]
            labels = [f"item_{i}" for i in range(n_items)]
            return pd.DataFrame(array, columns=labels, index=labels)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
            
    def analyze_rdm(self, rdm_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Perform basic analysis of an RDM.
        
        Args:
            rdm_df: RDM dataframe
            
        Returns:
            Dictionary with analysis results
        """
        # Get upper triangle (excluding diagonal)
        upper_triangle = np.triu(rdm_df.values, k=1)
        distances = upper_triangle[upper_triangle > 0]
        
        analysis = {
            'n_items': len(rdm_df),
            'n_distances': len(distances),
            'mean_distance': np.mean(distances),
            'std_distance': np.std(distances),
            'min_distance': np.min(distances),
            'max_distance': np.max(distances),
            'median_distance': np.median(distances),
            'distance_range': np.max(distances) - np.min(distances)
        }
        
        # Find most similar and dissimilar pairs
        indices = np.unravel_index(np.argmin(upper_triangle + np.eye(len(rdm_df)) * np.inf), 
                                  upper_triangle.shape)
        analysis['most_similar_pair'] = (rdm_df.index[indices[0]], rdm_df.columns[indices[1]])
        analysis['most_similar_distance'] = rdm_df.iloc[indices[0], indices[1]]
        
        indices = np.unravel_index(np.argmax(upper_triangle), upper_triangle.shape)
        analysis['most_dissimilar_pair'] = (rdm_df.index[indices[0]], rdm_df.columns[indices[1]])
        analysis['most_dissimilar_distance'] = rdm_df.iloc[indices[0], indices[1]]
        
        return analysis
        
    def save_experiment_metadata(self, metadata: Dict[str, Any], 
                                output_dir: Union[str, Path], 
                                participant_id: str) -> Path:
        """
        Save experiment metadata to JSON file.
        
        Args:
            metadata: Dictionary with experiment metadata
            output_dir: Output directory
            participant_id: Participant identifier
            
        Returns:
            Path to saved metadata file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = output_dir / f"participant_{participant_id}_metadata.json"
        
        # Convert any non-serializable objects to strings
        serializable_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                serializable_metadata[key] = value
            else:
                serializable_metadata[key] = str(value)
                
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_metadata, f, indent=2, ensure_ascii=False)
            
        return metadata_file
