"""Bounded, reproducible candidates; every result needs independent certification."""
import itertools
import random
from coverlib.recursive import transversal_design
from coverlib.certificates import certify_schedule


def shared_hole_cover(g, n, h, k, outer, inner):
    """Inflate outer groups and fill each group together with h common points."""
    if not 0 < h < k or n+h < k:
        raise ValueError('require 0 < h < k and n+h >= k')
    if not certify_schedule(g,k,outer).complete or not certify_schedule(n+h,k,inner).complete:
        raise ValueError('shared-hole ingredients must be complete covers')
    td=transversal_design(k,n)
    result=[]
    for block in outer:
        for row in td:
            result.append(tuple(block[j]*n+row[j] for j in range(k)))
    for group in range(g):
        for block in inner:
            result.append(tuple(group*n+x if x<n else g*n+x-n for x in block))
    after=certify_schedule(g*n+h,k,result)
    if not after.complete or len(result)!=len(outer)*n*n+g*len(inner):
        raise AssertionError('shared-hole construction failed validation')
    return result


def puncture_cover(source_v, v, k, blocks, seed):
    """Delete several points, then pad surviving blocks greedily to size k."""
    if not k <= v < source_v or not certify_schedule(source_v,k,blocks).complete:
        raise ValueError('puncturing requires a complete source cover and k <= v < source_v')
    rng=random.Random(seed)
    retained=rng.sample(range(source_v),v)
    relabel={x:j for j,x in enumerate(retained)}
    work=list({tuple(sorted(relabel[x] for x in block if x in relabel)) for block in blocks})
    work=[b for b in work if len(b)>=2]
    counts=[[0]*v for _ in range(v)]
    freq=[0]*v
    for block in work:
        for x in block:freq[x]+=1
        for x,y in itertools.combinations(block,2):counts[x][y]+=1;counts[y][x]+=1
    rng.shuffle(work)
    for index,raw in enumerate(work):
        block=list(raw)
        while len(block)<k:
            candidates=[x for x in range(v) if x not in block]
            x=min(candidates,key=lambda x:(tuple(sorted((counts[x][z] for z in block),reverse=True)),freq[x],rng.random()))
            for z in block:counts[x][z]+=1;counts[z][x]+=1
            freq[x]+=1;block.append(x)
        work[index]=tuple(sorted(block))
    result=sorted(set(work))
    if not certify_schedule(v,k,result).complete:
        raise AssertionError('puncturing failed coverage validation')
    return result


def neutral_item_walk(v,k,blocks,seed,max_moves=80):
    """Permit equal-quality item transfers to escape strictly improving traps."""
    if isinstance(max_moves,bool) or not isinstance(max_moves,int) or max_moves<0:
        raise ValueError('max_moves must be a nonnegative integer')
    before=certify_schedule(v,k,blocks)
    if not before.complete:
        raise ValueError('neutral walks require a complete cover')
    rng=random.Random(seed)
    work=sorted(tuple(sorted(b)) for b in blocks)
    present=set(work)
    counts=[[0]*v for _ in range(v)]
    freq=[0]*v
    for block in work:
        for x in block:freq[x]+=1
        for x,y in itertools.combinations(block,2):counts[x][y]+=1;counts[y][x]+=1
    seen={tuple(work)}
    best=list(work)
    def item_key():return tuple(sorted((abs(v*r-k*len(work)) for r in freq),reverse=True))
    best_key=item_key()
    for _ in range(max_moves):
        if max(freq)-min(freq)<=1:break
        order=list(range(len(work)));rng.shuffle(order)
        strict=[];neutral=[]
        for index in order:
            block=work[index]
            for x in block:
                rest=tuple(z for z in block if z!=x)
                removed=sorted(counts[x][z] for z in rest)
                if removed[0]<2:continue
                for y in range(v):
                    if y in block or freq[x]<=freq[y]:continue
                    replacement=tuple(sorted(rest+(y,)))
                    if replacement in present:continue
                    if sorted(counts[y][z]+1 for z in rest)!=removed:continue
                    next_state=tuple(sorted((present-{block})|{replacement}))
                    if next_state in seen:continue
                    move=(index,x,y,rest,replacement,next_state)
                    (strict if freq[x]>=freq[y]+2 else neutral).append(move)
            if strict:break
        options=strict or neutral
        if not options:break
        index,x,y,rest,replacement,state=rng.choice(options)
        seen.add(state);present.remove(work[index]);present.add(replacement);work[index]=replacement
        for z in rest:counts[x][z]-=1;counts[z][x]-=1;counts[y][z]+=1;counts[z][y]+=1
        freq[x]-=1;freq[y]+=1
        key=item_key()
        if key<best_key:best=list(work);best_key=key
    result=sorted(best)
    after=certify_schedule(v,k,result)
    if (not after.complete or after.b!=before.b or after.pair_histogram!=before.pair_histogram
            or after.item_deviation_profile>before.item_deviation_profile):
        raise AssertionError('neutral walk violated its preservation contract')
    return result
