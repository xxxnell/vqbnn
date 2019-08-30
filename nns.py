import math
import numpy as np
import tensorflow as tf
from collections import Counter


class ANN:
    """
    Approximate nearest neighbor search for rank 2 vector (i.e., x0 ⊕ x1 ⊕ ...) using LSH.
    """

    def __init__(self, lshs, i=None, xhashs=None, hashxs=None):
        """
        :param lshs: set of LSHs
        :param i: index of x (i.e., x_i)
        :param xhashs: [(x, (hash1, hash2, ...))]
        :param hashxs: ({hash1: [x], ...}, {hash2: [x], ...})
        """
        if xhashs is None:
            xhashs = []
        if hashxs is None:
            hashxs = tuple([{} for _ in range(len(lshs))])

        self.lshs = lshs
        self.xhashs = xhashs
        self.hashxs = hashxs
        self.i = i

    @classmethod
    def every(cls, dims, hash_no, w=None, cache_no=None):
        if w is None:
            w = [0.5] * hash_no

        lshs = []
        for j in range(hash_no):
            lshs.append(LSH(dims, w[j], cache_no))

        anns = [cls(lshs)]
        for i in range(len(dims)):
            anns.append(cls(lshs, i))

        return anns

    def search(self, x):
        hashs = tuple([lsh.hash(x, self.i) for lsh in self.lshs])
        candidates = []
        for hashx, hash in zip(self.hashxs, hashs):
            if hash in hashx:
                candidates += hashx[hash]
        if self.i is None:
            candidates = [tuple(candidate) for candidate in candidates]

        count = Counter(candidates).most_common()
        candidates = [candidate for candidate, n in count if n >= count[0][1]]

        if len(candidates) <= 1:
            nn = next(iter(candidates), None)
        else:
            nn = self.full_search(x, candidates)
        if self.i is None and nn is not None:
            nn = list(nn)

        return nn

    @staticmethod
    def full_search(x, cs):
        normsqrs = []
        for c in cs:
            if isinstance(x, list):
                normsqr = sum([tf.math.square(tf.norm(c_i - x_i)) if c_i is not x_i else 0 for c_i, x_i in zip(c, x)])
            else:
                normsqr = tf.math.square(tf.norm(c - x)) if c is not x else 0
            normsqrs.append(normsqr)

        return cs[tf.math.argmin(normsqrs)]

    def add(self, x):
        hashs = tuple([lsh.hash(x, self.i) for lsh in self.lshs])

        self.xhashs.append((x, hashs))

        for hash, hashx_dict in zip(hashs, self.hashxs):
            if hash in hashx_dict:
                hashx_dict[hash].append(x)
            else:
                hashx_dict[hash] = [x]

    def remove(self, x):
        _hashs = ()
        xhashs = []
        for _x, hashs in self.xhashs:
            if _x == x:
                _hashs = hashs
            else:
                xhashs.append((_x, hashs))
        self.xhashs = xhashs

        for _hash, hashx in zip(_hashs, self.hashxs):
            hashx[_hash].remove(x)
            if len(hashx[_hash]) is 0:
                hashx.pop(_hash, None)

    def is_empty(self):
        return len(self.xhashs) == 0 and all([len(hashx_dict) == 0 for hashx_dict in self.hashxs])


class LSH:
    """
    Stable distribution Locality-sensitive hashing (LSH) for rank 2 vector.
    h(x) = ⌊ (a * x + b) / w ⌋, where a ~ N(0, 1) and b ~ U[0, w] for given w.

    cache: ([(x_0, ax_0), ...], [(x_1, ax_1), ...], ...)

    See https://en.wikipedia.org/wiki/Locality-sensitive_hashing#Stable_distributions or
        http://mlwiki.org/index.php/Euclidean_LSH
    """

    def __init__(self, dims, w, cache_no=None):
        if cache_no is None:
            cache_no = [0] * len(dims)

        a = [self._normal(dim) for dim in dims]
        b = self._uniform(w)

        self.w = w
        self.a = a
        self.b = b
        self.cache = tuple([[] for _ in range(len(dims))])
        self.cache_no = cache_no

    @staticmethod
    def _normal(dim):
        return tf.random.normal(shape=[dim])

    @staticmethod
    def _uniform(w):
        return np.random.uniform(high=w)

    def hash(self, x, i=None):
        if i is None:
            ax = sum([self._ax(x_i, i) for x_i, i in zip(x, range(len(self.a)))])
        else:
            ax = self._ax(x, i)
        return math.ceil((ax + self.b) / self.w)

    def _ax(self, x, i):
        ax = next(iter([ax_i for x_i, ax_i in self.cache[i] if x == x_i]), None)
        if ax is None:
            ax = tf.tensordot(self.a[i], x, 1)
            self.cache[i].append((x, ax))
            if len(self.cache[i]) > self.cache_no[i]:
                self.cache[i].pop()
        return ax