#!/usr/bin/env python3

import argparse
import importlib
from PIL import Image
import os, sys
import ar_utils, encoder, decoder

# -'s in import not allowed
# ideepcolor = importlib.import_module("interactive-deep-colorization")
CI = importlib.import_module("interactive-deep-colorization.data.colorize_image")
# CICIT = importlib.import_module("interactive-deep-colorization.data.colorize_image.ColorizeImageTorch")
# ideepcolor_pytorch = importlib.import_module("colorization-pytorch")

sys.path.insert(1, os.path.abspath("interactive-deep-colorization"))

# TODO: add full auto mode: watch folder for new images
# TODO: add config file parser. Encoder, Decoder etc.
# TODO: Encoder, Decoder
class Recolor(object):
    def __init__(self):
        self.methods = ar_utils.methods
        self.method = self.methods[0]
        # True for retrained, false for caffe model
        self.maskcent = False
        self.load_size = 256

        # Whether to save the mask of colorization pixels
        self.input_mask = True
        # Whether to open an extra window with the output
        self.show_plot = False
        self.ir_folder = None

        # lower CPU priority (to not freeze PC)
        # os.nice(19)


    def main(self):
        parser = argparse.ArgumentParser(prog='Recolor', description='TODO')

        parser.add_argument('-o', '--output_path', action='store', dest='output_path', type=str,
                               default='output_images',
                               help='The path to the folder or file, where the output will be written to. ')
        parser.add_argument('-i', '--input_path', action='store', dest='input_path', type=str,
                               default='input_images',
                               help='The path to the folder with input color images... What did you expect?')
        parser.add_argument('-ir', '--intermediate_representation', action='store', dest='intermediate_representation', type=str,
                               default='intermediate_representation',
                               help='The path, where the grayscale images + color cues will be stored')
        parser.add_argument('-m', '--method', action='store', dest='method', type=str, default=self.methods[0],
                            help='The colorization method to use. Possible values: \"' + ', '.join(self.methods) + '\"')

        # parser.add_argument('--color_model', dest='color_model', help='colorization model (color & dist for Pytorch)', type=str,
        #                 default='colorization-pytorch/checkpoints/siggraph_caffemodel/latest_net_G.pth')
        # 'colorization-pytorch/checkpoints/siggraph_retrained/latest_net_G.pth'

        # for ideepcolor-px
        parser.add_argument('-s', '--size', action='store', dest='size', type=int, default=256,
                               help='Size of the indermediate mask to store the color pixels. Power of 2. \
                               The bigger, the more accurate the result, but requires more storage, and RAM capacity (decoder) \
                               (For 2048 up to 21GB RAM)')
        parser.add_argument('-g', '--grid_size', action='store', dest='grid_size', type=int, default=10,
                               help='Spacing between color pixels in intermediate mask (--size).  -1: fill every spot in mask.  0: dont use any color pixel ')
        parser.add_argument('-p', '--p', action='store', dest='p', type=int, default=0,
                               help='The "radius" the color values will have. \
                               A higher value means one color pixel will later cover multiple gray pixels. Default: 0')
        parser.add_argument('-plt','--plot', dest='plot', help='Generate Plots for visualization', action='store_true')
        parser.add_argument('-q', '--quantize', dest='quantize', action='store', type=int, default=0,
                            help='Quantize Pixel values. Number of bins. Default: not used (0), off. ')
        # TODO: test gpu on cuda gpu
        parser.add_argument('--gpu_id', dest='gpu_id', help='gpu id', type=int, default=-1)
        # TODO: remove?
        parser.add_argument('--cpu_mode', dest='cpu_mode', help='do not use gpu', action='store_true')
        # parser.add_argument('--pytorch_maskcent', dest='pytorch_maskcent', help='need to center mask (activate for siggraph_pretrained but not for converted caffemodel)', action='store_true')
        parser.add_argument('--delete_gray', dest='delete_gray', help='Delete generated grayscale image after colorization', action='store_true')


        args = parser.parse_args()
        # self.maskcent = args.pytorch_maskcent
        # self.show_plot = args.show_plot

        if args.cpu_mode:
            self.gpu_id = -1
            args.gpu_id = -1

        if args.grid_size > 255:
            print("Warning: truncating grid size to 255")
            args.grid_size = 255


        if args.method not in self.methods:
            print("Method not valid. One of: \"" + ', '.join(self.methods) + '\"')
            sys.exit(1)
        self.method = args.method

        self.ir_path = os.path.abspath(args.intermediate_representation)
        args.intermediate_representation = self.ir_path

        if not os.path.isdir(args.input_path):
            if not os.path.isfile(args.input_path):
                print('The input_path is not a directory or file')
                sys.exit(1)

        if not os.path.isdir(args.input_path):
            # TODO: check if image

            self.img_recolor(args, args.input_path)

        # colorize all pictures in folder
        elif os.path.isdir(args.input_path):
            os.makedirs(args.output_path, exist_ok=True)
            os.makedirs(args.intermediate_representation, exist_ok=True)
            
            for root, d_names, f_names in os.walk(args.input_path):
                for file_name in f_names:
                    file_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(file_path, args.input_path)
                    output_file = os.path.join(args.output_path, relative_path)


                    try:
                        # to check if valid image
                        Image.open(file_path)
                        print("\nNow recoloring: ", file_path)
                        self.img_recolor(args, file_path)
                    except IOError as err:
                        print("Skipping non image file: ", file_path)
                        print(err)
                        # traceback.print_exc()
                        print()
                        pass


    def img_recolor(self, args, input_image_path):
        """
        Performs Encoding and Decoding at once
        """
        
        ec = encoder.Encoder(output_path=args.intermediate_representation, method=args.method,
                             size=args.size, p=args.p, grid_size=args.grid_size, plot=args.plot, quantize=args.quantize)
        dc = decoder.Decoder(output_path=args.output_path, method=args.method, size=args.size, p=args.p, gpu_id=args.gpu_id, plot=args.plot)

        ec.encode(input_image_path)
        img_gray_name = ar_utils.gen_new_gray_filename(input_image_path)
        img_gray_path = os.path.join(args.intermediate_representation, img_gray_name)
        dc.decode(img_gray_path)

        if args.delete_gray and os.path.exists(img_gray_path):
            os.remove(img_gray_path)
        

if __name__ == "__main__":
    rc = Recolor()
    rc.main()