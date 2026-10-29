"""Page-cache residency (mincore) of files under given roots, grouped. Read-only diagnostics, log 47."""
import ctypes, os, sys, collections
libc = ctypes.CDLL(None, use_errno=True)
libc.mmap.restype = ctypes.c_void_p
libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
PG = os.sysconf("SC_PAGE_SIZE")
def resident(path):
    try:
        size = os.path.getsize(path)
        if size == 0: return 0
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return 0
    try:
        addr = libc.mmap(None, size, 1, 1, fd, 0)   # PROT_READ, MAP_SHARED
        if addr in (None, ctypes.c_void_p(-1).value): return 0
        n = (size + PG - 1) // PG
        vec = (ctypes.c_ubyte * n)()
        libc.mincore(ctypes.c_void_p(addr), size, vec)
        libc.munmap(ctypes.c_void_p(addr), size)
        return sum(b & 1 for b in vec) * PG
    finally:
        os.close(fd)
groups = collections.Counter(); files = []
for root in sys.argv[1:]:
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.islink(p): continue
            r = resident(p)
            if r:
                rel = os.path.relpath(p, root).split(os.sep)
                g = os.path.basename(root) + "/" + "/".join(rel[:2] if rel[0] == "nvidia" else rel[:1])
                groups[g] += r; files.append((r, p))
tot = sum(groups.values())
print(f"total resident under {sys.argv[1:]}: {tot/2**20:.0f} MiB")
for g, r in groups.most_common(18):
    print(f"{r/2**20:8.0f} MiB  {g}")
print("-- biggest files --")
for r, p in sorted(files, reverse=True)[:15]:
    print(f"{r/2**20:8.0f} MiB  {p}")
