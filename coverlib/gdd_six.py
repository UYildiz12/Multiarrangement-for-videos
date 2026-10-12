"""Direct 3-GDD type6^n for every n>=3, with cooperative resource checks.

Known STS inflation, Jiang1996 §2.3, a verified finite PBD14, and Wilson
weight6 on affine truncations. For n=14+12t>=98, Nagura1952 supplies a prime
5n/18<q<n/3. Then n=3q+r, with r odd and1<=r<q, so every index ingredient
has supported size3,4 or oddq/r. Six smaller prime choices are explicit.
No numerical solver, covering cache or unbounded combinatorial search.
"""
from itertools import combinations
import math


PBD14 = ((0,1,2,3,4),(0,5,6,7),(0,8,9),(0,10,11),(0,12,13),
         (1,5,11,13),(1,6,8,12),(1,7,9,10),(2,5,9),(2,6,11),
         (2,7,12),(2,8,10,13),(3,5,8),(3,6,10),(3,7,13),
         (3,9,11,12),(4,5,10,12),(4,6,9,13),(4,7,8,11))


def _prime(q, check):
    if q<2:return False
    if q%2==0:return q==2
    for d in range(3,math.isqrt(q)+1,2):
        if d%256==3:check()
        if q%d==0:return False
    return True


def _prime_plan(n,check):
    finite={26:7,38:11,50:13,62:17,74:19,86:23}
    if n in finite:return finite[n],n-3*finite[n]
    q=5*n//18+1
    if q%2==0:q+=1
    while 3*q<n:
        check()
        if _prime(q,check):
            r=n-3*q
            if not (1<=r<q and r%2):raise AssertionError("invalid affine prime remainder")
            return q,r
        q+=2
    raise AssertionError("Nagura prime interval failed")


def _basic(n,check,sts):
    if n in (0,1):return ()
    if n<3 or n%6==2:raise ValueError("unsupported basic ingredient")
    if n%3 in (0,1):
        order=2*n+1; deleted=order-1; base=sts(order,check)
        groups=[tuple(x for x in row if x!=deleted) for row in base if deleted in row]
        source=[row for row in base if deleted not in row]; weight=3
    else:
        base=sts(3*n,check)
        groups=[(x,n+x,2*n+x) for x in range(n)]
        source=[row for row in base if len({x%n for x in row})==3]; weight=2
    check()
    relabel={weight*x+a:6*i+weight*j+a for i,group in enumerate(groups)
             for j,x in enumerate(group) for a in range(weight)}
    rows=[]
    for i,(x,y,z) in enumerate(source):
        if i%128==0:check()
        for a in range(weight):
            for b in range(weight):
                rows.append(tuple(sorted((relabel[weight*x+a],relabel[weight*y+b],
                                          relabel[weight*z+(a+b)%weight]))))
    if len(rows)!=6*n*(n-1):raise AssertionError("basic GDD count mismatch")
    check()
    return rows


def _jiang(n,check):
    s=n//4
    pairs=[(r,4*s-r) for r in range(1,2*s)]+[(2*s,4*s+1)]
    g=[(1+r,4*s-r) for r in range(1,s-1)]
    g += [(s+r,3*s+1-r) for r in range(1,s+1)]+[(s,5*s-1)]
    pairs += [(n+a,n+b) for a,b in g]
    modulus=6*n;rows=[]
    for i,(a,b) in enumerate(pairs):
        if i%128==0:check()
        d=b-a
        # Jiang Lemma2.3 exceptional upper endpoint2n+(s-1).
        base=(0,d,(-(3*n-(s-1)))%modulus) if b==9*s-1 else (0,d,n+b)
        for t in range(modulus):
            if t%128==0:check()
            points=[(x+t)%modulus for x in base]
            rows.append(tuple(sorted(6*(x%n)+x//n for x in points)))
    if len(rows)!=6*n*(n-1):raise AssertionError("Jiang GDD count mismatch")
    check()
    return rows


def _index_blocks(q,r,check):
    for row in range(3):
        check()
        yield tuple(row*q+x for x in range(q))
    if r>1:yield tuple(3*q+x for x in range(r))
    for slope in range(q):
        check()
        for intercept in range(q):
            if intercept%128==0:check()
            block=[row*q+(intercept+slope*row)%q for row in range(3)]
            x=(intercept+3*slope)%q
            if x<r:block.append(3*q+x)
            yield tuple(block)


def gdd_six(n,check,sts):
    """Return cross triples plus contiguous groups on0..6n-1.

    Caller validates n and performs finite output/pair preflight before entry.
    n=0/1 means an empty crossing design; n=2 requires separate finite seeds.
    Each generated block lies on three groups; between-group pairs occur once.
    """
    if type(n) is not int or n<0 or n==2:raise ValueError("n>=0 except2 required")
    check()
    if n<2:rows=[]
    elif n%6!=2:rows=_basic(n,check,sts)
    elif n%4==0:rows=_jiang(n,check)
    else:
        if n==14:index_blocks=iter(PBD14)
        else:
            q,r=_prime_plan(n,check)
            index_blocks=_index_blocks(q,r,check)
        rows=[]; ingredients={}
        for i,block in enumerate(index_blocks):
            check()
            h=len(block)
            if h not in ingredients:ingredients[h]=_basic(h,check,sts)
            for j,row in enumerate(ingredients[h]):
                if j%128==0:check()
                rows.append(tuple(sorted(6*block[x//6]+x%6 for x in row)))
    if len(rows)!=6*n*(n-1):raise AssertionError("complete GDD count mismatch")
    check()
    return rows,[tuple(range(6*i,6*i+6)) for i in range(n)]
