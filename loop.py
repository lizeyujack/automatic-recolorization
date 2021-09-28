import os
def get_filelist(dir, Filelist):
    newDir = dir
    if os.path.isfile(dir):
        Filelist.append(dir)
    elif os.path.isdir(dir):
        for s in os.listdir(dir):
            newDir=os.path.join(dir,s)
            get_filelist(newDir, Filelist)
    return Filelist

if __name__ =='__main__' :
    list = get_filelist('D:\\paper\\fall_detection\\images\\', [])
    # print(len(list))
    # list1 = list[:5]
    # print(list)
    # for e in list1:
    #     # print(e)
    #     list1.append(e)
    # print(list1)
# list00 = ['D:\\上海交大论文\\fall_detection\\images\\rgb_0001.png', 'D:\\上海交大论文\\fall_detection\\images\\rgb_0002.png', 'D:\\上海交大论文\\fall_detection\\images\\rgb_0003.png', 'D:\\上海交大论文\\fall_detection\\images\\rgb_0004.png', 'D:\\上海交大论文\\fall_detection\\images\\rgb_0005.png']
# for i in list00:
#     print('./converted/'+ i[-12:])