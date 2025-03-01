import itertools
import random
import time
import tracemalloc
from collections import defaultdict
import heapq

"""
Optimized batch generation algorithm for multi-arrangement experiments.
This version reduces memory usage and improves performance through:
1. Using more efficient data structures
2. Avoiding generation of all possible combinations at once
3. Implementing a smarter greedy selection process
4. Tracking pair coverage more efficiently
"""

def generate_optimal_batches(n_items, batch_size):
    """
    Generate batches where each pair of items appears together at least once,
    while minimizing the number of batches.
    
    Args:
        n_items: Total number of items (videos)
        batch_size: Size of each batch to create
        
    Returns:
        List of batches (each batch is a tuple of item indices)
    """
    # Create all pairs that need to be covered
    items = list(range(n_items))
    all_pairs = set((min(a, b), max(a, b)) for a, b in itertools.combinations(items, 2))
    uncovered_pairs = all_pairs.copy()
    total_pairs = len(all_pairs)
    
    print(f"Total pairs to cover: {total_pairs}")
    
    # Map each item to all pairs it participates in
    item_to_pairs = defaultdict(set)
    for a, b in all_pairs:
        item_to_pairs[a].add((a, b))
        item_to_pairs[b].add((a, b))
    
    batches = []
    batch_count = 0
    
    while uncovered_pairs:
        batch_count += 1
        pairs_covered_so_far = total_pairs - len(uncovered_pairs)
        progress = (pairs_covered_so_far / total_pairs) * 100
        
        print(f"Creating batch {batch_count}... Progress: {progress:.1f}% ({pairs_covered_so_far}/{total_pairs} pairs covered)")
        
        # Start a new batch
        current_batch = []
        current_pairs_covered = set()
        
        # Track candidate items and their value (number of new pairs they would cover)
        candidates = []
        for item in items:
            if item not in current_batch:
                # Value is number of uncovered pairs this item would add with current batch
                new_pairs = sum(1 for pair in item_to_pairs[item] 
                               if pair in uncovered_pairs and 
                               pair not in current_pairs_covered)
                heapq.heappush(candidates, (-new_pairs, item))  # Negative for max-heap
        
        # Build batch incrementally, always adding the most valuable item
        while len(current_batch) < batch_size and candidates:
            _, best_item = heapq.heappop(candidates)
            
            # Skip if item is already in batch
            if best_item in current_batch:
                continue
                
            current_batch.append(best_item)
            
            # Update pairs covered by this batch
            for item in current_batch[:-1]:  # Check with all previous items in batch
                pair = (min(item, best_item), max(item, best_item))
                if pair in uncovered_pairs:
                    current_pairs_covered.add(pair)
            
            # Recalculate values for remaining candidates
            candidates = []
            for item in items:
                if item not in current_batch:
                    # Recalculate value based on current batch
                    value = 0
                    for batch_item in current_batch:
                        pair = (min(item, batch_item), max(item, batch_item))
                        if pair in uncovered_pairs and pair not in current_pairs_covered:
                            value += 1
                    heapq.heappush(candidates, (-value, item))
        
        # If batch is not full but we can't add more items, just keep it as is
        batches.append(tuple(sorted(current_batch)))
        
        # Remove covered pairs from uncovered set
        uncovered_pairs -= current_pairs_covered
    
    return batches

# Example usage with parameters
if __name__ == "__main__":
    # Number of videos in your dataset
    n_videos = 25
    # How many should appear in the screen at once
    batch_size = 8
    
    # Measure performance
    start_time = time.time()
    tracemalloc.start()
    
    batches = generate_optimal_batches(n_videos, batch_size)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    end_time = time.time()
    
    print("Optimized algorithm:")
    print("Number of batches created:", len(batches))
    print("Time taken:", end_time - start_time, "seconds")
    print(f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
    
    # Calculate coverage statistics
    total_pairs = n_videos * (n_videos - 1) // 2
    pairs_per_batch = batch_size * (batch_size - 1) // 2
    theoretical_min_batches = total_pairs / pairs_per_batch
    
    print(f"Coverage efficiency:")
    print(f"  Total pairs to cover: {total_pairs}")
    print(f"  Pairs per batch: {pairs_per_batch}")
    print(f"  Theoretical minimum batches (perfect efficiency): {theoretical_min_batches:.2f}")
    print(f"  Actual efficiency: {theoretical_min_batches / len(batches):.2f}x")
    
    # Shuffle for randomized presentation
    random.shuffle(batches)
    
    # Save to file
    with open(f'batches_{n_videos}videos_batchsize{batch_size}.txt', 'w') as f:
        for batch in batches:
            f.write(', '.join(map(str, batch)) + '\n')
    
    print(f"Batches saved to batches_{n_videos}videos_batchsize{batch_size}.txt")
