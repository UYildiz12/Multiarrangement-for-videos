// greedy_pairs_windows.c
// Portable C11 implementation: bitsets + lazy max-heap over all k-combinations.
// Works on Windows (MinGW) and POSIX. Avoids clock_gettime on Windows, avoids __int128.
// Compile on MinGW (64-bit recommended):
//   gcc -std=c11 -O3 -march=native -pipe -Wall -Wextra greedy_pairs_windows.c -o greedy_pairs.exe
// Run:
//   ./greedy_pairs.exe <n_items<=255> <batch_size>
// Output:
//   batches_<n>videos_batchsize<k>.txt

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
    // convert to ns carefully to avoid overflow
    return (uint64_t)((counter.QuadPart * 1000000000ULL) / (uint64_t)freq.QuadPart);
#else
    struct timespec ts;
    // CLOCK_MONOTONIC is available on POSIX; on very old systems link with -lrt
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
#endif
}

// ---------------- popcount -------------------
static inline int popcount64(uint64_t x){
#ifdef _MSC_VER
    return (int)__popcnt64(x);
#else
    return __builtin_popcountll(x);
#endif
}

// -------------- pair indexing ---------------
static inline uint32_t pair_index(uint32_t i, uint32_t j, uint32_t n){
    // i < j
    uint32_t prior = i*(n-1u) - (i*(i-1u))/2u;
    return prior + (j - i - 1u);
}

// -------------- gcd & nCk (no 128-bit) ------
static inline uint64_t gcd_u64(uint64_t a, uint64_t b){
    while (b){ uint64_t t = a % b; a = b; b = t; }
    return a;
}

static uint64_t nCk_uint64(uint32_t n, uint32_t k){
    if (k > n) return 0;
    if (k > n - k) k = n - k;
    uint64_t res = 1;
    for (uint32_t i = 1; i <= k; ++i){
        uint64_t num = (uint64_t)(n - k + i);
        uint64_t den = (uint64_t)i;
        uint64_t g1 = gcd_u64(num, den); num /= g1; den /= g1;
        uint64_t g2 = gcd_u64(res, den); res /= g2; den /= g2;
        // after reduction res * num fits for practical ranges (e.g., n<=60 safely)
        res *= num;
    }
    return res;
}

// -------------- combinations -----------------
static int next_combination(uint32_t *a, uint32_t k, uint32_t n){
    if (k == 0) return 0;
    for (int i = (int)k - 1; i >= 0; --i){
        if (a[i] != (uint32_t)(n - k + i)){
            a[i]++;
            for (uint32_t j = i + 1; j < k; ++j) a[j] = a[j-1] + 1;
            return 1;
        }
    }
    return 0;
}

// -------------- max-heap ---------------------
typedef struct { int *ids; int *scores; int size; } MaxHeap;
static inline void heap_swap(MaxHeap *h, int i, int j){ int ti=h->ids[i], ts=h->scores[i]; h->ids[i]=h->ids[j]; h->scores[i]=h->scores[j]; h->ids[j]=ti; h->scores[j]=ts; }
static void heap_sift_down(MaxHeap *h, int i){ for(;;){ int l=2*i+1, r=l+1, b=i; if(l<h->size && h->scores[l]>h->scores[b]) b=l; if(r<h->size && h->scores[r]>h->scores[b]) b=r; if(b==i) break; heap_swap(h,i,b); i=b; }}
static void heap_sift_up(MaxHeap *h, int i){ while(i>0){ int p=(i-1)>>1; if(h->scores[p]>=h->scores[i]) break; heap_swap(h,p,i); i=p; } }
static void heap_build(MaxHeap *h){ for(int i=(h->size>>1)-1;i>=0;--i) heap_sift_down(h,i); }
static void heap_push(MaxHeap *h, int id, int score){ int i=h->size++; h->ids[i]=id; h->scores[i]=score; heap_sift_up(h,i);} 
static int heap_pop(MaxHeap *h, int *id, int *score){ if(h->size==0) return 0; *id=h->ids[0]; *score=h->scores[0]; h->size--; if(h->size>0){ h->ids[0]=h->ids[h->size]; h->scores[0]=h->scores[h->size]; heap_sift_down(h,0);} return 1; }

