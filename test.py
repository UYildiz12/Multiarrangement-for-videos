import multiarrangement as ma

input_dir = "15audios"

res=ma.multiarrangement_adaptive(input_dir, output_dir="results")
res.vis()
res.savefig("results/rdm_setcover.png", title="Set‑Cover RDM (15 videos)")