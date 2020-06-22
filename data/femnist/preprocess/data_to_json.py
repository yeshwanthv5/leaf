# Converts a list of (writer, [list of (file,class)]) tuples into a json object
# of the form:
#   {users: [bob, etc], num_samples: [124, etc.],
#   user_data: {bob : {x:[img1,img2,etc], y:[class1,class2,etc]}, etc}}
# where 'img_' is a vectorized representation of the corresponding image

from __future__ import division
import json
import math
import numpy as np
import os
import sys

from PIL import Image

utils_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
utils_dir = os.path.join(utils_dir, 'utils')
sys.path.append(utils_dir)

import util

MAX_WRITERS = int(sys.argv[1])  # max number of writers per json file.
print("Max writers per JSON", MAX_WRITERS)

DATA_PARTITION = int(sys.argv[2]) # 0 - Full data. 1 - (0-4 digits A-M, a-m) 2 - (5-9 digits N-Z, n-z)
print("Data partition:", DATA_PARTITION)

def relabel_class(c):
    '''
    maps hexadecimal class value (string) to a decimal number
    returns:
    - 0 through 9 for classes representing respective numbers
    - 10 through 35 for classes representing respective uppercase letters
    - 36 through 61 for classes representing respective lowercase letters
    '''
    if c.isdigit() and int(c) < 40:
        return (int(c) - 30)
    elif int(c, 16) <= 90: # uppercase
        return (int(c, 16) - 55)
    else:
        return (int(c, 16) - 61)

parent_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

by_writer_dir = os.path.join(parent_path, 'data', 'intermediate', 'images_by_writer')
writers = util.load_obj(by_writer_dir)

num_json = int(math.ceil(len(writers) / MAX_WRITERS))

users = []
num_samples = []
user_data = {}

writer_count = 0
json_index = 0
for (w, l) in writers:

    users.append(w)
    num_samples.append(len(l))
    user_data[w] = {'x': [], 'y': []}

    size = 28, 28  # original image size is 128, 128
    for (f, c) in l:
        file_path = os.path.join(parent_path, f)
        img = Image.open(file_path)
        gray = img.convert('L')
        gray.thumbnail(size, Image.ANTIALIAS)
        arr = np.asarray(gray).copy()
        vec = arr.flatten()
        vec = vec / 255  # scale all pixel values to between 0 and 1
        vec = vec.tolist()

        nc = relabel_class(c)

        if DATA_PARTITION == 1:
            if (nc >= 0 and nc <= 4) or (nc >= 10 and nc <= 22) or (nc >= 36 and nc <= 48):
                user_data[w]['x'].append(vec)
                user_data[w]['y'].append(nc)
        elif DATA_PARTITION == 2:
            if (nc >= 5 and nc <= 9) or (nc >= 23 and nc <= 35) or (nc >= 49 and nc <= 61):
                user_data[w]['x'].append(vec)
                user_data[w]['y'].append(nc)
        else:
            user_data[w]['x'].append(vec)
            user_data[w]['y'].append(nc)

    writer_count += 1
    if writer_count == MAX_WRITERS:

        all_data = {}
        all_data['users'] = users
        all_data['num_samples'] = num_samples
        all_data['user_data'] = user_data

        file_name = 'all_data_%d.json' % json_index
        file_path = os.path.join(parent_path, 'data', 'all_data', file_name)

        print('writing %s' % file_name)

        with open(file_path, 'w') as outfile:
            json.dump(all_data, outfile)

        writer_count = 0
        json_index += 1
        
        users[:] = []
        num_samples[:] = []
        user_data.clear()

# Handle the last few users
if writer_count > 0:
    all_data = {}
    all_data['users'] = users
    all_data['num_samples'] = num_samples
    all_data['user_data'] = user_data

    file_name = 'all_data_%d.json' % json_index
    file_path = os.path.join(parent_path, 'data', 'all_data', file_name)

    print('writing %s' % file_name)

    with open(file_path, 'w') as outfile:
        json.dump(all_data, outfile)

    writer_count = 0
    json_index += 1

    users[:] = []
    num_samples[:] = []
    user_data.clear()
