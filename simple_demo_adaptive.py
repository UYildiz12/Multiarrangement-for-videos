import multiarrangement as ma


"""
ma.multiarrangement_adaptive(
    input_dir,
    output_dir="results",
    use_inverse_mds=True,      # optional refinement
    evidence_threshold=0.5,    # stop when all pairs reach this evidence
    min_subset_size=3,         # must be >= 3
    fullscreen=True,          # windowed to match set-cover demo size
)
"""

ma.multiarrangement_adaptive(
    input_dir="C:/Users/user/Desktop/Sounds",
    output_dir="results",
    use_inverse_mds=True,
    evidence_threshold=0.5,
    instructions=["Ahmet"],
    min_subset_size=3,
    fullscreen=True,
)