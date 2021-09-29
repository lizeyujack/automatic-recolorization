import os
from loop import get_filelist
list00 = get_filelist('D:\\paper\\fall_detection\\images\\', [])
for i in range(0,len(list00)):
    st = "python recolor.py -i " + list00[i]
    print(st)
    os.system(st)
