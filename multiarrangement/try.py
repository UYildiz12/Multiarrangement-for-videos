import multiarrangement as ml

# Detect number of media files (audio or video)
input_dir = "C:/Users/user/Desktop/Sounds"  # Change to your media folder
n_media = ml.auto_detect_stimuli(input_dir)

# Create batches for all media files
batches = ml.create_batches(n_media, 8)

custom_instructions = [
    "Welcome to the custom experiment!",
    "Arrange the stimuli as you wish.",
    "Press SPACE to continue."
]

result_file = ml.multiarrangement(
    input_dir=input_dir,
    batches=batches,
    output_dir="./results",
    language="tr",  # Uncomment for Turkish instructions
    instructions="default" # Change the custom_instructions for your own
)

print("Results saved to:", result_file)