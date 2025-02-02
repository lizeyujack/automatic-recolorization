#!/usr/bin/env python3
"""
Encodes an RGB image into grayscale + color cues.
"""


import os, sys
import argparse
# from typing_extensions import ParamSpecArgs
import cv2
import numpy as np
import math
import random
from skimage import color
from sklearn.cluster import KMeans
from PIL import Image
import ar_utils
import importlib


class Encoder(object):
    def __init__(self, output_path="intermediate_representation", method=ar_utils.methods[0],
                 size=256, p=0, grid_size=10, plot=False, quantize=0) -> None:
        self.methods = ar_utils.methods
        self.method = method
        self.watch = False
        self.size = size
        # set default size for global mode
        if self.method == self.methods[2]:
            self.size = 256
        self.p = p
        self.grid_size = grid_size
        # self.input_path = input_path
        self.output_path = output_path
        self.plot = plot
        self.quantize_k = quantize

        # lower CPU priority (to not freeze PC), unix only
        # os.nice(19)
        
        try:
            os.makedirs(self.output_path, exist_ok=True)
        except FileExistsError:
            pass

        sys.path.insert(1, os.path.abspath("./interactive-deep-colorization/caffe_files"))
        os.environ['GLOG_minloglevel'] = '2'  # supress Caffe verbose prints

    def main(self):
        parser = argparse.ArgumentParser(prog='Recolor Encoder',
                                         description='Encodes images, to be decoded by Decoder')

        parser.add_argument('-o', '--output_path', action='store', dest='output_path', type=str,
                            default='intermediate_representation',
                            help='The path to the folder or file, where the grayscale version and color information will be written to')
        parser.add_argument('-i', '--input_path', action='store', dest='input_path', type=str, default='input_images',
                            help='Path to individual image, or folder with images')
        parser.add_argument('-m', '--method', action='store', dest='method', type=str, default=self.methods[0],
                            help='The colorization method to use. Possible values: \"' + ', '.join(self.methods) + '\"')
        parser.add_argument('-w', '--watch', dest='watch', help='watch input folder for new images', action='store_true')

        # for ideepcolor-px
        parser.add_argument('-s', '--size', action='store', dest='size', type=int, default=256,
                            help='Size of the indermediate mask to store the color pixels. Power of 2. \
                            The bigger, the more accurate the result, but requires more storage, and RAM capacity (decoder) \
                            (For 2048 up to 21GB RAM)')
        parser.add_argument('-g', '--grid_size', action='store', dest='grid_size', type=int, default=10,
                            help='Spacing between color pixels in intermediate mask (--size)  1: fill every spot in mask.  0: dont use any color pixel ')
        parser.add_argument('-p', '--p', action='store', dest='p', type=int, default=0,
                            help='The "radius" the color values will have. \
                            A higher value means one color pixel will later cover multiple gray pixels. Default: 0')
        parser.add_argument('-plt', '--plot', dest='plot', help='Generate Plots for visualization', action='store_true')
        parser.add_argument('-q', '--quantize', dest='quantize', action='store', type=int, default=0, 
                            help='Quantize Pixel values. Number of bins. Default: not used (0), off. ')

        args = parser.parse_args()
        self.watch = args.watch
        self.size = args.size
        self.grid_size = args.grid_size
        self.p = args.p
        self.output_path = args.output_path
        self.method = args.method
        self.plot = args.plot
        self.quantize_k = args.quantize

        try:
            os.makedirs(self.output_path, exist_ok=True)
        except FileExistsError:
            pass

        # TODO: implement watch functionality
        if not os.path.isdir(args.input_path):
            try:
                Image.open(args.input_path) # Just to test if file is image
                self.encode(args.input_path)
            except IOError as err:
                print("Error: File is not a image file: " + args.input_path)
        else:
            for fil in os.scandir(args.input_path):
                if os.path.isdir(fil):
                    continue
                fil.path
                try:
                    # to check if file is valid image
                    Image.open(fil.path)
                    self.encode(fil.path)
                except IOError as err:
                    print("Warning: Found non image file: " + fil.path)
                    pass

    def load_image(self, path, colorspace="lab", quantize=False):
        """
        :param quantize: quantize loaded image (only applies to ab of LAB)
        """
        if colorspace == "lab":
            img_rgb = cv2.cvtColor(cv2.imread(path, 1), cv2.COLOR_BGR2RGB)
            img_lab = self.rgb_to_lab(img_rgb)
            img_lab[1] = self.quantize(img_lab[1], k=self.quantize_k, ret_labels=False)
            img_lab[2] = self.quantize(img_lab[2], k=self.quantize_k, ret_labels=False)
            return img_lab
        elif colorspace == "rgb":
            img = cv2.cvtColor(cv2.imread(path, 1), cv2.COLOR_BGR2RGB)
            return img
        elif "gray" in colorspace or "grey" in colorspace:
            return cv2.cvtColor(cv2.imread(path, 1), cv2.COLOR_BGR2GRAY)

    def quantize(self, arr, k=0, ret_labels=False):
        """
        Quantizes a 2D Array using K-Means clustering to k clusters.
        :param arr: 2D Array, usually a or b channel.
        :param ret_labels: if True, returns tuple: image with labels from 0-k and centers (label_img, centers). False: normally usable array
        """
        if not k:
            return arr

        # shift to positive if -100-100
        ab_shifted = False
        if np.min(arr) < 0:
            arr = arr + 100
            ab_shifted = True

        inarray=np.array(arr, dtype=np.uint8)
        orig=inarray
        inarray=inarray.reshape((-1,1))
        kmeans=KMeans(n_clusters=k,init='k-means++')
        kmeans.fit(inarray)
        centers=kmeans.cluster_centers_
        labels=kmeans.labels_
        if ret_labels:
            final = labels.reshape(orig.shape)
            centers = centers.astype(int)
            if ab_shifted:
                centers = centers - 100
            return (final, centers)
        else:
            f=[]
            centers=centers.squeeze()
            for i in labels:
                f.append(centers[i])
            final=np.asarray(f)
            final=final.reshape(orig.shape)
            final = final.astype(int)
            if ab_shifted:
                final = final - 100
            return final
        
    def rgb_to_lab(self, rgb):
        return color.rgb2lab(rgb).transpose((2, 0, 1))

    def encode(self, img_path):
        """
        Executes the right encoding method depending on self.method set.
        Converts img to grayscale and saves in self.output_path
        :return:
        """
        self.image_path = img_path
        img_lab_fullres = self.load_image(img_path)
        img_gray = self.load_image(img_path, colorspace="gray")
        ar_utils.save_img(self.output_path, ar_utils.gen_new_gray_filename(img_path), img_gray)

        if "ideepcolor-px" in self.method:
            filename_mask = ar_utils.gen_new_mask_filename(img_path)
            mask = None
            if self.method == "ideepcolor-px-grid":
                mask = self.get_color_mask_grid(img_path, self.grid_size, self.size, self.p)
                mask.save(self.output_path, os.path.basename(filename_mask), grid_size=self.grid_size)
            elif self.method == "ideepcolor-px-selective":
                mask = self.get_color_mask_selective(img_path)
                mask.save(self.output_path, os.path.basename(filename_mask))
            # "ideepcolor-px-grid-exclude"
            elif self.method == ar_utils.methods[4]:
                mask = self.get_color_mask_grid(img_path, self.grid_size, self.size, self.p, exclude=True)
                mask.save(self.output_path, os.path.basename(filename_mask))
            # "ideepcolor-px-grid-selective"
            elif self.method == ar_utils.methods[5]:
                # get two masks, one grid one selective, save both in Decoder combine both
                mask_grid = self.get_color_mask_grid(img_path)
                mask_grid.save(self.output_path, os.path.basename(filename_mask), name_extra="1", grid_size=self.grid_size)

                mask_sel = self.get_color_mask_selective(img_path)#, sigma_gauss_div=225, sigma_bilat_div=250)
                mask_sel.save(self.output_path, os.path.basename(filename_mask), name_extra="2")
                

        elif self.method == "ideepcolor-global":
            self.encode_ideepcolor_global(img_path, self.size)

        # ideepcolor-stock: no encoding necessary
        elif self.method == ar_utils.methods[3]:
            pass

        else:
            print("Error: method not valid:", self.method)

    def encode_ideepcolor_global(self, img_path, size) -> np.ndarray:
        import caffe
        lab = importlib.import_module("interactive-deep-colorization.data.lab_gamut")

        img_path = os.path.abspath(img_path)
        prev_wd = os.getcwd()

        ideepcolor_folder = "./interactive-deep-colorization"
        # check if already in folder
        if not os.path.basename(ideepcolor_folder) == os.path.basename(os.getcwd()):
            os.chdir(ideepcolor_folder)
            
        # models need to be downloaded before, using "interactive-deep-colorization/models/fetch_models.sh"
        global_stats_model = os.path.abspath('./models/global_model/global_stats.prototxt')
        weights = os.path.abspath('./models/global_model/dummy.caffemodel')
        gt_glob_net = caffe.Net(global_stats_model, 1, weights=weights)

        # load image
        ref_img_fullres = caffe.io.load_image(os.path.abspath(img_path))
        img_glob_dist = (255*caffe.io.resize_image(ref_img_fullres,(size,size))).astype('uint8')
        gt_glob_net.blobs['img_bgr'].data[...] = img_glob_dist[:,:,::-1].transpose((2,0,1))
        gt_glob_net.forward()
        glob_dist_in = gt_glob_net.blobs['gt_glob_ab_313_drop'].data[0,:-1,0,0].copy()
        os.chdir(prev_wd)

        ar_utils.save_glob_dist(self.output_path, img_path, glob_dist_in)
        return glob_dist_in

    def denoise_image_for_px_selection(self, rgb, k=5):
        """
        :param rgb: input image in rgb format
        :return: median denoised image in rgb format
        """
        return cv2.medianBlur(rgb, k)

    def get_color_mask_grid(self, img_path, grid_size=None, size=None, p=None, exclude=False, rand_offset=None):
        """
        :param img: original color image as lab (lab, y, x)
        :param grid_size: distance between pixels of grid in pixels 0 - mask size (-1: every space filled, 0: None filled (stock coloring))
        :param exclude: Use exclude method. Leave out similar colored pixels
        :param rand_offset: For testing/debugging, give every pixel in the grid a random offset of +-this. if used, don't save with grid.
        :return Mask: Mask of pixels
        """
        # TODO: replace in code properly by globals
        if p is None:
            p = self.p
        if size is None:
            size = self.size
        if grid_size is None:
            grid_size = self.grid_size
            
        mask = ar_utils.Mask(size=size, p=p)
        if grid_size == 0:
            return mask

        rgb = self.load_image(img_path, colorspace="rgb")
        rgb = self.denoise_image_for_px_selection(rgb, k=5)
        img = self.rgb_to_lab(rgb)
        # if k=0 (default), arr will not be modified
        img[1] = self.quantize(img[1], k=self.quantize_k, ret_labels=False)
        img[2] = self.quantize(img[2], k=self.quantize_k, ret_labels=False)

        h = len(img[0])
        w = len(img[0][0])

        for y in range(size):
            if y % grid_size != 0:
                continue
            for x in range(size):
                if x % grid_size != 0:
                    continue
                use_px = True
                if exclude:
                    use_px = self.mask_check_vicinity(img, y, x)
                if use_px:
                    if rand_offset and not exclude:
                        y_off = random.randrange(-rand_offset, rand_offset)
                        x_off = random.randrange(-rand_offset, rand_offset)
                        if y+y_off>=size or y-y_off<0 or x+x_off>=size or x-x_off<0:
                            continue
                        y_img, x_img = ar_utils._coord_mask_to_img(h, w, y+y_off, x+x_off, size)
                        mask.put_point((y+y_off, x+x_off), [ img[1][y_img][x_img],
                                                             img[2][y_img][x_img] ])
                    else:
                        y_img, x_img = ar_utils._coord_mask_to_img(h, w, y, x, size)
                        mask.put_point((y, x), [ img[1][y_img][x_img],
                                                 img[2][y_img][x_img] ])
                    

        if self.plot:
            import matplotlib.pyplot as plt
            rgb = self.load_image(img_path, colorspace="rgb")
            plt.imshow(rgb)
            y_arr, x_arr = [], []
            for ys in range(mask.size):
                for xs in range(mask.size):
                    if not mask.mask[0][ys][xs]:
                        continue
                    y_img, x_img = ar_utils._coord_mask_to_img(h, w, ys, xs, size)
                    y_arr.append(y_img)
                    x_arr.append(x_img)

            plt.scatter(x=x_arr, y=y_arr, c='r', s=1)
                    
            plt_fn = ar_utils.gen_new_mask_filename(self.image_path, [self.method, self.size, "scatter"])
            plt_path = os.path.join(self.output_path, plt_fn)
            plt.savefig(plt_path+".png", bbox_inches='tight', dpi=1500)
            plt.clf()
            plt.close()

        return mask

    def mask_check_vicinity(self, img, y, x, round_to=25, radius=1):
        """
        round_to: 10 for cityscapes, 20/25 for colorful high res
        Checks if pixels of same color (rounded) are in square vicinity of size radius of coordinates given.
        y and x mask coordinates, not image
        Returns True if other colors are in vicinity. False if all colors in this radius are the same.
        TODO: clear cache after IR got written
        """
        h = len(img[0])
        w = len(img[0][0])
        # bin_mask = mask.mask[0]

        if not hasattr(self, 'px_vic_cache_a'):
            a = img[1]+100 
            b = img[2]+100
            a = np.int16(a)  # OpenCV is weird. why not int8 ??!!???
            b = np.int16(b)
            self.px_vic_cache_a = self.round_arr_to( self.denoise_image_for_px_selection(a), round_to)
            self.px_vic_cache_b = self.round_arr_to( self.denoise_image_for_px_selection(b), round_to)

        a = self.px_vic_cache_a
        b = self.px_vic_cache_b

        y_img, x_img = ar_utils._coord_mask_to_img(h, w, y, x, self.size)
        center = (a[y_img][x_img], b[y_img][x_img])
        for y_rel in range(-radius, radius):
            for x_rel in range(-radius, radius):
                y_px, x_px = ar_utils._coord_mask_to_img(h, w, y + y_rel, x + x_rel, self.size)
                if y_px >= h or y_px < 0 or x_px >= w or x_px < 0:
                    continue
                ab = (a[y_px][x_px], b[y_px][x_px])
                if center != ab:
                    return True
        return False
        

    # Everything for selective color mask
    def get_color_mask_selective(self, img_path, round_to=10, scaling_factor=None, sigma_gauss_div=250, sigma_bilat_div=500):
        """
        :param sigma_gauss_div: divider for the gaussian sigma (last blurring step). Smaller -> stronger blur -> fewer points. Default: 250
        :return Mask: Mask of pixels
        """
        from skimage import filters, restoration, util, transform
        # PARAM: hardcoded, round_to (for cityscapes rather smaller (8). Default: 10)
        # PARAM: hardcoded, scaling_factor: 8 for highres, or higher. 4, 2 for cityscapes and low res

        # load as rgb 0-255, also save copy for plot later
        rgb_orig = rgb = self.load_image(img_path, colorspace="rgb")

        img_dims = rgb.shape[:-1]

        if not scaling_factor:
            scaling_factor = int(round( min(img_dims)/250 )) # cityscapes(vga; w:480) -> 2, dragon_pool(w:2370) -> 9
        print("Scaling factor: ", scaling_factor)

        mask = ar_utils.Mask(size=self.size, p=self.p)
        
        # Median Filter; remove extreme individual noise pixels
        # will be used for selection of pixels for mask later and also as first preprocessing step
        rgb = self.denoise_image_for_px_selection(rgb, k=5)

        lab_median = self.rgb_to_lab(rgb)
        a_median = lab_median[1].astype(int)
        b_median = lab_median[2].astype(int)
        # will be returned unmodified, if k=0
        a_median = self.quantize(a_median, k=self.quantize_k, ret_labels=False)
        b_median = self.quantize(b_median, k=self.quantize_k, ret_labels=False)
        
        # scale down image
        img_resized = transform.resize(rgb,
                                       (img_dims[0] // scaling_factor, img_dims[1] // scaling_factor),
                                       anti_aliasing=True)

        img_resized = self.rgb_to_lab(img_resized)

        L = img_resized[0].astype(int)
        a = img_resized[1].astype(int)
        b = img_resized[2].astype(int)

        # shift ab into positive (to make filters work)
        a = a.astype(int)+100
        b = b.astype(int)+100

        # Bilateral Filter; Edge preserving blur
        # PARAM: sigma_spatial, (/250)
        sigma_spatial = min(img_dims) / sigma_bilat_div
        print("Sigma Spatial (Bilateral)", sigma_spatial)
        # PARAM: sigma_color: sig-default*100
        sigma_color = None  # restoration.estimate_sigma(img_resized)*100
        print("Sigma Color (Bilateral)", sigma_color)
        # img_resized = restoration.denoise_bilateral(img_resized, multichannel=True,
        #                                             sigma_spatial=sigma_spatial,
        #                                             sigma_color=sigma_color)

        a = restoration.denoise_bilateral(a.astype(float), multichannel=False,
                                          sigma_spatial=sigma_spatial,
                                          sigma_color=sigma_color)
        b = restoration.denoise_bilateral(b.astype(float), multichannel=False,
                                          sigma_spatial=sigma_spatial,
                                          sigma_color=sigma_color)

        # Gaussian blur; smooth out colors a bit more, reduces points overall
        # PARAM: calculated sigma
        sigma = min(a.shape) / sigma_gauss_div  # Gaussian (/250)
        print("Sigma Gaussian:", sigma)
        a = filters.gaussian(a, sigma, preserve_range=True)
        b = filters.gaussian(b, sigma, preserve_range=True)

        # shift back to ab space -100-100
        a = util.img_as_ubyte(a.astype(int)).astype(int)-100
        b = util.img_as_ubyte(b.astype(int)).astype(int)-100

        ab = self.get_ab(a, b, round_to)
        ab_ids = self.set_color_area_ids(ab)
        centres = self.get_centres(ab_ids)

        # delete points near edges, since sometimes they tend to bunch on the edges, and those are not super important for colorization anyway
        h, w = a.shape
        dist = 2  # distance from edges
        keep = np.ones(len(centres), dtype=bool)
        for idx, c in enumerate(centres):
            if c[0] < dist or c[0] > h-dist or c[1] < dist or c[1] > w-dist:
                keep[idx] = False
        centres = centres[keep]

        # Save image with red dots for selected pixels
        if self.plot:
            import matplotlib.pyplot as plt
            plt.imshow(rgb_orig)
            y = np.array( [row[0] for row in centres] )*scaling_factor
            x = np.array( [row[1] for row in centres] )*scaling_factor
            plt.scatter(x=x, y=y, c='r', s=1)
            plt_fn = ar_utils.gen_new_mask_filename(self.image_path, [self.method, self.size])
            plt_path = os.path.join(self.output_path, plt_fn)
            plt.savefig(plt_path+".png", bbox_inches='tight', dpi=1500)
            plt.clf()
            plt.close()

        # Use found interesting pixels as coordinates to fill mask
        h, w = img_dims
        for px in centres:
            # scale up to resolution of input image
            loc = (px[0]*scaling_factor, px[1]*scaling_factor)
            # use colors from median filtered image
            val = (a_median[loc], b_median[loc])
            loc = ar_utils._coord_img_to_mask(h, w, loc[0], loc[1], size=self.size)
            mask.put_point(loc, val)

        return mask

    def round_arr_to(self, arr, r_to=10):
        """
        Rounds numpy array to nearest r_to
        """
        return np.around(arr/r_to, decimals=0)*r_to

    def get_ab(self, a, b, round_to=10):
        """
        Returns an array combined of a and b channels, where each color value has a unique value
        """
        an = self.round_arr_to(a, round_to)
        bn = self.round_arr_to(b, round_to)
        # shift into positive
        an = an + 100
        bn = bn + 100
        ab = an.astype(int)*1000 + bn.astype(int)
        ab = ab.astype(int)
        # ab = np.array([ab, make_arr(ab, l=None)])
        ab = np.array(ab, dtype="uint32")
        return ab

    def flood_fill(self, a, yx, newval):
        from skimage.measure import label
        a = np.array(a)
        y, x = yx
        l = label(a==a[y, x])
        a[l==l[y, x]] = newval
        return a

    def set_color_area_ids(self, ab):
        """
        Replaces every seperate blob of a color with a unique id
        """
        # replace pixel values via ff with unique id
        id_ = 0
        # np.unique sorted ascendingly
        unique_colors = np.unique(ab)
        for col in unique_colors:
            # while as long as there is this color in the array
            while np.where(ab==col)[0].size:
                found_pos = np.where(ab==col)
                y = found_pos[0][0]
                x = found_pos[1][0]
                # run ff from this pixel and give all connected same colors the same id
                ab = self.flood_fill(ab, (y, x), id_)
                # cv2.floodFill(ab_uint8, None, (x, y), id)
                id_ = id_+1
        return ab

    def get_centres(self, ab_ids, random_px_threshold=1000):
        """
        Returns the most centre pixel position of every blob with a unique id
        :param ab_ids: 2D Array of combined a&b channel, where each self-contained unique blob is replaced with a id
        :param random_px_threshold: size of blob, at which to add new random pixels. 
        """
        import scipy.spatial.distance
        import random
        ids = np.unique(ab_ids)
        centres = []

        for id in ids:
            area_coords = np.where(ab_ids == id)
            area_coords_y = area_coords[0]
            area_coords_x = area_coords[1]
            # Skip extremely small blobs of only a few pixels
            if len(area_coords_y) <= 4:
                continue
            # get centre
            centre = ( int(round((sum(area_coords_y)/len(area_coords_y)))),
                       int(round((sum(area_coords_x)/len(area_coords_x)))) )

            # since centre could be outside shape, search nearest point to centre
            closest = None
            dist = float('inf')
            # TODO: get more points if area is above certain size
            # NOTE: this is really slow, if centre not in shape. Maybe just use a random point in this case. 
            for idx, i in enumerate(area_coords_y):
                # break if calculated centre is inside area
                if centre[0] in area_coords_y and centre[1] in area_coords_x:
                    closest = centre
                    break
                
                n_dist = distance.euclidean((area_coords_y[idx], area_coords_x[idx]), centre)
                if n_dist < dist:
                    dist = n_dist
                    closest = (area_coords_y[idx], area_coords_x[idx])
            centres.append(closest)

            # if current blob is particularly large, use additional randomly selected pixels. Not with grid+selective
            if len(area_coords_y) >= random_px_threshold and self.method != ar_utils.methods[5]:

                # scale up additional pixels linearly in beginning, logarithmically later
                if len(area_coords_y) < random_px_threshold*3:
                    add_px = int( len(area_coords_y) // random_px_threshold )
                else:
                    add_px = int(round( math.log(len(area_coords_y), 10) ))
                
                for i in range(add_px):
                    random.seed(i)
                    new_coord = random.randint(0, len(area_coords_y)-1)
                    new_px = (area_coords_y[new_coord], area_coords_x[new_coord])
                    centres.append(new_px)
                    
        return np.array(centres)

    def lab_to_rgb(self, *args):
        """
        Either takes lab array of shape (3, h, w) or as 3 separate 2D Arrays, l, a, b
        """
        lab = None
        if len(args) == 1:
            lab = args[0]
        elif len(args) == 3:
            lab = [args[0], args[1], args[2]]
        else:
            print("Wrong number of arguments in lab_to_rgb. ")
            return None
        return np.fliplr(np.rot90(color.lab2rgb(np.transpose(lab)), 3))



if __name__ == "__main__":
    ec = Encoder()
    ec.main()
