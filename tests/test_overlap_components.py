from multiarrangement.core.batch_generator import BatchGenerator, trial_overlap_components


def test_trials_linked_only_through_shared_pairs():
    assert trial_overlap_components([[0, 1, 2], [3, 4, 5]]) == [1, 1]
    assert trial_overlap_components([[0, 1, 2], [1, 2, 3]]) == [2]
    # a shared item is not a shared pair
    assert trial_overlap_components([[0, 1, 2], [2, 3, 4]]) == [1, 1]


def test_components_are_sorted_largest_first():
    batches = [[0, 1, 2], [1, 2, 3], [3, 4, 5], [4, 5, 0], [0, 4, 5]]
    assert trial_overlap_components(batches) == [3, 2]
    assert trial_overlap_components([]) == []


def test_validate_batches_reports_overlap():
    generator = BatchGenerator(7, 3)
    # trials 0-1 share the pair 1-2 and trials 2-3 the pair 4-5; trial 4 shares no pair with any other
    stats = generator.validate_batches([[0, 1, 2], [1, 2, 3], [3, 4, 5], [0, 4, 5], [0, 3, 6]])
    assert stats['overlap_components'] == 3
    assert stats['largest_overlap_component'] == 2
