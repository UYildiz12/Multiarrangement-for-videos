#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <assert.h>

#ifdef _WIN32
  #include <windows.h>
#endif

// ---------------- time in ns -----------------
static inline uint64_t now_ns(void){
#ifdef _WIN32
    LARGE_INTEGER freq, counter;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&counter);
    return (uint64_t)((counter.QuadPart * 1000000000ULL) / (uint64_t)freq.QuadPart);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

// ---------------- bitset utils -----------------
static inline int popcount64(uint64_t x) {
#ifdef _MSC_VER
    return (int)__popcnt64(x);
#else
    return __builtin_popcountll(x);
#endif
}

static inline int ctz64(uint64_t x) {
#ifdef _MSC_VER
    unsigned long idx;
    _BitScanForward64(&idx, x);
    return (int)idx;
#else
    return __builtin_ctzll(x);
#endif
}

// Core algorithm from Greedy_gen.c (simplified for extension)
static PyObject* generate_batches_c(PyObject* self, PyObject* args) {
    int n_videos, batch_size;
    
    if (!PyArg_ParseTuple(args, "ii", &n_videos, &batch_size)) {
        return NULL;
    }
    
    if (n_videos > 255) {
        PyErr_SetString(PyExc_ValueError, "n_videos must be <= 255");
        return NULL;
    }
    
    if (batch_size < 2 || batch_size > n_videos) {
        PyErr_SetString(PyExc_ValueError, "Invalid batch_size");
        return NULL;
    }
    
    // Simplified greedy algorithm core
    uint64_t** rows = calloc(n_videos, sizeof(uint64_t*));
    if (!rows) {
        PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory");
        return NULL;
    }
    
    // Initialize bitsets for uncovered pairs
    int words_per_row = (n_videos + 63) / 64;
    for (int i = 0; i < n_videos; i++) {
        rows[i] = calloc(words_per_row, sizeof(uint64_t));
        if (!rows[i]) {
            // Cleanup on error
            for (int j = 0; j < i; j++) free(rows[j]);
            free(rows);
            PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory");
            return NULL;
        }
        
        // Set all bits except diagonal
        for (int w = 0; w < words_per_row; w++) {
            rows[i][w] = ~0ULL;
        }
        // Clear bit for self (diagonal)
        rows[i][i / 64] &= ~(1ULL << (i % 64));
    }
    
    int total_pairs = n_videos * (n_videos - 1) / 2;
    int uncovered = total_pairs;
    
    PyObject* result = PyList_New(0);
    if (!result) {
        // Cleanup
        for (int i = 0; i < n_videos; i++) free(rows[i]);
        free(rows);
        return NULL;
    }
    
    // Greedy batch construction
    while (uncovered > 0) {
        // Find highest degree vertex as starting point
        int max_deg = -1;
        int start_vertex = 0;
        for (int i = 0; i < n_videos; i++) {
            int deg = 0;
            for (int w = 0; w < words_per_row; w++) {
                deg += popcount64(rows[i][w]);
            }
            if (deg > max_deg) {
                max_deg = deg;
                start_vertex = i;
            }
        }
        
        if (max_deg == 0) break; // All pairs covered
        
        // Build batch starting from highest degree vertex
        int batch[256]; // Max batch size
        batch[0] = start_vertex;
        int batch_len = 1;
        
        // Greedily add vertices that maximize new pair coverage
        while (batch_len < batch_size) {
            int best_vertex = -1;
            int best_gain = -1;
            
            for (int candidate = 0; candidate < n_videos; candidate++) {
                // Check if candidate is already in batch
                int already_in = 0;
                for (int j = 0; j < batch_len; j++) {
                    if (batch[j] == candidate) {
                        already_in = 1;
                        break;
                    }
                }
                if (already_in) continue;
                
                // Count new pairs that would be covered
                int gain = 0;
                for (int j = 0; j < batch_len; j++) {
                    int other = batch[j];
                    int word_idx = other / 64;
                    int bit_idx = other % 64;
                    if (rows[candidate][word_idx] & (1ULL << bit_idx)) {
                        gain++;
                    }
                }
                
                if (gain > best_gain) {
                    best_gain = gain;
                    best_vertex = candidate;
                }
            }
            
            if (best_vertex == -1) {
                // No more beneficial vertices, add any remaining vertex
                for (int candidate = 0; candidate < n_videos; candidate++) {
                    int already_in = 0;
                    for (int j = 0; j < batch_len; j++) {
                        if (batch[j] == candidate) {
                            already_in = 1;
                            break;
                        }
                    }
                    if (!already_in) {
                        best_vertex = candidate;
                        break;
                    }
                }
            }
            
            if (best_vertex == -1) break; // No more vertices available
            
            batch[batch_len++] = best_vertex;
        }
        
        // Mark pairs in this batch as covered
        int new_coverage = 0;
        for (int i = 0; i < batch_len; i++) {
            for (int j = i + 1; j < batch_len; j++) {
                int a = batch[i];
                int b = batch[j];
                int word_a = b / 64;
                int bit_a = b % 64;
                int word_b = a / 64;
                int bit_b = a % 64;
                
                if (rows[a][word_a] & (1ULL << bit_a)) {
                    rows[a][word_a] &= ~(1ULL << bit_a);
                    rows[b][word_b] &= ~(1ULL << bit_b);
                    new_coverage++;
                }
            }
        }
        uncovered -= new_coverage;
        
        // Convert batch to Python list and add to result
        PyObject* py_batch = PyList_New(batch_len);
        if (!py_batch) {
            Py_DECREF(result);
            for (int i = 0; i < n_videos; i++) free(rows[i]);
            free(rows);
            return NULL;
        }
        
        for (int i = 0; i < batch_len; i++) {
            PyObject* item = PyLong_FromLong(batch[i]);
            if (!item) {
                Py_DECREF(py_batch);
                Py_DECREF(result);
                for (int j = 0; j < n_videos; j++) free(rows[j]);
                free(rows);
                return NULL;
            }
            PyList_SetItem(py_batch, i, item);
        }
        
        if (PyList_Append(result, py_batch) < 0) {
            Py_DECREF(py_batch);
            Py_DECREF(result);
            for (int i = 0; i < n_videos; i++) free(rows[i]);
            free(rows);
            return NULL;
        }
        Py_DECREF(py_batch);
    }
    
    // Cleanup
    for (int i = 0; i < n_videos; i++) {
        free(rows[i]);
    }
    free(rows);
    
    return result;
}

// Method definitions
static PyMethodDef GreedyMethods[] = {
    {"generate_batches", generate_batches_c, METH_VARARGS,
     "Generate batches using high-performance C implementation"},
    {NULL, NULL, 0, NULL}  // Sentinel
};

// Module definition
static struct PyModuleDef greedy_c_module = {
    PyModuleDef_HEAD_INIT,
    "greedy_c",
    "High-performance C implementation of greedy batch generation",
    -1,
    GreedyMethods
};

// Module initialization
PyMODINIT_FUNC PyInit_greedy_c(void) {
    PyObject* module;
    
    module = PyModule_Create(&greedy_c_module);
    if (module == NULL) {
        return NULL;
    }
    
    // Import NumPy
    import_array();
    
    return module;
}