// -------------- bitset ops -------------------
static inline int recompute_score(const uint64_t *mask, const uint64_t *uncovered, size_t words){
    int s = 0; for (size_t w=0; w<words; ++w) s += popcount64(mask[w] & uncovered[w]); return s; }
static inline int clear_and_count(uint64_t *uncovered, const uint64_t *mask, size_t words){
    int cleared = 0; for (size_t w=0; w<words; ++w){ uint64_t before=uncovered[w]; uint64_t to_clear=before & mask[w]; if(to_clear){ uncovered[w]=before & ~mask[w]; cleared += popcount64(to_clear);} } return cleared; }

int main(int argc, char **argv){
    if (argc < 3){ fprintf(stderr, "Usage: %s <n_items<=255> <batch_size>\n", argv[0]); return 1; }
    uint32_t n = (uint32_t)strtoul(argv[1], NULL, 10);
    uint32_t k = (uint32_t)strtoul(argv[2], NULL, 10);
    if (k==0 || n==0 || k>n){ fprintf(stderr, "Invalid n,k. Need 0 < k <= n.\n"); return 1; }
    if (n > 255){ fprintf(stderr, "n=%u too large for uint8_t item storage (limit 255).\n", n); return 1; }

    uint64_t t0 = now_ns();

    uint32_t pairs_total = n*(n-1u)/2u;
    uint32_t pairs_per_batch = k*(k-1u)/2u;
    size_t words = ((size_t)pairs_total + 63u)/64u;
    uint64_t M = nCk_uint64(n, k);

    fprintf(stderr, "n=%u, k=%u\n", n, k);
    fprintf(stderr, "Total pairs: %u, pairs per batch: %u\n", pairs_total, pairs_per_batch);
    fprintf(stderr, "Candidates: C(%u,%u) = %llu\n", n, k, (unsigned long long)M);
    fprintf(stderr, "Bitset words per mask: %llu (64-bit each)\n", (unsigned long long)words);

    if (M == 0){ return 0; }

    // allocate
    uint64_t need_masks_bytes = (uint64_t)((size_t)M * words * sizeof(uint64_t));
    uint64_t *masks = (uint64_t*)calloc((size_t)M * words, sizeof(uint64_t));
    if (!masks){ fprintf(stderr, "Failed to allocate masks (need ~%llu bytes)\n", (unsigned long long)need_masks_bytes); return 1; }

    uint8_t *items_pool = (uint8_t*)malloc((size_t)M * (size_t)k);
    if (!items_pool){ fprintf(stderr, "Failed to allocate items_pool (~%llu bytes)\n", (unsigned long long)((uint64_t)M * k)); free(masks); return 1; }

    MaxHeap H; H.ids=(int*)malloc((size_t)M * sizeof(int)); H.scores=(int*)malloc((size_t)M * sizeof(int));
    if (!H.ids || !H.scores){ fprintf(stderr, "Failed to allocate heap arrays (~%llu bytes)\n", (unsigned long long)((uint64_t)M * (sizeof(int)+sizeof(int)))); free(items_pool); free(masks); free(H.ids); free(H.scores); return 1; }

    uint64_t *uncovered = (uint64_t*)malloc(words * sizeof(uint64_t));
    if (!uncovered){ fprintf(stderr, "Failed to allocate uncovered.\n"); free(H.ids); free(H.scores); free(items_pool); free(masks); return 1; }
    for (size_t w=0; w<words; ++w) uncovered[w] = ~0ULL;
    if ((pairs_total & 63u) != 0){ unsigned valid = pairs_total & 63u; uint64_t mask = (valid==64u)?~0ULL:((1ULL<<valid)-1ULL); uncovered[words-1]=mask; }

    // generate combinations & masks
    uint64_t gen_start = now_ns();
    uint32_t *comb = (uint32_t*)malloc(k * sizeof(uint32_t));
    for (uint32_t i=0; i<k; ++i) comb[i]=i;

    for (uint64_t cid=0; cid<M; ++cid){
        // store items
        for (uint32_t t=0; t<k; ++t) items_pool[cid*(uint64_t)k + t] = (uint8_t)comb[t];
        // build mask
        uint64_t *cmask = &masks[cid * words];
        for (uint32_t a=0; a<k; ++a){ uint32_t ia=comb[a];
            for (uint32_t b=a+1; b<k; ++b){ uint32_t ib=comb[b];
                uint32_t pidx = (ia<ib)? pair_index(ia,ib,n) : pair_index(ib,ia,n);
                cmask[pidx>>6] |= (1ULL << (pidx & 63));
            }
        }
        H.ids[cid] = (int)cid; H.scores[cid] = (int)pairs_per_batch;
        if (cid + 1 < M){ if (!next_combination(comb, k, n)){ fprintf(stderr, "Internal error: ended combinations early at cid=%llu\n", (unsigned long long)cid); free(comb); free(uncovered); free(H.ids); free(H.scores); free(items_pool); free(masks); return 1; } }
    }
    free(comb);
    uint64_t gen_end = now_ns();

    H.size = (int)M; heap_build(&H);

    uint32_t remaining_pairs = pairs_total;
    uint32_t theoretical_min = (pairs_total + pairs_per_batch - 1u) / pairs_per_batch;
    uint64_t chosen_cap = theoretical_min + theoretical_min/2 + 32;
    uint64_t chosen_cnt = 0;
    uint64_t *chosen_ids = (uint64_t*)malloc(chosen_cap * sizeof(uint64_t));
    if (!chosen_ids){ fprintf(stderr, "Failed to allocate chosen_ids.\n"); free(uncovered); free(H.ids); free(H.scores); free(items_pool); free(masks); return 1; }

    uint64_t greedy_start = now_ns();
    for (;;){
        if (remaining_pairs == 0) break;
        int cid, key; if (!heap_pop(&H, &cid, &key)) break;
        const uint64_t *cmask = &masks[(uint64_t)cid * words];
        int actual = recompute_score(cmask, uncovered, words);
        if (actual == 0) continue;
        if (actual < key){ heap_push(&H, cid, actual); continue; }
        int cleared = clear_and_count(uncovered, cmask, words);
        if (cleared <= 0) continue;
        if (chosen_cnt == chosen_cap){ chosen_cap = chosen_cap*2 + 16; uint64_t *tmp = (uint64_t*)realloc(chosen_ids, chosen_cap * sizeof(uint64_t)); if (!tmp){ fprintf(stderr, "Out of memory expanding chosen_ids.\n"); break; } chosen_ids = tmp; }
        chosen_ids[chosen_cnt++] = (uint64_t)cid; remaining_pairs -= (uint32_t)cleared;
    }
    uint64_t greedy_end = now_ns();

    // write output
    char fname[256]; snprintf(fname, sizeof(fname), "batches_%uvideos_batchsize%u.txt", n, k);
    FILE *f = fopen(fname, "w");
    if (!f){ fprintf(stderr, "Failed to open output file %s\n", fname); }
    else {
        for (uint64_t t=0; t<chosen_cnt; ++t){ uint64_t cid = chosen_ids[t];
            for (uint32_t j=0; j<k; ++j){ if (j) fputs(", ", f); fprintf(f, "%u", (unsigned)items_pool[cid*(uint64_t)k + j]); }
            fputc('\n', f);
        }
        fclose(f);
        printf("Saved batches to %s\n", fname);
    }

    uint64_t t1 = now_ns();

    // stats
    printf("Greedy completed.\n");
    printf("  Number of batches created: %llu\n", (unsigned long long)chosen_cnt);
    printf("  Theoretical minimum batches: %u\n", theoretical_min);
    if (chosen_cnt){ printf("  Actual efficiency: %.3fx\n", (double)theoretical_min / (double)chosen_cnt); }
    printf("Timing (s):\n");
    printf("  Generate candidates: %.3f s\n", (double)(gen_end - gen_start)/1e9);
    printf("  Greedy selection:    %.3f s\n", (double)(greedy_end - greedy_start)/1e9);
    printf("  Total wall time:     %.3f s\n", (double)(t1 - t0)/1e9);

    free(chosen_ids); free(uncovered); free(H.ids); free(H.scores); free(items_pool); free(masks);
    return 0;
}
