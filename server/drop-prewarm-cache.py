import os
n=0
for p in open("/opt/parakeet/prewarm.list").read().split():
    try:
        fd=os.open(p,os.O_RDONLY); os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED); os.close(fd); n+=1
    except OSError: pass
print("dropped", n)