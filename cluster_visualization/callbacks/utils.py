"""
Utility functions for callback modules

"""

from typing import Optional, cast
import base64
import io
import numpy as np
import pandas as pd
from numpy.typing import NDArray


# 
def get_idclusters_array(
            upload_contents, 
            upload_filename
        ) -> Optional[NDArray[np.int64]]:
        """Extract cluster IDs from uploaded txt/dat/csv contents."""
        if not upload_contents or not upload_filename:
            return None

        try:
            _, content_string = upload_contents.split(",", 1)
            decoded_text = base64.b64decode(content_string).decode("utf-8", errors="ignore")
            suffix = upload_filename.lower().rsplit(".", 1)[-1]

            if suffix in ("txt", "dat"):
                values = [
                    int(line.strip())
                    for line in decoded_text.splitlines()
                    if line.strip()
                ]
                return np.asarray(values, dtype=int)

            if suffix == "csv":
                df = pd.read_csv(io.StringIO(decoded_text))

                preferred_columns = ["ID_UNIQUE_CLUSTER", "idclusters", "ID", "id"]
                for col in preferred_columns:
                    if col in df.columns:
                        series = pd.to_numeric(df[col], errors="coerce").dropna()
                        arr = series.to_numpy(dtype=np.int64)
                        return cast(NDArray[np.int64], arr)

                numeric_df = df.apply(pd.to_numeric, errors="coerce")
                numeric_cols = numeric_df.columns[numeric_df.notna().any()].tolist()

                if len(numeric_cols) == 1:
                    arr = numeric_df[numeric_cols[0]].dropna().to_numpy(dtype=np.int64)
                    return cast(NDArray[np.int64], arr)
                
                if len(numeric_cols) > 1:
                    values = numeric_df[numeric_cols].to_numpy().ravel()
                    values = values[~pd.isna(values)]
                    return np.asarray(values, dtype=np.int64)

                raise ValueError("No numeric ID column found in CSV.")

            raise ValueError(f"Unsupported file type: {upload_filename}")

        except Exception as e:
            print(f"Error processing uploaded file: {e}")
            return None
