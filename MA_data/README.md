# MA_data Analysis Reproduction

To regenerate the figures, tables, and statistics bundled with this dataset, run the following command from the repository root:

```
python -m ma_data.reproduce
```

The script sets deterministic seeds, loads the packaged CSV files in `MA_data/`, recreates all figures/CSVs in that folder, and prints the key metrics so you can verify they match `analysis_results.txt`.
