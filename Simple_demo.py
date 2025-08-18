import multiarrangement as ma

batches = ma.create_batches(15, 8)

input_dir = "15videos"

res=ma.multiarrangement(input_dir, batches, output_dir="results")
res.vis()
res.savefig("results/rdm_setcover.png", title="Set‑Cover RDM (15 videos)")